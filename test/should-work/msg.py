#!/usr/bin/env python

import netsblox
import time

client = netsblox.Client()

total_ticks = 0
def foo(ticks):
    global total_ticks
    total_ticks += ticks
client.on_message('tick', foo)

for i in range(1,11):
    client.send_message('tick', ticks = i)
    time.sleep(0.5)
assert total_ticks == 55
