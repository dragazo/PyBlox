#!/usr/bin/env python

import builtins as _builtins

import turtle as _turtle

import threading as _threading
import traceback as _traceback
import inspect as _inspect
import queue as _queue
import math as _math
import copy as _copy
import sys as _sys
import re as _re

import numpy as _np

import netsblox.common as _common
import netsblox.events as _events
import netsblox.colors as _colors

from typing import Any, Union, Tuple, Iterable, Optional, List

from PIL import Image, ImageTk, ImageDraw
import mss

VIS_THRESH = 20
def _image_alpha(img: Image.Image) -> Image.Image:
    assert img.mode == 'RGBA'
    return img.getchannel('A')
def _area(size: Tuple[int, int]) -> int:
    return size[0] * size[1]
def _intersects(a: Tuple[Image.Image, int, int], b: Tuple[Image.Image, int, int]) -> bool:
    asize, bsize = _area(a[0].size), _area(b[0].size)
    if asize == 0 or bsize == 0:
        return False
    if bsize < asize:
        a, b = b, a

    base, other = _image_alpha(a[0]), _image_alpha(b[0])
    other_center_x = float(b[1] - a[1])
    other_center_y = -float(b[2] - a[2])
    other_x = base.width / 2 + other_center_x - other.width / 2
    other_y = base.height / 2 + other_center_y - other.height / 2

    other_trans = Image.new('L', base.size, 0)
    other_trans.paste(other, (round(other_x), round(other_y)))

    return _np.bitwise_and(_np.array(base) >= VIS_THRESH, _np.array(other_trans) >= VIS_THRESH).any()

def _traceback_wrapped(fn):
    def wrapped(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except:
            print(_traceback.format_exc(), file = _sys.stderr) # print out directly so that the stdio wrappers are used
    return wrapped

_key_events = {} # maps key to [raw handler, _EventWrapper[]]
def _add_key_event(key, event):
    if key not in _key_events:
        entry = [None, []]
        def raw_handler():
            handlers = entry[1] if key is None or None not in _key_events else entry[1] + _key_events[None][1]
            for handler in handlers:
                handler.schedule_no_queueing()
        entry[0] = raw_handler

        _key_events[key] = entry
        _turtle.onkeypress(entry[0], key)

    _key_events[key][1].append(_events.get_event_wrapper(event))

_click_events = {} # maps key to [raw handler, event[]]
def _add_click_event(key, event):
    if key not in _click_events:
        entry = [None, []]
        def raw_handler(rawx, rawy):
            scale = _get_logical_scale()
            x, y = rawx / scale, rawy / scale
            for handler in entry[1]:
                should_handle = True
                wrapped = handler.wrapped()
                obj = getattr(wrapped, '__self__', None)
                if isinstance(obj, TurtleBase) and not hasattr(wrapped, '__click_anywhere'):
                    obj_disp_img = getattr(obj, '_TurtleBase__display_image')
                    obj_x, obj_y = obj.x_pos * scale, obj.y_pos * scale
                    should_handle = _intersects((obj_disp_img, obj_x, obj_y), (_CURSOR_KERNEL, rawx, rawy))

                if should_handle:
                    handler.schedule_no_queueing(x, y)
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

_BLANK_IMG = Image.new('RGBA', (1, 1)) # fully transparent
_CURSOR_KERNEL = Image.new('RGBA', (3, 3), 'black') # used for cursor click collision detection on sprites - should be roughly circleish

def _turtle_image(color: Tuple[int, int, int], scale: float) -> Image.Image:
    w, h = round(40 * scale), round(30 * scale)
    img = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(img)
    draw.polygon([(0, 0), (w, h / 2), (0, h), (w * 0.25, h / 2)], fill = color, outline = 'black')
    return img

def _setcostume(t, rawt, tid, costume: Union[None, Image.Image]) -> None:
    def batcher():
        if costume is not None:
            name = f'custom-costume-{tid}'
            _turtle.register_shape(name, _ImgWrapper(costume))
            rawt.shape(name)
        elif isinstance(t, TurtleBase):
            rawt.shape('classic')
        else:
            _turtle.register_shape('blank', _ImgWrapper(_BLANK_IMG))
            rawt.shape('blank')
    _qinvoke(batcher)

def _apply_transforms(img: Optional[Image.Image], scale: float, rot: float) -> Image.Image:
    if img is None: return None

    w, h = img.size
    img = img.resize((round(w * scale), round(h * scale)))
    return img.rotate((0.25 - rot) * 360, expand = True, resample = Image.BICUBIC)

# if set to non-none, will use RawTurtle with this as its TurtleScreen parent
_raw_turtle_target = None
_turtle_count = 0
def _make_turtle(wrapper):
    def batcher():
        global _turtle_count
        tid = _turtle_count
        _turtle_count += 1

        t = _turtle.Turtle() if _raw_turtle_target is None else _turtle.RawTurtle(_raw_turtle_target)
        t.speed('fastest')
        t.penup()

        _setcostume(wrapper, t, tid, None)

        return t, tid
    return _qinvoke_wait(batcher)

_window_size_cached = None
_logical_size_cached = None
_logical_scale_cached = None
_registered_resize_hook = False
_all_turtles = []
_all_stages = [] # ide enforces only one stage, but in general could have multiple

def _get_logical_scale() -> float:
    if _logical_scale_cached is not None:
        return _logical_scale_cached

    def batcher():
        global _logical_scale_cached
        wsize = _get_window_size()
        lsize = _get_logical_size()
        _logical_scale_cached = min(wsize[0] / lsize[0], wsize[1] / lsize[1])
        return _logical_scale_cached
    return _qinvoke_wait(batcher)

def _perform_resize_ui() -> None:
    global _logical_scale_cached
    wsize = _get_window_size()
    lsize = _get_logical_size()
    scale = _logical_scale_cached = min(wsize[0] / lsize[0], wsize[1] / lsize[1])

    for t in _all_turtles:
        x, y = t.pos
        getattr(t, '_TurtleBase__turtle').goto(x * scale, y * scale)
        getattr(t, '_TurtleBase__update_costume')()
    for s in _all_stages:
        getattr(s, '_StageBase__update_costume')()

def _register_resize_hook() -> None:
    if _registered_resize_hook: return

    def batcher():
        global _registered_resize_hook
        if _registered_resize_hook: return # double checked lock now that we're on the ui thread
        _registered_resize_hook = True

        def update(e):
            global _window_size_cached
            if _window_size_cached is None or _window_size_cached[0] != e.width or _window_size_cached[1] != e.height:
                _window_size_cached = (e.width + 2, e.height + 2) # add back the 1px outline from tkinter
                _turtle.Screen().getcanvas().after(0, _perform_resize_ui)
        _turtle.Screen().getcanvas().bind('<Configure>', update)
    _qinvoke_wait(batcher)

def _get_window_size() -> Tuple[int, int]:
    global _window_size_cached
    _register_resize_hook()

    if _window_size_cached is not None:
        return _window_size_cached
    else:
        _window_size_cached = _qinvoke_wait(lambda: _turtle.Screen().screensize())
        return _window_size_cached
def _set_window_size(width: int, height: int) -> None:
    def batcher():
        global _logical_size_cached
        _logical_size_cached = (width, height)
        _register_resize_hook()
        _turtle.setup(width, height)
    _qinvoke_wait(batcher)
def _get_logical_size() -> Tuple[int, int]:
    global _logical_size_cached
    if _logical_size_cached is not None:
        return _logical_size_cached

    _logical_size_cached = _get_window_size()
    return _logical_size_cached

class _Ref:
    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self

class StageBase(_Ref):
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

        self.__costume = None

        self.__turtle, self.__tid = _make_turtle(self)

        _all_stages.append(self)

    def __update_costume(self):
        img = _apply_transforms(self.__costume, _get_logical_scale(), 0.25)
        _setcostume(self, self.__turtle, self.__tid, img)

    @property
    def costume(self) -> Union[None, Image.Image]:
        '''
        Get or set the current stage costume (background).

        ```
        self.costume = img
        ```
        '''
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Union[None, Image.Image]) -> None:
        if new_costume is not None:
            if not isinstance(new_costume, Image.Image):
                raise TypeError(f'attempt to set costume to a non-image type: {type(new_costume)}')
            new_costume = new_costume.convert('RGBA')

        self.__costume = new_costume
        self.__update_costume()

    @property
    def size(self) -> Tuple[int, int]:
        '''
        Gets or sets the logical size of the stage (width, height).
        This controls the space in which turtles are visible.
        Setting the logical size of the turtle space also changes the physical size of the window.

        ```
        width, height = self.size
        self.size = (800, 600)
        ```
        '''
        return _get_logical_size()
    @size.setter
    def size(self, new_size: Tuple[int, int]) -> None:
        _set_window_size(*map(int, new_size))

    @property
    def width(self) -> int:
        '''
        Get the width of the stage in pixels.

        ```
        print('width:', self.width)
        ```
        '''
        return _get_logical_size()[0]

    @property
    def height(self) -> int:
        '''
        Get the height of the stage in pixels.

        ```
        print('height:', self.height)
        ```
        '''
        return _get_logical_size()[1]
    
    def grab_image(self) -> Any:
        '''
        Grabs and returns an image of the stage and everything one it.
        This is effectively a picture of the entire turtle environment.

        ```
        img = self.grab_image()
        ```
        '''
        def batcher():
            canvas = _turtle.Screen().getcanvas()
            x = canvas.winfo_rootx()
            y = canvas.winfo_rooty()
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            with mss.mss() as sct:
                raw = sct.grab({ 'left': x, 'top': y, 'width': w, 'height': h })
                return Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        return _qinvoke_wait(batcher)

class TurtleBase(_Ref):
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

        self.__drawing = False
        self.__visible = True
        self.__x = 0.0
        self.__y = 0.0
        self.__rot = 0.25 # angle [0, 1)
        self.__scale = 1.0
        self.__degrees = 360.0
        self.__pen_size = 1.0
        self.__pen_color = (0, 0, 0) # [0,255] rgb (defaults to black)
        self.__costume = None
        self.__display_image = None # managed by costume transforms logic

        self.__turtle, self.__tid = _make_turtle(self)
        self.__update_costume() # update display image based on color/scale

        _all_turtles.append(self)

    def __clone_from(self, src):
        def batcher():
            self.pos = src.pos
            self.heading = src.heading
            self.visible = src.visible
            self.costume = src.costume
            self.pen_size = src.pen_size
            self.pen_color = src.pen_color
            self.drawing = src.drawing
            self.degrees = src.degrees
        _qinvoke_wait(batcher)

    def __update_costume(self):
        src = self.__costume
        scale = self.__scale * _get_logical_scale()
        res = _apply_transforms(src, scale, self.__rot) if src is not None else _apply_transforms(_turtle_image(self.__pen_color, scale), 1.0, self.__rot)

        self.__display_image = res
        _setcostume(self, self.__turtle, self.__tid, res)

    def clone(self) -> Any:
        '''
        Create and return a clone (copy) of this turtle.
        The created turtle will have a deep copy of any variables this turtle has set.
        The new turtle will be created at the same position and in the same direction as the current turtle (everything is identical).

        Cloning is a great way to reduce duplicated code.
        If you need many turtles which happen to do the same thing,
        consider writing a single turtle and making it clone itself several times at the beginning.

        ```
        my_clone = self.clone()
        ```
        '''
        Derived = getattr(self, '_Derived__Derived', None)
        if Derived is None:
            raise RuntimeError('Tried to clone a turtle type which was not defined with @turtle')
        return Derived(_CloneTag(self))

    # ----------------------------------------

    @property
    def costume(self) -> Any:
        '''
        Get or set the current turtle costume.

        ```
        self.costume = img
        ```
        '''
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Image.Image) -> None:
        if new_costume is not None:
            if not isinstance(new_costume, Image.Image):
                raise TypeError(f'attempt to set costume to a non-image type: {type(new_costume)}')
            new_costume = new_costume.convert('RGBA')

        self.__costume = new_costume
        self.__update_costume()

    @property
    def scale(self) -> float:
        '''
        Get or set the current turtle scale.
        Larger values make the turtle larger.

        This should be a positive number

        ```
        self.scale = 2.5
        ```
        '''
        return self.__scale
    @scale.setter
    def scale(self, new_scale: float) -> None:
        new_scale = float(new_scale)
        if new_scale <= 0:
            raise RuntimeError(f'attempt to set turtle scale to non-positive value: {new_scale}')
        self.__scale = new_scale
        self.__update_costume()

    @property
    def pos(self) -> Tuple[float, float]:
        '''
        Get or set the position of the turtle, which is a pair of (x, y) coordinates.

        ```
        self.pos = (10, 45)
        ```
        '''
        return self.__x, self.__y
    @pos.setter
    def pos(self, new_pos: Tuple[float, float]) -> None:
        self.__setpos(*map(float, new_pos))
    def __setpos(self, x: float, y: float) -> None:
        scale = _get_logical_scale()
        self.__x, self.__y = x, y
        _qinvoke(self.__turtle.goto, x * scale, y * scale)

    @property
    def x_pos(self) -> float:
        '''
        Get or set the x position of the turtle.

        ```
        self.x_pos = 60
        ```
        '''
        return self.__x
    @x_pos.setter
    def x_pos(self, new_x: float) -> None:
        self.__setpos(float(new_x), self.__y)

    @property
    def y_pos(self) -> float:
        '''
        Get or set the y position of the turtle.

        ```
        self.y_pos = -10
        ```
        '''
        return self.__y
    @y_pos.setter
    def y_pos(self, new_y: float) -> None:
        self.__setpos(self.__x, float(new_y))

    @property
    def heading(self) -> float:
        '''
        Get or set the heading (direction) of the turtle.
        Note that this is affected by the current degrees mode.

        ```
        self.heading = 0 # face north
        ```
        '''
        return self.__rot * self.__degrees
    @heading.setter
    def heading(self, new_heading: float) -> None:
        self.__setheading(float(new_heading))
    def __setheading(self, new_heading: float) -> None:
        self.__rot = (new_heading / self.__degrees) % 1.0
        self.__update_costume()
        _qinvoke(self.__turtle.setheading, (0.25 - self.__rot) % 1.0 * 360.0) # raw turtle is always in degrees mode

    @property
    def degrees(self) -> float:
        '''
        Get or set how many "degrees" are in a circle (default 360).
        This is useful if you want to draw pie charts (100 "degrees" per circle) or work in radians (2*pi "degrees" per circle).

        The apparent heading of the turtle is unchanged - this is just a way of measuring angles.

        ```
        self.degress = 360         # switch to (normal) degrees mode
        self.degress = 2 * math.pi # switch to radians mode
        ```
        '''
        return self.__degrees
    @degrees.setter
    def degrees(self, full_circle: float = 360.0) -> None:
        self.__degrees = float(full_circle)

    @property
    def visible(self) -> bool:
        '''
        Get or set whether or not the turtle is visible

        ```
        self.visible = True  # show the turtle
        self.visible = False # hide the turtle
        ```
        '''
        return self.__visible
    @visible.setter
    def visible(self, is_visible: bool) -> None:
        self.__visible = bool(is_visible)
        _qinvoke(self.__turtle.showturtle if self.__visible else self.__turtle.hideturtle)

    @property
    def drawing(self) -> bool:
        '''
        Get or set whether or not the turtle should draw a trail behind it as it moves.

        ```
        self.drawing = True  # start drawing
        self.drawing = False # stop drawing
        ```
        '''
        return self.__drawing
    @drawing.setter
    def drawing(self, is_drawing: bool) -> None:
        self.__drawing = bool(is_drawing)
        _qinvoke(self.__turtle.pendown if self.__drawing else self.__turtle.penup)

    @property
    def pen_size(self) -> float:
        '''
        Get or set the width of the drawing pen (in pixels).
        This affects the width of drawn trails when `drawing` is set to `True`.

        ```
        self.pen_size = 1 # normal pen size
        self.pen_size = 4 # larger pen size
        ```
        '''
        return self.__pen_size
    @pen_size.setter
    def pen_size(self, new_size: float) -> None:
        self.__pen_size = float(new_size)
        _qinvoke(self.__turtle.pensize, self.__pen_size)

    @property
    def pen_color(self) -> Tuple[int, int, int]:
        '''
        Get or set the current pen color.
        For getting, this is returned as three integers [0,255] representing the red, green, and blue (RGB) components.
        For setting, this can be specified as either an RGB tuple, or as a hex color code like `'#a0c8f0'`.

        ```
        self.pen_color = (34, 23, 104)
        self.pen_color = '#a0c8f0'
        ```
        '''
        return self.__pen_color
    @pen_color.setter
    def pen_color(self, new_color: Union[str, Tuple[int, int, int]]) -> None:
        new_color = _colors.parse_color(new_color)
        assert type(new_color) is tuple # sanity check so users can't modify colors

        self.__pen_color = new_color
        _qinvoke(self.__turtle.pencolor, tuple(x / 255 for x in new_color))

        if self.__costume is None:
            self.__update_costume()

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
    
    # -----------------------------------

    def is_touching(self, other: Any) -> bool:
        '''
        Checks if this turtle is touching the other turtle, that is, they are both visible overlapping.

        ```
        if self.is_touching(other_turtle):
            self.turn_right(180)
        ```
        '''
        if not isinstance(other, TurtleBase):
            raise TypeError(f'Attempt to check if a turtle is touching a non-turtle (type {type(other)})')

        scale = _get_logical_scale()
        return self.__visible and other.__visible and _intersects(
            (self.__display_image, self.__x * scale, self.__y * scale),
            (other.__display_image, other.__x * scale, other.__y * scale))
    def get_all_touching(self) -> List[Any]:
        '''
        Gets a list of all the turtles that this turtle is touching, other than itself.

        ```
        touch_count = len(self.get_all_touching())
        ```
        '''
        return [other for other in _all_turtles if other is not self and self.is_touching(other)]

class _CloneTag:
    def __init__(self, src):
        self.src = src

def _derive(bases, cls):
    limited_bases = [b for b in bases if not issubclass(cls, b)]
    class Derived(*limited_bases, cls):
        def __init__(self, *args, **kwargs):
            self.__Derived = Derived
            for base in bases:
                base.__init__(self)

            if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], _CloneTag):
                src = args[0].src
                self.__Derived_args = src.__Derived_args
                self.__Derived_kwargs = src.__Derived_kwargs

                self.__clone_from(src)
                self.__is_clone = src
                cls.__init__(self, *self.__Derived_args, **self.__Derived_kwargs)
            else:
                self.__Derived_args = args
                self.__Derived_kwargs = kwargs

                self.__is_clone = None
                cls.__init__(self, *args, **kwargs)

            start_tag = '__run_on_start' if not self.__is_clone else '__run_on_start_clone'
            start_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, start_tag))
            for _, start_script in start_scripts:
                thread = _threading.Thread(target = _traceback_wrapped(start_script))
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

        def __clone_from(self, src):
            def filter_out(name):
                return any(name.startswith(x) for x in ['_Derived_', '_TurtleBase_', '_StageBase_'])
            fields = [x for x in vars(src).keys() if not filter_out(x)]
            for field in fields:
                setattr(self, field, _copy.deepcopy(getattr(src, field)))
            
            for base in bases: # recurse to child types for specialized cloning logic (like turtle repositioning)
                getattr(self, f'_{base.__name__}__clone_from')(src)

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

    Turtles created via cloning will not run onstart events; instead, use the `@onstartclone` decorator.

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
        t = _threading.Thread(target = _traceback_wrapped(f))
        t.setDaemon(True)
        t.start()
    return f

def onstartclone(f):
    '''
    The `@onstartclone` decorator can be applied to turtle methods, and is
    equivalent to `@onstart` except that it runs when a clone is created.

    ```
    @onstartclone
    def clonestart(self):
        self.forawrd(75)
    ```
    '''
    if _common.is_method(f):
        setattr(f, '__run_on_start_clone', True)
    else:
        raise TypeError('Attempt to use @onstartclone on a non-method')
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

    This can also be applied to turtle/stage methods, however note that when used on turtles
    the function will only be called when the user clicks on the turtle itself.
    If you want to have a turtle run a function when the user clicks anywhere, use `@onclickanywhere` instead.

    ```
    @onclick
    def mouse_click(self, x, y):
        print('user clicked at', x, y)
    ```
    '''
    return _add_gui_event_wrapper('__run_on_click', _add_click_event, [1])(f) # call wrapper immediately cause we take no args

def onclickanywhere(f):
    '''
    Equivalent to `@onclick` except that it is triggered when the user clicks anywhere on the display,
    even when used on a turtle.

    ```
    @onclickanywhere
    def mouse_click(self, x, y):
        print('user clicked at', x, y)
    ```
    '''
    setattr(f, '__click_anywhere', True)
    return onclick(f)

_did_setup_stdio = False
_print_lock = _threading.Lock()
def setup_stdio():
    global _did_setup_stdio
    if _did_setup_stdio: return
    _did_setup_stdio = True

    def new_input(prompt: Any = '?') -> str:
        def asker():
            res = _turtle.textinput('UserInput', str(prompt))
            _turtle.listen()
            return res
        return _qinvoke_wait(asker)
    _builtins.input = new_input

    old_print = print
    def new_print(*args, **kwargs) -> None:
        with _print_lock:
            old_print(*args, **kwargs)
    _builtins.print = new_print
