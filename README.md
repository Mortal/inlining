Inlining Python code with Parso
===============================

```
$ python inlining.py --input example.py --location 10:16
foo(x, 2, False, 10, 20, foo=42)
def foo(a, b, c, *d, **k):
a = x
b = 2
c = False
d = [<Number: 10>, <Number: 20>]
k = {'foo': <Number: 42>}

    if False:
        print(x, 2)
    return x + 2
```
