Inlining Python code with Parso
===============================

Requires parso==0.8.2

```
$ python3 inlining.py --input example.py --location 30:15
def foo(a, b, c, *d, **k):
    dict(**k)
    print(*d)
    if c:
        print(a, b)
    if not c:
        print(b, a)
    if True:
        print("if True")
    if False:
        print("if False")
    elif a:
        print("elif a")
    if False:
        print("if False")
    elif True:
        print("elif True")
    else:
        print("else after elif True")
    if False:
        print("if False")
    else:
        print("else")
    return a + b


def bar(x):
    r = 0
    if x:
        dict(foo=42)
        print(10, 20)
        print(2, x)
        print("if True")
        if x:
            print("elif a")
        print("elif True")
        print("else")
        r = x + 2
    return r
```

```vim
nnoremap \I ma:exec "%!python ~/work/inlining/inlining.py --input /dev/stdin --location ".line(".").":".col(".")<CR>`a
```

```vim
py3 <<EOF
def _load_py_module_from_file(name, filepath):
	import importlib
	spec = importlib.util.spec_from_file_location(name, filepath)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def py_inlining_wrapper():
	inlining = _load_py_module_from_file("inlining", "/home/rav/work/inlining/inlining.py")
	w = vim.current.window
	row, col = w.cursor
	start_line, end_line, inl = inlining.compute_inlining("\n".join(vim.current.buffer), row, col)
	if end_line == start_line:
		end_line += 1
	vim.current.buffer[start_line-1:end_line-1] = inl.splitlines()
EOF
au FileType python nnoremap <silent> <buffer> <Leader>I :py3 py_inlining_wrapper()<CR>
```
