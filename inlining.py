import abc
import argparse
import ast
import parso
import textwrap
from abc import ABC
from typing import Union, List, Dict


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True, dest="filename")
parser.add_argument("--location", required=True)


def my_literal_eval(node_or_string):
    """
    Based on ast.literal_eval()
    """
    if isinstance(node_or_string, str):
        node_or_string = ast.parse(node_or_string, mode="eval")
    if isinstance(node_or_string, ast.Expression):
        node_or_string = node_or_string.body

    def _raise_malformed_node(node):
        raise ValueError(f"malformed node or string: {node!r}")

    def _convert_num(node):
        if not isinstance(node, ast.Constant) or type(node.value) not in (
            int,
            float,
            complex,
        ):
            _raise_malformed_node(node)
        return node.value

    def _convert_signed_num(node):
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = _convert_num(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            else:
                return -operand
        return _convert_num(node)

    def _convert(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, ast.List):
            return list(map(_convert, node.elts))
        elif isinstance(node, ast.Set):
            return set(map(_convert, node.elts))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "set"
            and node.args == node.keywords == []
        ):
            return set()
        elif isinstance(node, ast.Dict):
            if len(node.keys) != len(node.values):
                _raise_malformed_node(node)
            return dict(zip(map(_convert, node.keys), map(_convert, node.values)))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            left = _convert_signed_num(node.left)
            right = _convert_num(node.right)
            if isinstance(left, (int, float)) and isinstance(right, complex):
                if isinstance(node.op, ast.Add):
                    return left + right
                else:
                    return left - right
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            # Added case compared to ast.literal_eval
            return not _convert(node.operand)
        return _convert_signed_num(node)

    return _convert(node_or_string)


def guess_definition(name):
    assert name.type == "name"
    v = name.value

    def visit(n):
        while n is not None:
            for a in n.children:
                if a.type == "decorated":
                    f = a.children[1]
                else:
                    f = a
                if f.type == "funcdef":
                    assert f.children[0].value == "def"
                    assert f.children[1].type == "name"
                    if f.children[1].value == v:
                        yield f
                # if f.type == "expr_stmt":
            n = n.parent

    return next(visit(name.parent), None)


def parse_formals(param_nodes):
    posonlyargs = []
    args = []
    seen_vararg = False
    vararg = None
    kwonlyargs = []
    kwarg = None
    kw_defaults = []
    defaults = []
    for node in param_nodes:
        tok = node.children[0]
        if tok.value == "*":
            assert not seen_vararg
            seen_vararg = True
            vararg_node = node.children[1:]
            if vararg_node:
                assert vararg_node[0].type == "name"
                vararg = ast.Name(vararg_node[0].value)
        elif tok.value == "**":
            assert kwarg is None
            kwarg = ast.Name(node.children[1].value)
        elif tok.value == "/":
            posonlyargs, args = args, []
        elif seen_vararg:
            kwonlyargs.append(ast.Name(tok.value))
            default = node.children[1:]
            if "=" in default:
                kw_defaults.append(default[default.index("=") + 1])
        else:
            args.append(ast.Name(tok.value))
            default = node.children[1:]
            if "=" in default:
                defaults.append(default[default.index("=") + 1])
    return ast.arguments(posonlyargs, args, vararg, kwonlyargs, kw_defaults, kwarg, defaults)


class ActualsBase(ABC):
    @abc.abstractmethod
    def lookup(self, node) -> Union[None, parso.tree.NodeOrLeaf, List[parso.tree.NodeOrLeaf], Dict[str, parso.tree.NodeOrLeaf]]:
        ...


class SimpleActuals(ActualsBase):
    def __init__(self, assignment: Dict[str, Union[parso.tree.NodeOrLeaf, List[parso.tree.NodeOrLeaf], Dict[str, parso.tree.NodeOrLeaf]]]) -> None:
        self._assignment = assignment

    def lookup(self, node) -> Union[None, parso.tree.NodeOrLeaf, List[parso.tree.NodeOrLeaf], Dict[str, parso.tree.NodeOrLeaf]]:
        if not isinstance(node, parso.tree.Leaf):
            return None
        return self._assignment.get(node.value)


def assign_args_to_formals(formals, args) -> SimpleActuals:
    i = 0
    vararg = []
    posargs = formals.posonlyargs + formals.args
    assignment = {}
    while i < len(args) and args[i].type != "argument":
        if i < len(posargs):
            assignment[posargs[i].id] = args[i]
        else:
            vararg.append(args[i])
        i += 1
    names = {a.id for a in formals.args + formals.kwonlyargs}
    kwarg = {}
    for a in args[i:]:
        assert a.type == "argument"
        assert "=" in a.children
        assert a.children[1].value == "="
        k = a.children[0].value
        if k in names:
            names.remove(k)
            assert k not in assignment
            assignment[k] = a.children[2]
        else:
            kwarg[k] = a.children[2]
    for k, v in zip(posargs[i:], formals.defaults[i:]):
        if v is not None:
            assignment.setdefault(k.id, v)
    for k, v in zip(formals.kwonlyargs, formals.kw_defaults):
        if v is not None:
            assignment.setdefault(k.id, v)
    assert not vararg or formals.vararg
    if formals.vararg:
        assignment[formals.vararg.id] = vararg
    assert not kwarg or formals.kwarg
    if formals.kwarg:
        assignment[formals.kwarg.id] = kwarg
    return SimpleActuals(assignment)


def get_adjusted_prefix(extra_spaces, n):
    if n.start_pos[1] != len(n.prefix):
        return n.prefix
    elif extra_spaces < 0:
        return n.prefix[-extra_spaces:]
    else:
        return n.prefix + " " * extra_spaces


def do_inlining(extra_spaces, n, actuals: ActualsBase, before, after):
    assert isinstance(n, parso.tree.NodeOrLeaf), n
    actual_value = actuals.lookup(n)
    if actual_value is not None:
        if not isinstance(actual_value, parso.tree.NodeOrLeaf):
            raise NotImplementedError("vararg or kwarg")
        yield get_adjusted_prefix(extra_spaces, n) + actual_value.get_code(False)
        return
    if isinstance(n, parso.tree.Leaf):
        yield get_adjusted_prefix(extra_spaces, n) + n.value
        return
    # assert isinstance(n, parso.tree.Node), n
    children = n.children
    if n.type == "if_stmt":
        # <if> <expr> <:> <body> (<elif> <expr> <:> <body>)* (<else> <:> <body>)?
        i = 0
        j = 0
        while i < len(children):
            assert i != 0 or children[i].value == "if"
            assert i == 0 or children[i].value in ("elif", "else")
            if children[i].value == "else":
                assert len(children) == i + 3
                if j > 0:
                    rest = ["".join(do_inlining(extra_spaces, c, actuals, before, after)) for c in children[i:]]
                    yield "".join(rest)
                else:
                    body = children[i + 2]
                    assert body.children[0].type == "newline"
                    extra_spaces += get_indent(body) - get_indent(n.children[0])
                    body_code = "".join(do_inlining(extra_spaces, body, actuals, before, after))
                    assert body_code.startswith("\n")
                    yield body_code[1:]
                break
            assert len(children) >= i + 4
            expr = "".join(do_inlining(extra_spaces, children[i + 1], actuals, before, after))
            try:
                expr_value = my_literal_eval(textwrap.dedent(expr).strip())
                const = True
            except Exception:
                expr_value = None
                const = False
            if const and not expr_value:
                # Dead code elimination: `if False: ...` without an else.
                pass
            elif const and expr_value:
                # Dead code elimination: `if True: ...` without an else.
                if j > 0:
                    # We already output an "if".
                    # Turn "elif <expr>" into "else".
                    yield get_adjusted_prefix(extra_spaces, children[i]) + "else:" + "".join(do_inlining(extra_spaces, children[i + 3], actuals, before, after))
                else:
                    body = children[i + 3]
                    assert body.children[0].type == "newline"
                    extra_spaces += get_indent(body) - get_indent(n.children[0])
                    body_code = "".join(do_inlining(extra_spaces, body, actuals, before, after))
                    assert body_code.startswith("\n")
                    yield body_code[1:]
                # Break because there are no more cases to consider after "if True"
                break
            else:
                # Regular case
                if j > 0:
                    if_ = "elif"
                else:
                    if_ = "if"
                rest = ["".join(do_inlining(extra_spaces, c, actuals, before, after)) for c in children[i + 2 : i + 4]]
                j += 1
                yield get_adjusted_prefix(extra_spaces, children[i]) + if_ + expr + "".join(rest)
            i += 4
        return
    if n.type in ("star_expr", "argument") and children[1].type == "name":
        if children[0].value == "*":
            actual_value = actuals.lookup(children[1])
            if isinstance(actual_value, list):
                yield ", ".join(c.get_code(False) for c in actual_value)
                return
        if children[0].value == "**":
            actual_value = actuals.lookup(children[1])
            if isinstance(actual_value, dict):
                yield ", ".join("%s=%s" % (k, c.get_code(False)) for k, c in actual_value.items())
                return
    if n.type == "return_stmt":
        inner = "".join("".join(do_inlining(extra_spaces, c, actuals, before, after)) for c in children[1:])
        yield "%s%s%s%s" % (get_adjusted_prefix(extra_spaces, n.children[0]), before.lstrip(), inner.strip(), after)
        return
    for c in children:
        yield from do_inlining(extra_spaces, c, actuals, before, after)


def get_indent(n) -> int:
    l, c = n.get_start_pos_of_prefix()
    assert n.start_pos[0] == l
    return n.start_pos[1] - c


def main(location: str, filename: str):
    lineno, col = map(int, location.split(":"))
    with open(filename) as fp:
        file_contents = fp.read()
    module = parso.parse(file_contents)
    name = module.get_name_of_position((lineno, col))
    assert name.type == "name"
    call_trailer = name.get_next_sibling()
    assert call_trailer.type == "trailer"
    leaf = call_trailer.get_first_leaf()
    assert leaf == "(", leaf

    assert call_trailer.parent is not None
    assert call_trailer.parent.type == "atom_expr"
    atom_expr = list(call_trailer.parent.children)
    call_trailer_i = next(i for i, o in enumerate(atom_expr) if o is call_trailer)
    called_name, *called_attrs = atom_expr[:call_trailer_i]
    assert called_name is name
    assert all(a.type == "trailer" and a.children[0].value == "." for a in called_attrs)
    assert all(a.get_code() == "." + a.children[1].value for a in called_attrs)
    called = [name] + [a.children[1] for a in called_attrs]

    lines = file_contents.splitlines(True)

    anc = call_trailer
    while anc.type != "expr_stmt":
        assert anc.parent is not None
        anc = anc.parent
    assert anc is not None
    code = "".join(c.get_code() for c in [name, *called_attrs, call_trailer])
    context_indentation = get_indent(anc)
    before, after = anc.get_code().split(code.strip())

    assert call_trailer.children[0].value == "("
    assert call_trailer.children[2].value == ")"
    arglist = call_trailer.children[1]
    assert arglist.type == "arglist"
    commas = arglist.children[1::2]
    assert all(c.value == "," for c in commas)
    args = arglist.children[::2]

    defn = guess_definition(name)
    assert defn.type == "funcdef"
    parameters = defn.get_params()
    formals = parse_formals(parameters)
    actuals = assign_args_to_formals(formals, args)
    implementation = defn.children[4]
    assert implementation.type == "suite"
    assert implementation.children[0].type == "newline"
    implementation_indentation = get_indent(implementation.children[1])

    return locals()


def print_it(*, lines, implementation_indentation, context_indentation, lineno, file_contents, called_name, before, after, defn, parameters, actuals, implementation, **_):
    print("".join(lines[:lineno - 1]), end="")
    # print(called_name.parent.get_code(False))
    # print("%sHOLE%s" % (before, after))
    # print("def %s(%s):" % (defn.children[1].value, " ".join(p.get_code(False) for p in parameters)))
    # for k, v in actuals.items():
    #     try:
    #         print(f"{k} = {v.get_code(False)}")
    #     except AttributeError:
    #         print(f"{k} = {v}")
    inl = "".join(do_inlining(context_indentation - implementation_indentation, implementation, actuals, before, after))
    print(inl.strip("\n"))
    print("".join(lines[lineno:]), end="")


if __name__ == "__main__":
    print_it(**main(**vars(parser.parse_args())))
