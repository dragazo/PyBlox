#!/usr/bin/env python

import netsblox
import time

client = netsblox.Client()
signal = netsblox.concurrency.StepSignal()
count = 0

@client.on_message('button')
def on_button():
    global count
    time.sleep(1)
    count += 1
    signal.step()

for i in range(5):
    client.send_message('button')
    signal.wait()
assert count == 5
