#!/usr/bin/env python

import turtle as _turtle
import threading
import inspect
import queue
import math
from typing import Any, Union

from PIL import Image, ImageTk

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

_action_queue_thread_id = threading.get_ident()

_action_queue_ret_cv = threading.Condition(threading.Lock())
_action_queue_ret_id = 0
_action_queue_ret_vals = {}

_action_queue = queue.Queue(1) # max size is equal to max total exec imbalance, so keep it low
_action_queue_interval = 16    # ms between control slices
_action_max_per_slice = 16     # max number of actions to perform during a control slice

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
            val = _action_queue.get()
            if len(val) == 2:
                val[0](*val[1])
            else:
                ret = None
                try:
                    ret = val[0](*val[1])
                except Exception as e:
                    ret = e

                with _action_queue_ret_cv:
                    _action_queue_ret_vals[val[2]] = ret
                    _action_queue_ret_cv.notify_all()

        _turtle.Screen().ontimer(_process_queue, _action_queue_interval)

# this should only be used internally, not by user code
def _new_game():
    global _game_running, _game_stopped
    _game_running = False
    _game_stopped = False

def start_project():
    '''
    Run turtle game logic.
    Turtles begin running as soon as they are created,
    but you must call this function for them to start moving around and interacting.
    This must be called from the main thread (global scope), not from within a turtle.

    The game can manually be stopped by calling stop_project() (e.g., from a turtle).

    Trying to start a game that is already running results in a GameStateError.
    '''
    global _game_running, _game_stopped
    if _game_running:
        raise GameStateError('start_project() was called when the game was already running')
    if _game_stopped:
        raise GameStateError('start_project() was called when the game had previously been stopped')
    _game_running = True

    _turtle.delay(0)
    _turtle.listen()
    _turtle.Screen().ontimer(_process_queue, _action_queue_interval)
    _turtle.done()

def stop_project():
    '''
    Stops a game that was previously started by start_project().

    Multiple calls to stop_project() are allowed.
    '''
    global _game_running, _game_stopped
    if _game_running:
        _game_running = False
        _game_stopped = True

        _turtle.Screen().ontimer(_turtle.bye, 1000)

def _qinvoke(fn, *args) -> None:
    # if we're running on the action queue thread, we can just do it directly
    if _action_queue_thread_id == threading.current_thread().ident:
        fn(*args)
        return

    if not _game_stopped:
        _action_queue.put((fn, args))

def _qinvoke_wait(fn, *args) -> Any:
    global _action_queue_ret_id

    # if we're running on the action queue thread, we can just do it directly
    if _action_queue_thread_id == threading.current_thread().ident:
        return fn(*args)

    ret_id = None
    with _action_queue_ret_cv:
        ret_id = _action_queue_ret_id
        _action_queue_ret_id += 1

    ret_val = None
    _action_queue.put((fn, args, ret_id))
    while True:
        with _action_queue_ret_cv:
            if id in _action_queue_ret_vals:
                ret_val = _action_queue_ret_vals[id]
                del _action_queue_ret_vals[id]
                break
            _action_queue_ret_cv.wait()

    if isinstance(ret_val, Exception):
        raise ret_val
    return ret_val

class _ImgWrapper:
    _type = 'image'
    def __init__(self, img):
        self._data = ImageTk.PhotoImage(img)

_blank_img = Image.new('RGBA', (10, 10))
def _setcostume(t, tid, costume: Union[None, str, Any]):
    def batcher():
        if costume is not None:
            name = f'custom-costume-{tid}'
            _turtle.register_shape(name, costume if type(costume) == str else _ImgWrapper(costume))
            t.shape(name)
        else:
            _turtle.register_shape('blank', _ImgWrapper(_blank_img))
            t.shape('blank')
    return _qinvoke(batcher)

# if set to non-none, will use RawTurtle with this as its TurtleScreen parent
_raw_turtle_target = None
_turtle_count = 0
def _make_turtle(extra_fn = None):
    def batcher():
        global _turtle_count
        id = _turtle_count
        _turtle_count += 1

        t = _turtle.Turtle() if _raw_turtle_target is None else _turtle.RawTurtle(_raw_turtle_target)
        t.speed('fastest')
        t.penup()

        if extra_fn is not None:
            extra_fn(t, id)

        return t, id
    return _qinvoke_wait(batcher)

class StageBase:
    '''
    The base class for any custom stage.
    This type should not be used directly; instead, you should create a custom stage with the @stage decorator.

    ```
    @stage
    class MyStage:
        @onstart
        def start(self):
            pass

    stage = MyStage() # create an instance of MyStage - start() is executed automatically
    ```
    '''
    def __init__(self):
        self.__turtle, self.__id = _make_turtle(lambda t, id: _setcostume(t, id, None)) # default to blank costume

    def setcostume(self, costume):
        _setcostume(self.__turtle, self.__id, costume)

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
        self.__turtle, self.__id = _make_turtle()
        self.__drawing = False # turtles default to pendown
        self.__x = 0.0
        self.__y = 0.0
        self.__rot = 0.25 # angle [0, 1)
        self.__degrees = 360.0

    def setcostume(self, costume):
        _setcostume(self.__turtle, self.__id, costume)

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

def _derive(bases, cls):
    class Derived(*bases, cls):
        def __init__(self, *args, **kwargs):
            for base in bases:
                base.__init__(self)
            cls.__init__(self, *args, **kwargs)

            start_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                thread = threading.Thread(target = start_script)
                thread.setDaemon(True)
                thread.start()

            key_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_key'))
            for _, key_script in key_scripts:
                for key in getattr(key_script, '__run_on_key'):
                    _add_key_event(key, key_script)

            msg_scripts = inspect.getmembers(self, predicate = lambda x: inspect.ismethod(x) and hasattr(x, '__run_on_message'))
            for _, msg_script in msg_scripts:
                for inserter in getattr(msg_script, '__run_on_message'): # client gave us a list of convenient insertion functions
                    inserter(msg_script)
    
    return Derived

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
    return _derive([TurtleBase], cls)

def stage(cls):
    '''
    The `@stage` decorator for a class creates a new type of stage.
    Stages function much like the stage in NetsBlox - equivalent to a sprite/turtle except with no movement controls.
    Unlike in NetsBlox, you may create multiple instances of a stage, or even multiple types of stages.

    ```
    @stage
    class MyStage:
        @onstart
        def start(self):
            print('stage starting')
    ```
    '''
    return _derive([StageBase], cls)

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
    The `@onkey` decorator can be applied to a function at global scope
    or to a method definition inside a custom turtle
    to make that function run whenever the user presses a key on the keyboard.

    ```
    @onkey('space')
    def space_key_pressed():
        stop_project()

    @turtle
    class MyTurtle:
        @onkey('w')
        def w_key_pressed(self):
            self.forward(50)
    ```
    '''
    def wrapper(f):
        info = inspect.getfullargspec(f)
        if len(info.args) != 0 and info.args[0] == 'self':
            if not hasattr(f, '__run_on_key'):
                setattr(f, '__run_on_key', [])
            getattr(f, '__run_on_key').append(key)
        else:
            _add_key_event(key, f)

        return f
        
    return wrapper
