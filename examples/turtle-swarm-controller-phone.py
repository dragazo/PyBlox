#!/usr/bin/env python

import netsblox
from netsblox.turtle import *

client = netsblox.Client()
phoneiot = client.phone_iot

device = input('phone id: ')
phoneiot.set_credentials(device, input('password: '))

phoneiot.clear_controls(device)

phoneiot.add_button(device, 5, 5, 25, 25, '<', { 'event': 'leftbtn' })
phoneiot.add_button(device, 35, 5, 25, 25, '^', { 'event': 'forwardbtn' })
phoneiot.add_button(device, 65, 5, 25, 25, '>', { 'event': 'rightbtn' })

phoneiot.add_button(device, 5, 50, 25, 25, '<', { 'event': 'leftbtn2' })
phoneiot.add_button(device, 35, 50, 25, 25, '^', { 'event': 'forwardbtn2' })
phoneiot.add_button(device, 65, 50, 25, 25, '>', { 'event': 'rightbtn2' })

phoneiot.listen_to_gui(device)

@turtle
class MyTurtle(TurtleBase):
    def __init__(self, x, y):
        self.pos = (x * 50, y * 50)

    @client.on_message('forwardbtn')
    @client.on_message('forwardbtn2')
    @onkey('w')
    @onkey('Up')
    def press_forward(self):
        self.forward(10)

    @client.on_message('leftbtn')
    @client.on_message('leftbtn2')
    @onkey('a')
    @onkey('Left')
    def press_left(self):
        self.turn_left(15)

    @client.on_message('rightbtn')
    @client.on_message('rightbtn2')
    @onkey('d')
    @onkey('Right')
    def press_right(self):
        self.turn_right(15)

@onkey('space')
def press_space():
    stop_project()

for x in range(-5, 5 + 1):
    for y in range(-5, 5 + 1):
        MyTurtle(x, y)
start_project()
