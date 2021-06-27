def foo(a, b, c, *d, **k):
    if c:
        print(a, b)
    return a + b


def bar(x):
    r = 0
    if x:
        r = foo(x, 2, False, 10, 20, foo=42)
    return r
