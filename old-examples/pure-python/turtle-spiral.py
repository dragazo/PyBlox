#!/usr/bin/env python

from netsblox.graphical import *

@sprite
class MySprite(SpriteBase):
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

num_sprites = 50
for i in range(num_sprites):
    MySprite(i * 360 / num_sprites)
start_project()
