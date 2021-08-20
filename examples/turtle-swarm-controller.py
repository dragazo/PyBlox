#!/usr/bin/env python

from netsblox.turtle import *

@turtle
class MyTurtle:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @onstart
    def start(self):
        self.goto(self.x * 50, self.y * 50)
    
    @onkey('w')
    @onkey('Up')
    def press_forward(self):
        self.forward(10)

    @onkey('a')
    @onkey('Left')
    def press_left(self):
        self.left(15)

    @onkey('d')
    @onkey('Right')
    def press_right(self):
        self.right(15)

@onkey('space')
def press_space():
    stop_game()

for x in range(-5, 5 + 1):
    for y in range(-5, 5 + 1):
        MyTurtle(x, y)
run_game()
