#!/usr/bin/env python

import turtle as _turtle
import threading
import inspect
import queue
import math

_action_queue = queue.Queue(4)

def run_turtles():
    while not _action_queue.empty():
        fn, args = _action_queue.get()
        fn(*args)

    _turtle.Screen().ontimer(run_turtles, 33)

def _qinvoke(fn, *args):
    _action_queue.put((fn, args))

class Turtle:
    def __init__(self):
        self.__turtle = _turtle.Turtle()
        self.__turtle.speed('fastest')
        self.__x = 0.0
        self.__y = 0.0
        self.__rot = 0.25 # angle [0, 1)
        self.__degrees = 360.0

    def goto(self, x, y = None):
        if y is None:
            x, y = y
        self.__x = float(x)
        self.__y = float(y)
        _qinvoke(self.__turtle.goto, self.__x, self.__y)
    setposition = goto
    setpos = goto

    def setheading(self, to_angle):
        self.__rot = (float(to_angle) / self.__degrees) % 1.0
        _qinvoke(self.__turtle.setheading, self.__rot * 360.0) # raw turtle is always in degrees mode
    seth = setheading

    def setx(self, x):
        self.goto(float(x), self.__y)
    def sety(self, y):
        self.goto(self.__x, float(y))

    def forward(self, distance):
        distance = float(distance)
        h = self.__rot * 2 * math.pi
        self.goto(self.__x + math.sin(h) * distance, self.__y + math.cos(h) * distance)
    fd = forward

    def back(self, distance):
        self.forward(-float(distance))
    backward = back
    bk = back

    def left(self, angle):
        self.setheading(self.heading() - float(angle))
    lt = left

    def right(self, angle):
        self.setheading(self.heading() + float(angle))
    rt = right

    def home(self):
        self.setpos(0, 0)
        self.setheading(0)
    
    def dot(self, radius = None, *color):
        _qinvoke(self.__turtle.dot, radius, *color)

    def stamp(self):
        _qinvoke(self.__turtle.stamp)

    def clearstamps(self, n = None):
        _qinvoke(self.__turtle.clearstamps, n)

    def clear(self):
        _qinvoke(self.__turtle.clear)

    def write(self, arg, move = False, align = 'left', font = ('Arial', 8, 'normal')):
        _qinvoke(self.__turtle.write, arg, move, align, font)

    def showturtle(self):
        _qinvoke(self.__turtle.showturtle)
    st = showturtle

    def hideturtle(self):
        _qinvoke(self.__turtle.hideturtle)
    ht = hideturtle

    def isvisible(self):
        return self.__turtle.isvisible()

    def position(self):
        return self.__x, self.__y
    pos = position

    def towards(self, x, y = None):
        return self.__turtle.towards(x, y)
    
    def xcor(self):
        return self.__x
    
    def ycor(self):
        return self.__y
    
    def heading(self):
        return self.__rot * self.__degrees
    
    def distance(self, x, y = None):
        return self.__turtle.distance(x, y)

    def degrees(self, fullcircle = 360.0):
        self.__degrees = float(fullcircle)
    
    def radians(self):
        self.__degrees = 2 * math.pi

    def pendown(self):
        self.__turtle.pendown()
    down = pendown
    pd = pendown

    def penup(self):
        self.__turtle.penup()
    up = penup
    pu = penup

    def pensize(self, width=None):
        return self.__turtle.pensize(width)
    width = pensize

    def pen(self, pen = None, **pendict):
        return self.__turtle.pen(pen, **pendict)

    def isdown(self):
        return self.__turtle.isdown()

def turtle(cls):
    class Derived(Turtle, cls):
        def __init__(self, *args, **kwargs):
            Turtle.__init__(self)
            cls.__init__(self, *args, **kwargs)

            start_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                thread = threading.Thread(target = start_script)
                thread.setDaemon(True)
                thread.start()
    return Derived

def onstart(f):
    setattr(f, '__run_on_start', True)
    return f
