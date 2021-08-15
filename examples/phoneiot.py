#!/usr/bin/env python

import netsblox

client = netsblox.Client() # create a new connection to NetsBlox
phone_iot = client.phone_iot # we can alias services for convenience

printing = False
@client.on_message('start')
def start():
    global printing
    printing = True
@client.on_message('stop')
def stop():
    global printing
    printing = False

@client.on_message('accelerometer')
def accel_handler(x, y, z):
    if printing:
        print(f'accel: {x:.1f} {y:.1f} {z:.1f}')

device = input('device id: ')
phone_iot.set_credentials(device, input('password: '))

phone_iot.listen_to_sensors(device, { 'accelerometer': 500 })

green = phone_iot.get_color(14, 138, 26)
red = phone_iot.get_color(219, 13, 13)
black = phone_iot.get_color(0, 0, 0)
white = phone_iot.get_color(255, 255, 255)

phone_iot.clear_controls(device)
phone_iot.listen_to_gui(device)
phone_iot.add_button(device, 30, 5, 40, 40, 'start', { 'event': 'start', 'fontSize': 3, 'style': 'circle', 'color': green })
phone_iot.add_button(device, 30, 40, 40, 40, 'stop', { 'event': 'stop', 'fontSize': 3, 'style': 'circle', 'color': red })
phone_iot.add_button(device, 12.5, 75, 75, 20, 'terminate', { 'event': 'terminate', 'fontSize': 3, 'style': 'ellipse', 'color': black, 'textColor': white })

client.wait_for_message('terminate') # wait till the terinate button sends us a message
