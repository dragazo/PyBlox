#!/usr/bin/env python

import netsblox
import time

client = netsblox.Client()

g, h, i = None, None, None
def foo(x, y):
    global g
    g = (x, y)
def bar(z, y):
    global h
    h = (y, z)
def baz(y, **extra):
    global i
    i = sorted(list(extra.items()))
client.on_message('vec', foo)
client.on_message('vec', bar)
client.on_message('vec', baz)

client.send_message('vec', y=2, x=1, z=3)
time.sleep(0.5)
assert g == (1, 2)
assert h == (2, 3)
assert i == [('x', 1), ('z', 3)]