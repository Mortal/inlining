Inlining Python code with Parso
===============================

Requires parso==0.8.2

```
$ python inlining.py --input example.py --location 12:16
foo(x, 2, False, 10, 20, foo=42)
        r = HOLE
def foo(a, b, c, *d, **k):
a = x
b = 2
c = False
d = [<Number: 10>, <Number: 20>]
k = {'foo': <Number: 42>}

    dict(foo=42)
    print(10, 20)
        r = x + 2

```
