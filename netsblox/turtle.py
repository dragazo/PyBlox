#!/usr/bin/env python

import turtle as _turtle
import threading
import inspect
import queue

_action_queue = queue.Queue(4)

def start_sim():
    while not _action_queue.empty():
        fn, args = _action_queue.get()
        fn(*args)

    turtle.Screen().ontimer(start_sim, 33)

def _qinvoke(fn, *args):
    _action_queue.put((fn, args))

class Turtle:
    def __init__(self):
        self.__turtle = _turtle.Turtle()
        self.__turtle.speed('fastest')

    def goto(self, x, y = None):
        _qinvoke(self.__turtle.goto, x, y)
    setposition = goto
    setpos = goto

    def setx(self, x):
        _qinvoke(self.__turtle.setx, x)
    def sety(self, y):
        _qinvoke(self.__turtle.sety, y)

    def forward(self, distance):
        _qinvoke(self.__turtle.forward, distance)
    fd = forward

    def back(self, distance):
        _qinvoke(self.__turtle.back, distance)
    backward = back
    bk = back

    def setheading(self, to_angle):
        _qinvoke(self.__turtle.setheading, to_angle)
    seth = setheading

    def right(self, angle):
        _qinvoke(self.__turtle.right, angle)
    rt = right

    def left(self, angle):
        _qinvoke(self.__turtle.left, angle)
    lt = left

    def home(self):
        _qinvoke(self.__turtle.home)
    
    def reset(self):
        _qinvoke(self.__turtle.reset)

    def circle(self, radius, extent = None, steps = None):
        _qinvoke(self.__turtle.circle, radius, extent, steps)
    
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
        return self.__turtle.position()
    pos = position

    def towards(self, x, y = None):
        return self.__turtle.towards(x, y)
    
    def xcor(self):
        return self.__turtle.xcor()
    
    def ycor(self):
        return self.__turtle.ycor()
    
    def heading(self):
        return self.__turtle.heading()
    
    def distance(self, x, y = None):
        return self.__turtle.distance(x, y)

    def degrees(self, fullcircle = 360.0):
        self.__turtle.degrees(fullcircle)
    
    def radians(self):
        self.__turtle.radians()

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
