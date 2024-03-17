#!/usr/bin/env python

import netsblox
import time

editor = netsblox.Client()

@editor.on_message('message')
def foo(msgg):
    print(msgg)

editor.send_message('message', msg='hello')
time.sleep(0.5)
