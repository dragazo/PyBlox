#!/usr/bin/env python

import turtle as _turtle
import threading
import inspect
import queue
import math

_key_events = {} # maps key to [raw handler, event[]]
def _add_key_event(key, event):
    if key not in _key_events:
        entry = [None, []]
        def raw_handler():
            for handler in entry[1]:
                t = threading.Thread(target = handler)
                t.setDaemon(True)
                t.start()
        entry[0] = raw_handler

        _key_events[key] = entry
        _turtle.onkeypress(entry[0], key)

    _key_events[key][1].append(event)

class GameStateError(Exception):
    pass

_action_queue = queue.Queue(1) # max size is equal to max total exec imbalance, so keep it low
_action_queue_interval = 16 # ms between control slices
_action_max_per_slice = 16 # max number of actions to perform during a control slice
_game_running = False
_game_stopped = False # different than not running due to 3-state system

# filling up the queue before we start can help mitigate total starting exec imbalance by up to maxsize steps
# effective max starting error decreases by 1, so if max size is 1, this is perfect
for i in range(_action_queue.maxsize):
    _action_queue.put((lambda *_: None, tuple()))

def _process_queue():
    if _game_running:
        for _ in range(_action_max_per_slice):
            if _action_queue.qsize() == 0:
                break
            fn, args = _action_queue.get()
            fn(*args)

        _turtle.Screen().ontimer(_process_queue, _action_queue_interval)

def run_game():
    '''
    Run turtle game logic.
    Turtles begin running as soon as they are created,
    but you must call this function for them to start moving around and interacting.
    This must be called from the main thread (global scope), not from within a turtle.

    The game can manually be stopped by calling stop_game() (e.g., from a turtle).

    Trying to start a game that is already running results in a GameStateError.
    '''
    global _game_running, _game_stopped
    if _game_running:
        raise GameStateError('run_game() was called when the game was already running')
    if _game_stopped:
        raise GameStateError('run_game() was called when the game had previously been stopped')
    _game_running = True

    _turtle.delay(0)
    _turtle.listen()
    _turtle.Screen().ontimer(_process_queue, _action_queue_interval)
    _turtle.done()

def stop_game():
    '''
    Stops a game that was previously started by run_game().

    Multiple calls to stop_game() are allowed.
    '''
    global _game_running, _game_stopped
    _game_running = False
    _game_stopped = True

    _turtle.Screen().ontimer(_turtle.bye, 1000)

def _qinvoke(fn, *args):
    if not _game_stopped:
        _action_queue.put((fn, args))

class TurtleBase:
    '''
    The base class for any custom turtle.
    This type should not be used directly; instead, you should create a custom turtle with the @turtle decorator.

    ```
    @turtle
    class MyTurtle:
        @onstart
        def start(self):
            self.forward(75)

    t = MyTurtle() # create an instance of MyTurtle - start() is executed automatically
    ```
    '''
    def __init__(self):
        self.__turtle = _turtle.Turtle()
        self.__turtle.speed('fastest')
        self.__turtle.penup()
        self.__drawing = False
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
        _qinvoke(self.__turtle.setheading, (0.25 - self.__rot) % 1.0 * 360.0) # raw turtle is always in degrees mode
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
    show = showturtle
    st = showturtle

    def hideturtle(self):
        _qinvoke(self.__turtle.hideturtle)
    hide = hideturtle
    ht = hideturtle

    def isvisible(self):
        return self.__turtle.isvisible()

    def pendown(self):
        self.__drawing = True
        _qinvoke(self.__turtle.pendown)
    down = pendown
    pd = pendown

    def penup(self):
        self.__drawing = False
        _qinvoke(self.__turtle.penup)
    up = penup
    pu = penup

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

    def pensize(self, width=None):
        return self.__turtle.pensize(width)
    width = pensize

    def pen(self, pen = None, **pendict):
        return self.__turtle.pen(pen, **pendict)

    def isdown(self):
        return self.__drawing

def turtle(cls):
    '''
    The `@turtle` decorator for a class creates a new type of turtle.
    You can use the `@onstart` annotation on any method definition to make it run when a turtle of this type is created.

    ```
    @turtle
    class MyTurtle:
        @onstart
        def start(self):
            self.forward(75)

    t = MyTurtle() # create an instance of MyTurtle - start() is executed automatically
    ```
    '''
    class Derived(TurtleBase, cls):
        def __init__(self, *args, **kwargs):
            TurtleBase.__init__(self)
            cls.__init__(self, *args, **kwargs)

            start_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                thread = threading.Thread(target = start_script)
                thread.setDaemon(True)
                thread.start()

            key_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_key'))
            for _, key_script in key_scripts:
                _add_key_event(getattr(key_script, '__run_on_key'), key_script)
    
    return Derived

def onstart(f):
    '''
    The `@onstart` decorator can be applied to a method definition inside a custom turtle
    to make that function run whenever an instance of the custom turtle type is created.

    ```
    @turtle
    class MyTurtle:
        @onstart
        def start(self):
            self.forward(75)

    t = MyTurtle() # create an instance of MyTurtle - start() is executed automatically
    ```
    '''
    setattr(f, '__run_on_start', True)
    return f

def onkey(key):
    '''
    The `@onkey` decorator can be applied to a method definition inside a custom turtle
    to make that function run whenever the user presses a key on the keyboard.

    ```
    @turtle
    class MyTurtle:
        @onkey('w')
        def w_key_pressed(self):
            self.forward(50)
    ```
    '''
    def wrapper(f):
        setattr(f, '__run_on_key', key)
        return f
    return wrapper
