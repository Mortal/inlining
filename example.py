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
        r = foo(x, 2, False, 10, 20, foo=42)
    return r
