#!/usr/bin/env python

import builtins as _builtins

import turtle as _turtle
import threading as _threading
import inspect as _inspect
import queue as _queue
import math as _math

import netsblox.common as _common
import netsblox.events as _events

from typing import Any, Union, Tuple, Iterable

from PIL import Image, ImageTk

_key_events = {} # maps key to [raw handler, _EventWrapper[]]
def _add_key_event(key, event):
    if key not in _key_events:
        entry = [None, []]
        def raw_handler():
            handlers = entry[1] if key is None or None not in _key_events else entry[1] + _key_events[None][1]
            for handler in handlers:
                handler.schedule()
        entry[0] = raw_handler

        _key_events[key] = entry
        _turtle.onkeypress(entry[0], key)

    _key_events[key][1].append(_events.get_event_wrapper(event))

_click_events = {} # maps key to [raw handler, event[]]
def _add_click_event(key, event):
    if key not in _click_events:
        entry = [None, []]
        def raw_handler(x, y):
            for handler in entry[1]:
                handler.schedule(x, y)
        entry[0] = raw_handler

        _click_events[key] = entry
        _turtle.onscreenclick(entry[0], key)

    _click_events[key][1].append(_events.get_event_wrapper(event))

class GameStateError(Exception):
    pass

_action_queue_thread_id = _threading.get_ident()

_action_queue_ret_cv = _threading.Condition(_threading.Lock())
_action_queue_ret_id = 0
_action_queue_ret_vals = {}

_action_queue = _queue.Queue(1) # max size is equal to max total exec imbalance, so keep it low
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
    if _action_queue_thread_id == _threading.current_thread().ident:
        fn(*args)
        return

    if not _game_stopped:
        _action_queue.put((fn, args))

def _qinvoke_wait(fn, *args) -> Any:
    global _action_queue_ret_id

    # if we're running on the action queue thread, we can just do it directly
    if _action_queue_thread_id == _threading.current_thread().ident:
        return fn(*args)

    ret_id = None
    with _action_queue_ret_cv:
        ret_id = _action_queue_ret_id
        _action_queue_ret_id += 1

    ret_val = None
    _action_queue.put((fn, args, ret_id))
    while True:
        with _action_queue_ret_cv:
            if ret_id in _action_queue_ret_vals:
                ret_val = _action_queue_ret_vals[ret_id]
                del _action_queue_ret_vals[ret_id]
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
        tid = _turtle_count
        _turtle_count += 1

        t = _turtle.Turtle() if _raw_turtle_target is None else _turtle.RawTurtle(_raw_turtle_target)
        t.speed('fastest')
        t.penup()

        if extra_fn is not None:
            extra_fn(t, tid)

        return t, tid
    return _qinvoke_wait(batcher)

class StageBase:
    '''
    The base class for any custom stage.
    Custom stages should use this as their base class, and additionally use the `@stage` decorator.

    ```
    @stage
    class MyStage(StageBase):
        @onstart
        def start(self):
            pass

    stage = MyStage() # create an instance of MyStage - start() is executed automatically
    ```
    '''
    def __init__(self):
        try:
            if self.__initialized:
                return # don't initialize twice (can happen from mixing @stage decorator and explicit StageBase base class)
        except:
            self.__initialized = True

        self.__turtle, self.__tid = _make_turtle(lambda t, tid: _setcostume(t, tid, None)) # default to blank costume
        self.__costume = None

    @property
    def costume(self) -> Any:
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Any) -> None:
        '''
        Get or set the current stage costume (background).

        ```
        self.costume = img
        ```
        '''
        _setcostume(self.__turtle, self.__tid, new_costume)
        self.__costume = new_costume

    @property
    def size(self) -> Tuple[float, float]:
        '''
        Get the size of the stage (width, height) in pixels.

        ```
        width, height = self.size
        ```
        '''
        def batcher():
            return _turtle.window_width(), _turtle.window_height()
        return _qinvoke_wait(batcher)

    @property
    def width(self) -> float:
        '''
        Get the width of the stage in pixels.

        ```
        print('width:', self.width)
        ```
        '''
        return _qinvoke_wait(_turtle.window_width)

    @property
    def height(self) -> float:
        '''
        Get the height of the stage in pixels.

        ```
        print('height:', self.height)
        ```
        '''
        return _qinvoke_wait(_turtle.window_height)

class TurtleBase:
    '''
    The base class for any custom turtle.
    Custom turtles should use this as their base class, and additionally use the `@turtle` decorator.

    ```
    @turtle
    class MyTurtle(TurtleBase):
        @onstart
        def start(self):
            self.forward(75)

    t = MyTurtle() # create an instance of MyTurtle - start() is executed automatically
    ```
    '''
    def __init__(self):
        try:
            if self.__initialized:
                return # don't initialize twice (can happen from mixing @turtle decorator and explicit TurtleBase base class)
        except:
            self.__initialized = True

        self.__turtle, self.__tid = _make_turtle()
        self.__drawing = False
        self.__visible = True
        self.__x = 0.0
        self.__y = 0.0
        self.__rot = 0.25 # angle [0, 1)
        self.__degrees = 360.0
        self.__costume = 'classic'
        self.__pen_size = 1.0

    # ----------------------------------------

    @property
    def costume(self) -> Any:
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Any) -> None:
        '''
        Get or set the current turtle costume.

        ```
        self.costume = img
        ```
        '''
        _setcostume(self.__turtle, self.__tid, new_costume)
        self.__costume = new_costume

    @property
    def pos(self) -> Tuple[float, float]:
        return self.__x, self.__y
    @pos.setter
    def pos(self, new_pos: Tuple[float, float]) -> None:
        '''
        Get or set the position of the turtle, which is a pair of (x, y) coordinates.

        ```
        self.pos = (10, 45)
        ```
        '''
        self.__setpos(*map(float, new_pos))
    def __setpos(self, x: float, y: float) -> None:
        self.__x, self.__y = x, y
        _qinvoke(self.__turtle.goto, x, y)

    @property
    def x_pos(self) -> float:
        return self.__x
    @x_pos.setter
    def x_pos(self, new_x: float) -> None:
        '''
        Get or set the x position of the turtle.

        ```
        self.x_pos = 60
        ```
        '''
        self.__setpos(float(new_x), self.__y)

    @property
    def y_pos(self) -> float:
        return self.__y
    @y_pos.setter
    def y_pos(self, new_y: float) -> None:
        '''
        Get or set the y position of the turtle.

        ```
        self.y_pos = -10
        ```
        '''
        self.__setpos(self.__x, float(new_y))

    @property
    def heading(self) -> float:
        return self.__rot * self.__degrees
    @heading.setter
    def heading(self, new_heading: float) -> None:
        '''
        Get or set the heading (direction) of the turtle.
        Note that this is affected by the current degrees mode.

        ```
        self.heading = 0 # face north
        ```
        '''
        self.__setheading(float(new_heading))
    def __setheading(self, new_heading: float) -> None:
        self.__rot = (new_heading / self.__degrees) % 1.0
        _qinvoke(self.__turtle.setheading, (0.25 - self.__rot) % 1.0 * 360.0) # raw turtle is always in degrees mode

    @property
    def degrees(self) -> float:
        return self.__degrees
    @degrees.setter
    def degrees(self, full_circle: float = 360.0) -> None:
        '''
        Get or set how many "degrees" are in a circle (default 360).
        This is useful if you want to draw pie charts (100 "degrees" per circle) or work in radians (2*pi "degrees" per circle).

        The apparent heading of the turtle is unchanged - this is just a way of measuring angles.

        ```
        self.degress = 360         # switch to (normal) degrees mode
        self.degress = 2 * math.pi # switch to radians mode
        ```
        '''
        self.__degrees = float(full_circle)

    @property
    def visible(self) -> bool:
        return self.__visible
    @visible.setter
    def visible(self, is_visible: bool) -> None:
        '''
        Get or set whether or not the turtle is visible

        ```
        self.visible = True  # show the turtle
        self.visible = False # hide the turtle
        ```
        '''
        self.__visible = bool(is_visible)
        _qinvoke(self.__turtle.showturtle if self.__visible else self.__turtle.hideturtle)

    @property
    def drawing(self) -> bool:
        return self.__drawing
    @drawing.setter
    def drawing(self, is_drawing: bool) -> None:
        '''
        Get or set whether or not the turtle should draw a trail behind it as it moves.

        ```
        self.drawing = True  # start drawing
        self.drawing = False # stop drawing
        ```
        '''
        self.__drawing = bool(is_drawing)
        _qinvoke(self.__turtle.pendown if self.__drawing else self.__turtle.penup)

    @property
    def pen_size(self) -> float:
        return self.__pen_size
    @pen_size.setter
    def pen_size(self, new_size: float) -> None:
        '''
        Get or set the width of the drawing pen (in pixels).
        This affects the width of drawn trails when `drawing` is set to `True`.

        ```
        self.pen_size = 1 # normal pen size
        self.pen_size = 4 # larger pen size
        ```
        '''
        self.__pen_size = float(new_size)
        _qinvoke(self.__turtle.pensize, self.__pen_size)

    @property
    def pen_color(self) -> Tuple[int, int, int]:
        return _qinvoke_wait(self.__turtle.color)
    @pen_color.setter
    def pen_color(self, new_color: Any) -> None:
        '''
        Get or set the current pen color.
        For getting, this is returned as three integers representing the red, green, and blue components: (red, green, blue).
        For setting, this can be specified in several ways:
            - A color name string like `'red'`
            - A tuple of three integers representing the red, green, and blue components like `(34, 23, 104)`
            - A hexadecimal color string like `'#a0c8f0'`

        ```
        self.pen_color = 'red'
        self.pen_color = (34, 23, 104)
        self.pen_color = '#a0c8f0'
        ```
        '''
        _qinvoke(self.__turtle.color, new_color)


    # -------------------------------------------------------

    def forward(self, distance: float) -> None:
        '''
        Move forward by the given number of pixels.

        ```
        self.forward(40)
        ```
        '''
        distance = float(distance)
        h = self.__rot * 2 * _math.pi
        self.__setpos(self.__x + _math.sin(h) * distance, self.__y + _math.cos(h) * distance)

    def turn_left(self, angle: float = None) -> None:
        '''
        Turn the turtle to the left by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_left(45)
        ```
        '''
        self.__setheading(self.heading - float(angle) if angle is not None else self.__degrees / 4)
    def turn_right(self, angle: float = None) -> None:
        '''
        Turn the turtle to the right by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_right(45)
        ```
        '''
        self.__setheading(self.heading + float(angle) if angle is not None else self.__degrees / 4)
    
    # -------------------------------------------------------

    def clear(self) -> None:
        '''
        Clears (erases) all of the drawings made by this turtle.

        ```
        self.clear()
        ```
        '''
        _qinvoke(self.__turtle.clear)

    def stamp(self) -> None:
        '''
        Stamps an image of the turtle on the background at the current position.
        Stamps can be deleted by calling `self.clear_stamps()` (just stamps) or `self.clear()` (all drawings).

        ```
        self.stamp()
        ```
        '''
        _qinvoke(self.__turtle.stamp)

    def clear_stamps(self) -> None:
        '''
        Clears (erases) all of the stamps made by this turtle.

        ```
        self.clear_stamps()
        ```
        '''
        _qinvoke(self.__turtle.clearstamps)

    def dot(self, radius: int = None):
        '''
        Draws a dot (circle) on the background at the current position.
        The radius argument allows you to set the size in pixels, otherwise a default is used based on the pen width.
        Dots count as drawings, so they can be erased with `self.clear()`.

        ```
        self.dot()   # make a dot with default radius
        self.dot(10) # make a dot with radius 10 pixels
        ```
        '''
        _qinvoke(self.__turtle.dot, int(radius) if radius is not None else None)

    def write(self, text: str, *, size: int = 12, align: str = 'left', move = False):
        '''
        Draws text onto the background.
        The `size` argument sets the font size of the drawn text.
        The `align` argument can be `left`, `right`, or `center` and controls how the text is drawn.
        The `move` argument specifies if the turtle should move to the end of the text after drawing.

        Text counts as a drawing, so it can be erased by calling `self.clear()`.

        ```
        self.write('normal hello world!')
        self.write('small hello world!', size = 8)
        ```
        '''
        def batcher():
            self.__turtle.write(str(text), bool(move), align, ('Arial', int(size), 'normal'))
            return self.__turtle.position()
        self.__x, self.__y = _qinvoke_wait(batcher)

def _derive(bases, cls):
    limited_bases = [b for b in bases if not issubclass(cls, b)]
    class Derived(*limited_bases, cls):
        def __init__(self, *args, **kwargs):
            for base in bases:
                base.__init__(self)
            cls.__init__(self, *args, **kwargs)

            start_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                thread = _threading.Thread(target = start_script)
                thread.setDaemon(True)
                thread.start()

            key_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_key'))
            for _, key_script in key_scripts:
                for key in getattr(key_script, '__run_on_key'):
                    _add_key_event(key, key_script)
            
            click_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_click'))
            for _, click_script in click_scripts:
                for key in getattr(click_script, '__run_on_click'):
                    _add_click_event(key, click_script)

            msg_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_message'))
            for _, msg_script in msg_scripts:
                for inserter in getattr(msg_script, '__run_on_message'): # client gave us a list of convenient insertion functions
                    inserter(msg_script)
    
    return Derived

def turtle(cls):
    '''
    The `@turtle` decorator for a class creates a new type of turtle.
    This should be used in conjunction with the `TurtleBase` base class.

    You can use the `@onstart` decorator on any method definition to make it run when a turtle of this type is created.

    ```
    @turtle
    class MyTurtle(TurtleBase):
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
    This should be used in conjunction with the `StageBase` base class.
    Stages function much like the stage in NetsBlox - equivalent to a sprite/turtle except with no movement controls.
    Unlike in NetsBlox, you may create multiple instances of a stage, or even multiple types of stages.

    You can use the `@onstart` decorator on any method definition to make it run when a stage of this type is created.

    ```
    @stage
    class MyStage(StageBase):
        @onstart
        def start(self):
            print('stage starting')
    ```
    '''
    return _derive([StageBase], cls)

def onstart(f):
    '''
    The `@onstart` decorator can be applied to a method definition inside a stage or turtle
    to make that function run whenever the stage/turtle is created.

    `@onstart` can also be applied to a function at global scope (not a method),
    in which case the function is called when the project is started.

    ```
    @onstart
    def start(self):
        self.forward(75)
    ```
    '''
    if _common.is_method(f):
        setattr(f, '__run_on_start', True)
    else:
        t = _threading.Thread(target = f)
        t.setDaemon(True)
        t.start()
    return f

def _add_gui_event_wrapper(field, register, keys):
    def wrapper(f):
        if _common.is_method(f):
            if not hasattr(f, field):
                setattr(f, field, [])
            getattr(f, field).extend(keys)
        else:
            for key in keys:
                register(key, f)

        return f
    return wrapper

# keys are targets (case sensitive), values are lists of valid inputs (case insentive)
_KEY_GROUPS = {
    ('Right',): ['right', 'right arrow', 'arrow right'],
    ('Left',): ['left', 'left arrow', 'arrow left'],
    ('Up',): ['up', 'up arrow', 'arrow up'],
    ('Down',): ['down', 'down arrow', 'arrow down'],
    ('Prior',): ['pageup', 'page up'],
    ('Next',): ['pagedown', 'page down'],
    ('Return', 'KP_Enter'): ['return', 'enter'],
    ('Caps_Lock',): ['capslock', 'caps lock'],
    ('Num_Lock',): ['numlock', 'num lock'],
    ('Scroll_Lock',): ['scrolllock', 'scroll lock'],
    ('Alt_L', 'Alt_R'): ['alt', 'left alt'],
    ('Control_L', 'Control_R'): ['control', 'left control', 'ctrl', 'left ctrl'],
    ('Shift_L', 'Shift_R'): ['shift', 'left shift'],
    ('Escape',): ['esc', 'escape'],
    ('minus', 'KP_Subtract'): ['-', 'minus', 'subtract'],
    ('plus', 'KP_Add'): ['+', 'plus', 'add'],
    ('space',): ['space', ' '],
    ('BackSpace',): ['backspace'],
    ('Delete',): ['delete'],
    ('Home',): ['home'],
    ('End',): ['end'],
    ('Insert',): ['insert'],
    ('Print',): ['print'],
    ('Tab',): ['tab'],
    ('0', 'KP_0'): ['0'],
    ('1', 'KP_1'): ['1'],
    ('2', 'KP_2'): ['2'],
    ('3', 'KP_3'): ['3'],
    ('4', 'KP_4'): ['4'],
    ('5', 'KP_5'): ['5'],
    ('6', 'KP_6'): ['6'],
    ('7', 'KP_7'): ['7'],
    ('8', 'KP_8'): ['8'],
    ('9', 'KP_9'): ['9'],
    (None,): ['any'],
}
# flattened transpose of _KEY_GROUPS - keys are input (case insensitive), values are targets (case sensitive)
_KEY_MAPS = {}
for k,vs in _KEY_GROUPS.items():
    for v in vs:
        assert v not in _KEY_MAPS
        assert v == v.lower()
        _KEY_MAPS[v] = k

for k,vs in _KEY_MAPS.items(): # sanity check
    assert type(k) == str
    assert type(vs) == tuple
    for v in vs:
        assert v is None or type(v) == str
def _map_key(key: str) -> Iterable[str]:
    return _KEY_MAPS.get(key.lower(), (key,))

def onkey(*keys: str):
    '''
    The `@onkey` decorator can be applied to a function at global scope
    or a method definition inside a stage or turtle
    to make that function run whenever the user presses a key on the keyboard.

    The special `'any'` value can be used to catch any key press.

    ```
    @onkey('space')
    def space_key_pressed():
        stop_project()

    @onkey('w', 'up')
    def w_or_up_arrow_pressed(self):
        self.forward(50)
    ```
    '''
    mapped_keys = []
    for key in keys:
        mapped_keys.extend(_map_key(key))
    return _add_gui_event_wrapper('__run_on_key', _add_key_event, mapped_keys)

def onclick(f):
    '''
    The `@onclick` decorator can be applied to a function at global scope to
    make that function run whenever the user clicks on the display.
    The function you apply it to will receive the `x` and `y` position of the click.

    This can also be applied to turtle/stage methods, however note that they
    will be called when the user clicks _anywhere_ on the display, not specifically on the stage/turtle.

    ```
    @onclick
    def mouse_click(x, y):
        print('user clicked at', x, y)
    ```
    '''
    return _add_gui_event_wrapper('__run_on_click', _add_click_event, [1])(f) # call wrapper immediately cause we take no args

_did_setup_input = False
def setup_input():
    global _did_setup_input
    if _did_setup_input:
        return
    _did_setup_input = True

    def new_input(prompt: Any = '?') -> str:
        def asker():
            res = _turtle.textinput('UserInput', str(prompt))
            _turtle.listen()
            return res
        return _qinvoke_wait(asker)
    _builtins.input = new_input
