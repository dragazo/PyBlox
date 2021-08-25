#!/usr/bin/env python

from netsblox.turtle import *
import random

@turtle
class MyTurtle:
    def __init__(self, rot, dist):
        self.rot = rot
        self.dist = dist

    @onstart
    def start(self):
        self.left(random.random() * 360)
        while True:
            self.left((random.random() - 0.5) * 2 * self.rot)
            self.forward(self.dist)

turtles = [MyTurtle(50, 5) for _ in range(100)]

start_project()
