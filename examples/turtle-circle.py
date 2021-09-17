#!/usr/bin/env python

from netsblox.turtle import *
import time

@turtle
class MyTurtle(TurtleBase):
    @onstart
    def start(self):
        self.drawing = True

        sides = 200
        ang = 360 / sides
        for _ in range(sides):
            self.forward(3)
            self.turn_left(ang)

        self.visible = False
        time.sleep(2) # give time to appreciate the artwork
        stop_project()

MyTurtle()
start_project()
