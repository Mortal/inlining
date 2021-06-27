import argparse
import ast
import parso
import textwrap


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--location", required=True)


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


def assign_args_to_formals(formals, args):
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
    if vararg:
        assert formals.vararg
        assignment[formals.vararg.id] = vararg
    if kwarg:
        assert formals.kwarg
        assignment[formals.kwarg.id] = kwarg
    return assignment


def do_inlining(n, actuals, before, after):
    assert isinstance(n, parso.tree.NodeOrLeaf), n
    if isinstance(n, parso.tree.Leaf):
        code = n.get_code()
        if n.value in actuals:
            yield code.replace(n.value, actuals[n.value].get_code(False))
        else:
            yield code
        return
    children = n.children
    if n.type == "if_stmt":
        if_, expr, *rest = ("".join(do_inlining(c, actuals, before, after)) for c in children)
        try:
            expr_value = ast.literal_eval(textwrap.dedent(expr))
            const = True
        except Exception:
            expr_value = None
            const = False
        if const and not expr_value and len(children) == 4:
            # Dead code elimination: `if False: ...` without an else.
            return
        yield if_ + expr + "".join(rest)
        return
    if n.type in ("star_expr", "argument") and children[1].type == "name":
        nam = children[1].value
        if children[0].value == "*":
            if nam in actuals and isinstance(actuals[nam], list):
                yield ", ".join(c.get_code(False) for c in actuals[nam])
                return
        if children[0].value == "**":
            if nam in actuals and isinstance(actuals[nam], dict):
                yield ", ".join("%s=%s" % (k, c.get_code(False)) for k, c in actuals[nam].items())
                return
    if n.type == "return_stmt":
        inner = "".join("".join(do_inlining(c, actuals, before, after)) for c in children[1:])
        yield "%s%s%s" % (before, inner.strip(), after)
        return
    for c in children:
        yield from do_inlining(c, actuals, before, after)


def main():
    args = parser.parse_args()
    lineno, col = map(int, args.location.split(":"))
    with open(args.input) as fp:
        code = fp.read()
    module = parso.parse(code)
    leaf = module.get_leaf_for_position((lineno, col))
    assert leaf == "(", leaf
    assert leaf.parent is not None
    call_trailer = leaf.parent
    assert call_trailer.type == "trailer"

    assert call_trailer.parent is not None
    assert call_trailer.parent.type == "atom_expr"
    atom_expr = list(call_trailer.parent.children)
    call_trailer_i = next(i for i, o in enumerate(atom_expr) if o is call_trailer)
    called_name, *called_attrs = atom_expr[:call_trailer_i]
    assert called_name.type == "name"
    assert all(a.type == "trailer" and a.children[0].value == "." for a in called_attrs)
    assert all(a.get_code() == "." + a.children[1].value for a in called_attrs)
    called = [called_name] + [a.children[1] for a in called_attrs]
    print(called_name.parent.get_code(False))
    anc = call_trailer
    while anc.type != "expr_stmt":
        assert anc.parent is not None
        anc = anc.parent
    assert anc is not None
    code = "".join(c.get_code() for c in [called_name, *called_attrs, call_trailer])
    before, after = anc.get_code().split(code.strip())
    print("%sHOLE%s" % (before, after))

    assert call_trailer.children[0].value == "("
    assert call_trailer.children[2].value == ")"
    arglist = call_trailer.children[1]
    assert arglist.type == "arglist"
    commas = arglist.children[1::2]
    assert all(c.value == "," for c in commas)
    args = arglist.children[::2]

    defn = guess_definition(called[0])
    assert defn.type == "funcdef"
    parameters = defn.children[2]
    assert parameters.type == "parameters"
    assert parameters.children[0].value == "("
    assert parameters.children[-1].value == ")"
    print("def %s%s:" % (defn.children[1].value, parameters.get_code(False)))
    formals = parse_formals(parameters.children[1:-1])
    actuals = assign_args_to_formals(formals, args)
    for k, v in actuals.items():
        try:
            print(f"{k} = {v.get_code(False)}")
        except AttributeError:
            print(f"{k} = {v}")
    implementation = defn.children[4]
    assert implementation.type == "suite"
    print("".join(do_inlining(implementation, actuals, before, after)))


if __name__ == "__main__":
    main()
