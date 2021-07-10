#!/usr/bin/env python

import netsblox
import time

client = netsblox.Client()

def foo(x, y):
    print(x, y)
client.on_message('vec', foo)

client.send_message('vec', x=1, y=2, z=3)
time.sleep(0.5)
