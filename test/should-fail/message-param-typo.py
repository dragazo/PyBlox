#!/usr/bin/env python

import netsblox
import time

client = netsblox.Client()

def foo(msgg):
    print(msgg)
client.on_message('message', foo)

client.send_message('message', msg='hello')
time.sleep(0.5)
