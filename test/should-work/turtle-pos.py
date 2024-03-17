#!/usr/bin/env python

from netsblox.graphical import *
import sys

steps = 100

@sprite
class MySprite:
    @onstart()
    def start(self):
        pos_set = set()
        for _ in range(steps):
            self.forward(5)
            pos_set.add(self.pos)
        if len(pos_set) != steps:
            print(f'got {len(pos_set)} steps - expected {steps}', file = sys.stderr)
            assert False
        if (0, 0) in pos_set:
            print('(0, 0) should not be possible', file = sys.stderr)
            assert False
        stop_project()

MySprite()
start_project()
