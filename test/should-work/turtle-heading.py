#!/usr/bin/env python

from netsblox.turtle import *
import sys

steps = 100

@turtle
class MyTurtle:
    @onstart
    def start(self):
        pos_set = set()
        self.radians()
        for _ in range(steps):
            pos_set.add(self.heading())
            self.left(1)
        if len(pos_set) != steps:
            print(f'got {len(pos_set)} steps - expected {steps}', file = sys.stderr)
            assert False
        if 0 in pos_set:
            print('0 should not be possible', file = sys.stderr)
            assert False

MyTurtle()
run_turtles()
