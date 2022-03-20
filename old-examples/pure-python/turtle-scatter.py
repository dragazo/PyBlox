#!/usr/bin/env python

from netsblox.turtle import *
import random

@turtle
class MyTurtle(TurtleBase):
    def __init__(self, rot, dist):
        self.rot = rot
        self.dist = dist
        self.drawing = True

    @onstart
    def start(self):
        self.turn_left(random.random() * 360)
        while True:
            self.turn_left((random.random() - 0.5) * 2 * self.rot)
            self.forward(self.dist)

            if random.random() < 0.1:
                self.pen_size = random.random()**2 * 5

            if random.random() < 0.01:
                self.clear()

turtles = [MyTurtle(50, 5) for _ in range(100)]

start_project()
