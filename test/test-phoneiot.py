#!/usr/bin/env python

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from pyblox import pyblox

client = pyblox.Client(run_forever = True)
phoneiot = client.get_service('PhoneIoT')

def accel_handler(x, y, z, **extra):
    print(f'accel: {x:.1f} {y:.1f} {z:.1f}')

client.on_message('accelerometer', accel_handler)

device = '02730a82c99f'
phoneiot.set_credentials(device, '0')
phoneiot.listen_to_sensors(device, [['accelerometer', 500]])
