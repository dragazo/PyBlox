#!/usr/bin/env python

import netsblox
import time

client = netsblox.Editor()
count = 0

@client.on_message('button')
def on_button():
    global count
    time.sleep(1)
    count += 1
    client.signal()

for i in range(5):
    client.reset_signal()
    client.send_message('button')
    client.wait_for_signal()
assert count == 5
