#!/usr/bin/env python

from netsblox.turtle import *

@turtle
class MyTurtle(TurtleBase):
    def __init__(self, start_angle):
        self.heading = start_angle
        self.drawing = True

    @onstart
    def start(self):
        d = 10
        while d >= 1:
            self.forward(d)
            self.turn_left(5)
            d *= 0.995

        self.visible = False

num_turtles = 50
for i in range(num_turtles):
    MyTurtle(i * 360 / num_turtles)
start_project()
