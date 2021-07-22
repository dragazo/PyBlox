#!/usr/bin/env python

import netsblox

editor = netsblox.Editor(run_forever = True)
phone_iot = editor.phone_iot

printing = False
@editor.on_message('start')
def start():
    global printing
    printing = True
@editor.on_message('stop')
def stop():
    global printing
    printing = False

@editor.on_message('accelerometer')
def accel_handler(x, y, z):
    if printing:
        print(f'accel: {x:.1f} {y:.1f} {z:.1f}')

device = input('device id: ')
phone_iot.set_credentials(device, input('password: '))

phone_iot.listen_to_sensors(device, { 'accelerometer': 500 })

green = phone_iot.get_color(14, 138, 26)
red = phone_iot.get_color(219, 13, 13)

phone_iot.clear_controls(device)
phone_iot.listen_to_gui(device)
phone_iot.add_button(device, 16.666, 5, 66.666, 42.5, 'start', { 'event': 'start', 'fontSize': 3, 'style': 'circle', 'color': green })
phone_iot.add_button(device, 16.666, 50, 66.666, 42.5, 'stop', { 'event': 'stop', 'fontSize': 3, 'style': 'circle', 'color': red })
