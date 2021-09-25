#!/usr/bin/env python

from netsblox.turtle import *

@turtle
class MyTurtle(TurtleBase):
    def __init__(self, x, y):
        self.pos = (x * 50, y * 50)
    
    @onkey('w', 'up')
    def press_forward(self):
        self.forward(10)

    @onkey('a', 'left')
    def press_left(self):
        self.turn_left(15)

    @onkey('d', 'right')
    def press_right(self):
        self.turn_right(15)

@onkey('space')
def press_space():
    stop_project()

for x in range(-5, 5 + 1):
    for y in range(-5, 5 + 1):
        MyTurtle(x, y)
start_project()
