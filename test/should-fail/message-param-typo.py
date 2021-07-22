#!/usr/bin/env python

import netsblox
import time

editor = netsblox.Editor()

def foo(msgg):
    print(msgg)
editor.on_message('message', foo)

editor.send_message('message', msg='hello')
time.sleep(0.5)
