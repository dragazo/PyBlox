#!/usr/bin/env python

import netsblox
import time

editor = netsblox.Client()

g, h, i = None, None, None

@editor.on_message('vec')
def foo(x, y):
    global g
    g = (x, y)

@editor.on_message('vec')
def bar(z, y):
    global h
    h = (y, z)

@editor.on_message('vec')
def baz(y, **extra):
    global i
    i = sorted(list(extra.items()))

editor.send_message('vec', y=2, x=1, z=3)
time.sleep(0.5)
assert g == (1, 2)
assert h == (2, 3)
assert i == [('x', 1), ('z', 3)]
