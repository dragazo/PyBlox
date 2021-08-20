#!/usr/bin/env python

from netsblox.turtle import *
import netsblox
import time
import math

client = netsblox.Client() # create a new connection to NetsBlox
phone_iot = client.phone_iot # we can alias services for convenience

green = phone_iot.get_color(14, 138, 26)
black = phone_iot.get_color(0, 0, 0)
white = phone_iot.get_color(255, 255, 255)

device = input('device id: ')
phone_iot.set_credentials(device, input('password: '))

phone_iot.clear_controls(device)
phone_iot.add_button(device, 30, 5, 40, 40, 'reset', { 'event': 'reset', 'fontSize': 3, 'style': 'circle', 'color': green })
phone_iot.add_button(device, 15, 40, 70, 20, 'terminate', { 'event': 'terminate', 'fontSize': 3, 'style': 'ellipse', 'color': black, 'textColor': white })

phone_iot.listen_to_gui(device)
phone_iot.listen_to_sensors(device, { 'accelerometer': 100 })

@turtle
class MyTurtle:
    @onstart
    def start(self):
        self.radians() # math.atan2() returns radians, so switch to radians mode
        self.pendown()

        self.velx = 0
        self.vely = 0
        while True:
            time.sleep(0.05)
            x, y = self.pos()
            self.setheading(math.atan2(self.velx, self.vely))
            self.setpos(x + self.velx, y + self.vely)

    @client.on_message('accelerometer')
    def accel_handler(self, x, y):
        self.velx -= x * 0.1
        self.vely -= y * 0.1

    @client.on_message('reset')
    def reset(self):
        self.velx = 0
        self.vely = 0
        self.setpos(0, 0)
        self.clear()

@client.on_message('terminate')
def terminate():
    stop_game()

MyTurtle()
run_game()
