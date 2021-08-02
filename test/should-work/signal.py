#!/usr/bin/env python

import netsblox
import time

client = netsblox.Editor()
signal = netsblox.Signal()
count = 0

@client.on_message('button')
def on_button():
    global count
    time.sleep(1)
    count += 1
    signal.send()

for i in range(5):
    signal.clear()
    client.send_message('button')
    signal.wait()
assert count == 5
