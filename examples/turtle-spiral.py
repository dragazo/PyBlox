#!/usr/bin/env python

from netsblox.turtle import *

@turtle
class MyTurtle:
    def __init__(self, start_angle):
        self.start_angle = start_angle

    @onstart
    def start(self):
        self.setheading(self.start_angle)
        self.pendown()

        d = 10
        while d >= 1:
            self.forward(d)
            self.left(5)
            d *= 0.995
        
        self.hide()

num_turtles = 50
for i in range(num_turtles):
    MyTurtle(i * 360 / num_turtles)
start_project()
