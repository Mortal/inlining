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

```
nnoremap \I ma:exec "%!python ~/work/inlining/inlining.py --input /dev/stdin --location ".line(".").":".col(".")<CR>`a
```
