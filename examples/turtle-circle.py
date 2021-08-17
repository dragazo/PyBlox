#!/usr/bin/env python

from netsblox.turtle import *
import time

@turtle
class MyTurtle:
    @onstart
    def start(self):
        self.pendown()

        sides = 200
        ang = 360 / sides
        for _ in range(sides):
            self.forward(3)
            self.left(ang)
        
        self.hideturtle()
        time.sleep(2) # give time to appreciate the artwork
        stop_game()

MyTurtle()
run_game()
