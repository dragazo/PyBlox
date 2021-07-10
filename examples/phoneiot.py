#!/usr/bin/env python

import netsblox

client = netsblox.Client(run_forever = True)
phoneiot = client.get_service('PhoneIoT')

printing = False
def start(**extra):
    global printing
    printing = True
def stop(**extra):
    global printing
    printing = False
client.on_message('start', start)
client.on_message('stop', stop)

def accel_handler(x, y, z, **extra):
    if printing:
        print(f'accel: {x:.1f} {y:.1f} {z:.1f}')

client.on_message('accelerometer', accel_handler)

device = input('device id: ')
phoneiot.set_credentials(device, input('password: '))

phoneiot.listen_to_sensors(device, { 'accelerometer': 500 })

green = phoneiot.get_color(14, 138, 26)
red = phoneiot.get_color(219, 13, 13)

phoneiot.clear_controls(device)
phoneiot.listen_to_gui(device)
phoneiot.add_button(device, 16.666, 5, 66.666, 42.5, 'start', { 'event': 'start', 'fontSize': 3, 'style': 'circle', 'color': green })
phoneiot.add_button(device, 16.666, 50, 66.666, 42.5, 'stop', { 'event': 'stop', 'fontSize': 3, 'style': 'circle', 'color': red })
