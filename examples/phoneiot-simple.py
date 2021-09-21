#!/usr/bin/env python

import netsblox
nb = netsblox.Client() # create a new connection to NetsBlox

@nb.on_message('accelerometer') # equivalent of "When I Receive" block
def accel_handler(x, y, z):
    print(f'accel: {x:.1f} {y:.1f} {z:.1f}')

device = input('device id: ')
password = input('password: ')
nb.phone_iot.set_credentials(device, password)

# listen for accelerometer updates (messages) every 500ms
nb.phone_iot.listen_to_sensors(device, { 'accelerometer': 500 })

nb.wait_till_disconnect() # run until manually stopped by user
