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
phoneiot.listen_to_gui(device)

@turtle
class MyTurtle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    @onstart
    def start(self):
        self.goto(self.x * 50, self.y * 50)
    
    @client.on_message('forwardbtn')
    def press_forward(self):
        self.forward(10)
    @client.on_message('leftbtn')
    def press_left(self):
        self.left(15)
    @client.on_message('rightbtn')
    def press_right(self):
        self.right(15)
    
for x in range(-5, 5 + 1):
    for y in range(-5, 5 + 1):
        MyTurtle(x, y)
run_game()
