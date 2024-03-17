#!/usr/bin/env python

import netsblox
import time

editor = netsblox.Client()

total_a, total_b = 0, 0

@editor.on_message('tick')
def foo(ticks):
    global total_a
    total_a += ticks

@editor.on_message('tick')
def bar(ticks):
    global total_b
    total_b += ticks

for i in range(1,11):
    editor.send_message('tick', ticks = i)
    time.sleep(0.5)
assert total_a == 55, f'got {total_a}'
assert total_b == 55, f'got {total_b}'
