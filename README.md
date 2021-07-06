Inlining Python code with Parso
===============================

Requires parso==0.8.2

```
$ python inlining.py --input example.py --location 12:15
def foo(a, b, c, *d, **k):
    dict(**k)
    print(*d)
    if c:
        print(a, b)
    return a + b


def bar(x):
    r = 0
    if x:
    dict(foo=42)
    print(10, 20)
    r = x + 2
    return r
```

```
nnoremap \I ma:exec "%!python ~/work/inlining/inlining.py --input /dev/stdin --location ".line(".").":".col(".")<CR>`a
```
