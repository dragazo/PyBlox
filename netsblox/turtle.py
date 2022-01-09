#!/usr/bin/env python

import builtins as _builtins

import tkinter as _tk
from tkinter import simpledialog as _simpledialog
from tkinter import ttk as _ttk

import threading as _threading
import traceback as _traceback
import inspect as _inspect
import queue as _queue
import copy as _copy
import math as _math
import time as _time
import sys as _sys

import numpy as _np

import netsblox.common as _common
import netsblox.events as _events
import netsblox.colors as _colors
import netsblox.concurrency as _concurrency

from typing import Any, Union, Tuple, Optional, List, Callable

from PIL import Image, ImageTk, ImageDraw, ImageFont

_FONT_SRC = f'{_common._NETSBLOX_PY_PATH}/assets/fonts/Droid/DroidSansFallback.ttf'
_FONT_LOCK = _threading.Lock()
_CACHED_FONT = None
def _get_font() -> ImageFont.ImageFont:
    global _CACHED_FONT
    if _CACHED_FONT is not None: return _CACHED_FONT
    with _FONT_LOCK:
        if _CACHED_FONT is not None: return _CACHED_FONT
        _CACHED_FONT = ImageFont.truetype(_FONT_SRC)
        return _CACHED_FONT

_RENDER_PERIOD = 16 # time between frames in ms
_SAY_PAGINATE_LEN = 30 # max length of a paginated line in turtle.say()
_SAY_PAGINATE_MAX_LINES = 8 # max number of lines to show before ...-ing the rest

_GRAPHICS_SLEEP_TIME = 0.0085 # time to pause after gui stuff like sprite movement
_do_graphics_sleep = True
def _graphics_sleep():
    if _do_graphics_sleep:
        _time.sleep(_GRAPHICS_SLEEP_TIME)

_VIS_THRESH = 20
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

    return _np.bitwise_and(_np.array(base) >= _VIS_THRESH, _np.array(other_trans) >= _VIS_THRESH).any()

def _render_text(text: str, size: float, color: Tuple[int, int, int]) -> Image.Image:
    font = _get_font().font_variant(size = round(1.5 * size))

    text_mask = font.getmask(text, mode = 'L', features = ['aalt'])
    text_mask = Image.frombytes('L', text_mask.size, _np.array(text_mask).astype(_np.uint8)) # convert ImagingCore to Image
    text_img = Image.new('RGBA', text_mask.size, color)
    text_img.putalpha(text_mask)

    return text_img

def _traceback_wrapped(fn):
    def wrapped(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except:
            print(_traceback.format_exc(), file = _sys.stderr) # print out directly so that the stdio wrappers are used
    return wrapped

def _start_safe_thread(f: Callable, *args, **kwargs) -> _threading.Thread:
    thread = _threading.Thread(target = _traceback_wrapped(_start_signal_wrapped(f)), args = args, kwargs = kwargs)
    thread.setDaemon(True)
    thread.start()
    return thread

class ProjectStateError(Exception): pass

_action_queue_thread_id = _threading.get_ident()

_action_queue_ret_cv = _threading.Condition(_threading.Lock())
_action_queue_ret_id = 0
_action_queue_ret_vals = {}

_action_queue = _queue.Queue() # queue of 2- and 3-tuples for deferred execution on ui thread
_ACTION_QUEUE_INTERVAL = 16    # ms between control slices
_ACTION_MAX_PER_SLICE = 16     # max number of actions to perform during a control slice

_game_running = False
_game_stopped = False # different than not running due to 3-state system

_start_signal = _concurrency.Signal()
def _start_signal_wrapped(f):
    def wrapped(*args, **kwargs):
        _start_signal.wait()
        return f(*args, **kwargs)
    return wrapped

class _Project:
    def __init__(self, *, logical_size: Tuple[int, int], physical_size: Tuple[int, int]):
        self.__lock = _threading.RLock()
        self.__stages = {}
        self.__turtles = {}

        self.__tk = _tk.Tk()
        self.__tk.minsize(400, 200)
        self.__tk.geometry(f'{physical_size[0]}x{physical_size[1]}')

        self.__tk.protocol('WM_DELETE_WINDOW', stop_project)

        self.__tk_canvas = _tk.Canvas(self.__tk)
        self.__tk_canvas.pack(fill = _tk.BOTH, expand = True)
        self.logical_size = logical_size

        self.__last_frame = Image.new('RGBA', logical_size, (255, 255, 255))

        last_size = [(-1, -1)]
        def on_canvas_resize(e):
            if e.widget is not self.__tk_canvas: return 'break' # ignore children, if any
            new_size = (self.__tk_canvas.winfo_width(), self.__tk_canvas.winfo_height())
            if last_size[0] == new_size: return 'break'
            last_size[0] = new_size
            self.invalidate()
            return 'break'
        self.__tk_canvas.bind_all('<Configure>', on_canvas_resize)

        self.__key_events = { 'any': [] } # maps key to [raw handler, _EventWrapper[]]

        def on_key(key, src):
            if src is not self.__tk_canvas: return
            with self.__lock:
                for event in self.__key_events.get(key, []) + self.__key_events['any']:
                    event.schedule_no_queueing()
            return 'break'
        self.__tk_canvas.bind('<Tab>', lambda e: on_key('tab', e.widget))
        self.__tk_canvas.bind_all('<Key>', lambda e: on_key(e.keysym.lower(), e.widget))

        self.__mouse_down_events = []
        self.__mouse_up_events = []

        def on_mouse(e, events):
            if e.widget is not self.__tk_canvas: return

            logical_size = _np.array(self.logical_size)
            physical_size = _np.array([self.__tk_canvas.winfo_width(), self.__tk_canvas.winfo_height()])
            scale = min(physical_size / logical_size)
            raw_pos = _np.array([e.x, e.y])
            x, y = (raw_pos - physical_size / 2) / scale * _np.array([1, -1])

            for event, anywhere in events:
                should_handle = True
                wrapped = event.wrapped()
                obj = getattr(wrapped, '__self__', None)
                if isinstance(obj, TurtleBase) and not anywhere:
                    obj_disp_img = getattr(obj, '_TurtleBase__display_image')
                    should_handle = _intersects((obj_disp_img, *obj.pos), (_CURSOR_KERNEL, x, y))

                if should_handle: event.schedule_no_queueing(x, y)

            return 'break'
        self.__tk_canvas.bind_all('<Button-1>', lambda e: on_mouse(e, self.__mouse_down_events))
        self.__tk_canvas.bind_all('<ButtonRelease-1>', lambda e: on_mouse(e, self.__mouse_up_events))

        self.__tk_canvas.focus_set() # grab focus so we can get key events (click events work either way)

    def get_image(self) -> Image.Image:
        with self.__lock:
            return self.__last_frame.copy()
    def get_drawings(self) -> Image.Image:
        with self.__lock:
            return self.__drawings_img.copy()

    def get_uv_mapper(self,) -> Callable:
        w, h = self.logical_size
        def mapper(pos: Tuple[float, float]) -> Tuple[float, float]:
            return (w / 2 + pos[0], h / 2 - pos[1])
        return mapper

    def invalidate(self) -> None:
        self.__needs_redraw = True

    @property
    def logical_size(self) -> Tuple[int, int]:
        return self.__logical_size
    @logical_size.setter
    def logical_size(self, new_size: Tuple[int, int]) -> None:
        width, height = new_size
        with self.__lock:
            self.__logical_size = (width, height)
            self.clear_drawings() # invalidates project internally

    @property
    def turtles(self) -> List[Any]:
        with self.__lock:
            return [x['obj'] for x in self.__turtles.values()]

    def register_entity(self, ent):
        if isinstance(ent, StageBase): target = self.__stages
        elif isinstance(ent, TurtleBase): target = self.__turtles
        else: raise TypeError(f'expected stage or turtle - got {type(ent)}')

        with self.__lock:
            id = len(target)
            setattr(ent, '_Project__id', id)
            target[id] = { 'obj': ent, 'id': id }
        self.invalidate()

    def render_frame(self):
        if not self.__needs_redraw: return
        self.__needs_redraw = False

        logical_size = self.__logical_size
        frame = Image.new('RGBA', logical_size, (255, 255, 255))

        with self.__lock:
            for info in self.__stages.values():
                stage_img = info['obj'].costume
                if stage_img is None: continue

                scale = min(logical_size[i] / stage_img.size[i] for i in range(2))
                new_size = tuple(round(v * scale) for v in stage_img.size)
                resized = stage_img.resize(new_size, Image.ANTIALIAS)
                center_offset = tuple(round((frame.size[i] - new_size[i]) / 2) for i in range(2))
                frame.paste(resized, center_offset, resized)

            frame.paste(self.__drawings_img, (0, 0), self.__drawings_img)

            for info in self.__turtles.values():
                turtle = info['obj']
                if not turtle.visible: continue

                turtle_pos = list(turtle.pos)
                turtle_pos[1] = -turtle_pos[1]
                turtle_img = getattr(turtle, '_TurtleBase__display_image')
                paste_pos = tuple(round(logical_size[i] / 2 + turtle_pos[i] - turtle_img.size[i] / 2) for i in range(2))
                frame.paste(turtle_img, paste_pos, turtle_img)

                say_img = getattr(turtle, '_TurtleBase__say_img')
                if say_img is not None:
                    say_pos = (paste_pos[0] + turtle_img.width, paste_pos[1] - say_img.height)
                    frame.paste(say_img, say_pos, say_img)

            self.__last_frame = frame # keep track of this for the image grab functions

        canvas_size = (self.__tk_canvas.winfo_width(), self.__tk_canvas.winfo_height())
        final_scale = min(canvas_size[i] / logical_size[i] for i in range(2))
        final_size = tuple(round(v * final_scale) for v in frame.size)
        final_frame = ImageTk.PhotoImage(frame.resize(final_size, Image.ANTIALIAS))
        self.__last_cached_frame = final_frame # we have to keep a ref around or it'll disapper

        self.__tk_canvas.delete('all')
        self.__tk_canvas.create_image(canvas_size[0] / 2, canvas_size[1] / 2, image = final_frame)

    def draw_line(self, start: Tuple[float, float], stop: Tuple[float, float], color: Tuple[int, int, int], width: float, *, critical: Optional[Callable]) -> None:
        xy2uv = self.get_uv_mapper()
        start, stop = [tuple(map(round, xy2uv(x))) for x in [start, stop]]
        if width < 0.5: return

        with self.__lock:
            ctx = ImageDraw.Draw(self.__drawings_img)
            ctx.line([start, stop], fill = color, width = round(width))

            # ImageDraw.line's curve joint mode is broken, so we'll implement it ourselves
            if width >= 5:
                r = width / 2 - 0.125
                for c in [start, stop]:
                    ctx.ellipse([_math.ceil(c[0] - r), _math.ceil(c[1] - r), _math.floor(c[0] + r), _math.floor(c[1] + r)], fill = color)

            if critical is not None: critical()
        self.invalidate()

    def draw_text(self, pos: Tuple[float, float], rot: float, text: str, size: float, color: Tuple[int, int, int], *, critical: Optional[Callable] = None) -> float:
        xy2uv = self.get_uv_mapper()
        text_img = _render_text(text, size, color)
        res = float(text_img.width)

        rot_img = text_img.rotate((0.25 - rot) * 360, expand = True)
        ang = (0.25 - rot) * 2 * _math.pi
        radial = _np.array([_math.cos(ang), _math.sin(ang)])
        tangent = _np.array([-radial[1], radial[0]])
        center = xy2uv(tuple(_np.array(pos) + radial * (res / 2) + tangent * (text_img.height / 2)))
        paste_pos = tuple(round(center[i] - rot_img.size[i] / 2) for i in range(2))

        with self.__lock:
            self.__drawings_img.paste(rot_img, paste_pos, rot_img)
            if critical is not None: critical(res)
        self.invalidate()
        return res

    def stamp_img(self, pos: Tuple[float, float], img: Image.Image) -> None:
        xy2uv = self.get_uv_mapper()
        paste_pos = xy2uv(pos)
        paste_pos = tuple(round(paste_pos[i] - img.size[i] / 2) for i in range(2))

        with self.__lock:
            self.__drawings_img.paste(img, paste_pos, img)
        self.invalidate()

    def clear_drawings(self) -> None:
        with self.__lock:
            self.__drawings_img = Image.new('RGBA', self.__logical_size)
        self.invalidate()

    def add_key_event(self, key: str, event: Callable) -> None:
        with self.__lock:
            if key not in self.__key_events:
                self.__key_events[key] = []
            self.__key_events[key].append(_events.get_event_wrapper(event))

    def add_mouse_event(self, mode: Tuple[str, bool], event: Callable) -> None:
        when, anywhere = mode

        target = None
        if when == 'down': target = self.__mouse_down_events
        elif when == 'up': target = self.__mouse_up_events
        else: raise ValueError(f'unknown mouse trigger: "{when}"')

        with self.__lock:
            target.append((_events.get_event_wrapper(event), anywhere))

    def run(self):
        renderer = _traceback_wrapped(self.render_frame)
        def render_loop():
            if not _game_running: return
            renderer()
            self.__tk.after(_RENDER_PERIOD, render_loop)
        render_loop()

        def process_queue():
            if _game_stopped:
                self.__tk.destroy()
                return

            for _ in range(_ACTION_MAX_PER_SLICE):
                if _action_queue.qsize() == 0: break
                val = _action_queue.get()
                if len(val) == 2: val[0](*val[1])
                else:
                    ret = None
                    try: ret = val[0](*val[1])
                    except Exception as e: ret = e

                    with _action_queue_ret_cv:
                        _action_queue_ret_vals[val[2]] = ret
                        _action_queue_ret_cv.notify_all()
            self.__tk.after(_ACTION_QUEUE_INTERVAL, process_queue)
        def starter():
            _start_signal.send()
            process_queue()
        self.__tk.after(100, starter) # give time for main window to open

        self.__tk.mainloop()

_proj_handle_obj = None
_proj_handle_lock = _threading.Lock()
def _get_proj_handle():
    global _proj_handle_obj, _proj_handle_lock
    if _proj_handle_obj is not None: return _proj_handle_obj
    with _proj_handle_lock: # double checked lock for speed
        if _proj_handle_obj is None:
            _proj_handle_obj = _Project(logical_size = (1080, 720), physical_size = (1080, 720))
    return _proj_handle_obj

def start_project():
    '''
    Run turtle game logic.
    Turtles begin running as soon as they are created,
    but you must call this function for them to start moving around and interacting.
    This must be called from the main thread (global scope), not from within a turtle.

    The game can manually be stopped by calling stop_project() (e.g., from a turtle).

    Trying to start a game that is already running results in a ProjectStateError.
    '''
    global _game_running, _game_stopped
    if _game_running: raise ProjectStateError('start_project() was called when the project was already running')
    if _game_stopped: raise ProjectStateError('start_project() was called when the project had previously been stopped')
    _game_running = True

    proj = _get_proj_handle()
    proj.run()

def stop_project():
    '''
    Stops a game that was previously started by start_project().

    Multiple calls to stop_project() are allowed.
    '''
    global _game_running, _game_stopped
    if _game_running:
        _game_running = False # just mark game as stopped - process queue will kill the window when it gets a chance
        _game_stopped = True
    _watch_kill_permanently()

def _qinvoke_defer(fn, *args) -> None:
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

    if isinstance(ret_val, Exception): raise ret_val
    return ret_val

_CURSOR_KERNEL = Image.new('RGBA', (3, 3), 'black') # used for cursor click collision detection on sprites - should be roughly circleish

def _turtle_image(color: Tuple[int, int, int], scale: float) -> Image.Image:
    scale *= 1.25
    w, h = round(32 * scale), round(18 * scale)
    img = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(img)
    draw.polygon([(0, 0), (w, h / 2), (0, h), (w * 0.25, h / 2)], fill = color, outline = 'black')
    return img

def _apply_transforms(img: Optional[Image.Image], scale: float, rot: float) -> Image.Image:
    if img is None: return None
    w, h = img.size
    img = img.resize((round(w * scale), round(h * scale)))
    return img.rotate((0.25 - rot) * 360, expand = True, resample = Image.BICUBIC)

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
        @onstart()
        def start(self):
            pass

    stage = MyStage() # create an instance of MyStage - start() is executed automatically
    ```
    '''
    def __init__(self):
        try:
            if self.__initialized: return # don't initialize twice (can happen from mixing @stage decorator and explicit StageBase base class)
        except:
            self.__initialized = True

        self.__costume = None

        self.__proj = _get_proj_handle()
        self.__proj.register_entity(self)

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
        self.__proj.invalidate()

    @property
    def size(self) -> Tuple[int, int]:
        '''
        Gets or sets the logical size of the stage (width, height).
        This controls the space in which turtles are visible.
        Higher resolutions mean you can display higher-quality images, but may also slow down the simulation.
        Note that this has nothing to do with the window size.

        ```
        width, height = self.size
        self.size = (1080, 720)
        ```
        '''
        return self.__proj.logical_size
    @size.setter
    def size(self, new_size: Tuple[int, int]) -> None:
        w, h = tuple(map(int, new_size))
        if any(x < 1 for x in (w, h)):
            raise ValueError(f'Attempt to set stage size to {w}x{h}, which is less than the minimum (1x1)')
        self.__proj.logical_size = (w, h) # invalidates project internally

    @property
    def width(self) -> int:
        '''
        Get the width of the stage in pixels.

        ```
        print('width:', self.width)
        ```
        '''
        return self.size[0]

    @property
    def height(self) -> int:
        '''
        Get the height of the stage in pixels.

        ```
        print('height:', self.height)
        ```
        '''
        return self.size[1]

    @property
    def turbo(self) -> bool:
        '''
        Get or set whether or not turbo mode is enabled (for all sprites).
        Turbo mode disables all implicit sleeping between calls to graphical functions like moving turtles.
        If you are doing a lot of graphical operations like movement or drawing, enabling turbo mode will speed it up.

        ```
        stage.turbo = True
        stage.turbo = False
        ```
        '''
        return _do_graphics_sleep
    @turbo.setter
    def turbo(self, value: bool) -> None:
        global _do_graphics_sleep
        _do_graphics_sleep = not bool(value)

    def get_image(self) -> Image.Image:
        '''
        Gets an image of the stage and everything on it, including any drawings.
        This is effectively a snapshot of the entire graphical environment.

        ```
        img = self.get_image()
        ```
        '''
        return self.__proj.get_image()
    def get_drawings(self) -> Image.Image:
        '''
        Gets an image of all the drawings on the stage.
        This includes lines, text, and stamps drawn by sprites, but does not include the sprites themselves or the stage costume.
        The returned image has a transparent background.

        ```
        img = self.get_drawings()
        ```
        '''
        return self.__proj.get_drawings()

def _get_meta_name(obj):
    cls = getattr(obj, '_Derived__DerivedFrom', None)
    return cls.__name__ if cls is not None else 'turtle'

class TurtleBase(_Ref):
    '''
    The base class for any custom turtle.
    Custom turtles should use this as their base class, and additionally use the `@turtle` decorator.

    ```
    @turtle
    class MyTurtle(TurtleBase):
        @onstart()
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

        self.__proj = _get_proj_handle()

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
        self.__say_img = None

        self.__update_costume() # init display image
        self.__proj.register_entity(self)

    def __clone_from(self, src):
        self.__raw_set_pos(*src.pos)        # avoid motion sleep
        self.degrees = src.degrees          # needed for heading
        self.__raw_set_heading(src.heading) # avoid motion sleep
        self.visible = src.visible
        self.costume = src.costume
        self.pen_size = src.pen_size
        self.pen_color = src.pen_color
        self.drawing = src.drawing

    def __update_costume(self):
        src = self.__costume # grab this so it can't change during evaluation (used multiple times)
        self.__display_image = _apply_transforms(src, self.__scale, self.__rot) if src is not None else _apply_transforms(_turtle_image(self.__pen_color, self.__scale), 1.0, self.__rot)
        self.__proj.invalidate()

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

    def watch(self, name: str):
        '''
        Creates a variable watcher which watches the sprite variable with the given name.
        This can be used to visually inspect the value of a sprite variable while the program is running.

        ```
        self.my_var = 7
        self.watch('my_var')
        ```
        '''
        my_name = _get_meta_name(self)
        getattr(self, name) # make sure a variable with this name exists
        watch(f'{my_name}\'s {name}', getter = lambda: getattr(self, name))

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
        self.__update_costume() # invalidates project internally

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
        self.__update_costume() # invalidates project internally

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
        self.__raw_set_pos(*map(float, new_pos))
        _graphics_sleep()
    def __raw_set_pos(self, x: float, y: float) -> None:
        if self.drawing:
            def updater():
                self.__x, self.__y = x, y
            self.__proj.draw_line((self.__x, self.__y), (x, y), self.__pen_color, self.__pen_size, critical = updater)
        else:
            self.__x, self.__y = x, y
            self.__proj.invalidate()

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
        self.pos = (float(new_x), self.__y)

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
        self.pos = (self.__x, float(new_y))

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
        self.__raw_set_heading(float(new_heading))
        _graphics_sleep()
    def __raw_set_heading(self, heading: float) -> None:
        self.__rot = (heading / self.__degrees) % 1.0
        self.__update_costume() # invalidates project internally

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
        self.__proj.invalidate()

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

        if self.__costume is None:
            self.__update_costume() # invalidates project internally

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
        self.pos = (self.__x + _math.sin(h) * distance, self.__y + _math.cos(h) * distance) # invalidates project internally

    def turn_left(self, angle: float = None) -> None:
        '''
        Turn the turtle to the left by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_left(45)
        ```
        '''
        self.heading -= float(angle) if angle is not None else self.__degrees / 4 # invalidates project internally
    def turn_right(self, angle: float = None) -> None:
        '''
        Turn the turtle to the right by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_right(45)
        ```
        '''
        self.heading += float(angle) if angle is not None else self.__degrees / 4 # invalidates project internally

    # -------------------------------------------------------

    def clear(self) -> None:
        '''
        Clears (erases) all of the drawings made by this turtle.

        ```
        self.clear()
        ```
        '''
        self.__proj.clear_drawings() # invalidates project internally

    def stamp(self) -> None:
        '''
        Stamps an image of the turtle on the background at the current position.
        Stamps can be deleted by calling `self.clear_stamps()` (just stamps) or `self.clear()` (all drawings).

        ```
        self.stamp()
        ```
        '''
        self.__proj.stamp_img((self.__x, self.__y), self.__display_image)

    def write(self, text: str, *, size: float = 12, move = True):
        '''
        Draws text onto the background.
        The `size` argument sets the font size of the drawn text.
        The `move` argument specifies if the turtle should move to the end of the text after drawing.

        Text counts as a drawing, so it can be erased by calling `self.clear()`.

        ```
        self.write('normal hello world!')
        self.write('small hello world!', size = 8)
        ```
        '''
        self.__proj.draw_text((self.__x, self.__y), self.__rot, str(text), float(size), self.__pen_color, critical = self.forward if move else None)

    def say(self, text: str = '', *, duration: Optional[float] = None) -> None:
        '''
        Causes the sprite to show a message bubble on the display with the given content.
        The message bubble will follow the sprite around as it moves on the display.
        You can get rid of the message by saying an empty string (the default value).

        If `duration` is provided, the sprite will say the message for the given duration (in seconds) and then clear it.
        Note that this will block (wait) for that length of time to elapse before returning.

        ```
        self.say('hello world')
        self.say('something else', duration = 2)
        ```
        '''
        text = str(text)
        if text == '':
            self.__say_img = None
            self.__proj.invalidate()
            return

        lines = _common.paginate_str(text, _SAY_PAGINATE_LEN)
        if len(lines) > _SAY_PAGINATE_MAX_LINES:
            lines = lines[:_SAY_PAGINATE_MAX_LINES-1] + ['...']
        imgs = [_render_text(x, size = 8, color = (0, 0, 0)) for x in lines]
        maxw = max(x.width for x in imgs)
        padding = 8
        line_spacing = 3

        res_size = (maxw + 2 * padding, sum(x.height for x in imgs) + max(len(imgs) - 1, 0) * line_spacing + 2 * padding)
        res = Image.new('RGBA', res_size)
        draw = ImageDraw.Draw(res)
        draw.rounded_rectangle((0, 0, res.width - 1, res.height - 1), fill = (255, 255, 255), outline = (150, 150, 150), width = 3, radius = 10)
        hpos = padding
        for img in imgs:
            paste_pos = (round((maxw - img.width) / 2) + padding, hpos)
            res.paste(img, paste_pos, img)
            hpos += img.height + line_spacing

        self.__say_img = res
        self.__proj.invalidate()

        if duration is not None:
            _time.sleep(float(duration))
            self.__say_img = None
            self.__proj.invalidate()

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

        return self.__visible and other.__visible and _intersects(
            (self.__display_image, self.__x, self.__y),
            (other.__display_image, other.__x, other.__y))
    def get_all_touching(self) -> List[Any]:
        '''
        Gets a list of all the turtles that this turtle is touching, other than itself.

        ```
        touch_count = len(self.get_all_touching())
        ```
        '''
        return [other for other in self.__proj.turtles if other is not self and self.is_touching(other)]

class _CloneTag:
    def __init__(self, src):
        self.src = src

def _derive(bases, cls):
    limited_bases = [b for b in bases if not issubclass(cls, b)]
    class Derived(*limited_bases, cls):
        def __init__(self, *args, **kwargs):
            self.__Derived = Derived
            self.__DerivedFrom = cls
            for base in bases:
                base.__init__(self)

            self.__proj = None
            for base in bases:
                self.__proj = getattr(self, f'_{base.__name__}__proj', None)
                if self.__proj is not None: break
            if self.__proj is None: self.__proj = _get_proj_handle()

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

            exec_start_tag = 'clone' if self.__is_clone else 'original'
            start_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                for key in getattr(start_script, '__run_on_start'):
                    if key == exec_start_tag: _start_safe_thread(start_script)

            key_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_key'))
            for _, key_script in key_scripts:
                for key in getattr(key_script, '__run_on_key'):
                    self.__proj.add_key_event(key, key_script)

            click_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_click'))
            for _, click_script in click_scripts:
                for key in getattr(click_script, '__run_on_click'):
                    self.__proj.add_mouse_event(key, click_script)

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

    You can use the `@onstart()` decorator on any method definition to make it run when a turtle of this type is created.

    ```
    @turtle
    class MyTurtle(TurtleBase):
        @onstart()
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

    You can use the `@onstart()` decorator on any method definition to make it run when a stage of this type is created.

    ```
    @stage
    class MyStage(StageBase):
        @onstart()
        def start(self):
            print('stage starting')
    ```
    '''
    return _derive([StageBase], cls)

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

def onstart(*, when: str = 'original'):
    '''
    The `@onstart()` decorator can be applied to a method definition inside a stage or turtle
    to make that function run whenever the stage/turtle is created.

    The `when` keyword argument controls when the function should be called.
    The following options are available:
     - 'original' (default) - run when the original (non-clone) sprite is created. This mode can also be used on stage methods or global functions.
     - 'clone' - run when a clone is created. Note that clone mode should only be used on a sprite method.

    ```
    @onstart()
    def start(self):
        self.forward(75)

    @onstart(when = 'clone')
    def cloned(self):
        self.pos = (0, 0)
    ```
    '''
    if when not in ['original', 'clone']:
        raise ValueError(f'Unknown @onstart() when mode - got "{when}", expected "original" or "clone"')
    return _add_gui_event_wrapper('__run_on_start', lambda _, f: _start_safe_thread(f), [when])

_KEYSYM_MAPS = { # anything not listed here passes through as-is (lower case)
    'up arrow': ['up'],
    'arrow up': ['up'],
    'right arrow': ['right'],
    'arrow right': ['right'],
    'down arrow': ['down'],
    'arrow down': ['down'],
    'left arrow': ['left'],
    'arrow left': ['left'],

    'pageup': ['prior'],
    'page up': ['prior'],
    'pagedown': ['next'],
    'page down': ['next'],

    'return': ['return', 'kp_enter'],
    'enter': ['return', 'kp_enter'],
    '\n': ['return', 'kp_enter'],
    '\t': ['tab'],

    'capslock': ['caps_lock'],
    'caps lock': ['caps_lock'],
    'numlock': ['num_lock'],
    'num lock': ['num_lock'],
    'scrolllock': ['scroll_lock'],
    'scroll lock': ['scroll_lock'],

    'alt': ['alt_l', 'alt_r'],
    'left alt': ['alt_l'],
    'right alt': ['alt_r'],

    'shift': ['shift_l', 'shift_r'],
    'left shift': ['shift_l'],
    'right shift': ['shift_r'],

    'control': ['control_l', 'control_r'],
    'ctrl': ['control_l', 'control_r'],
    'left control': ['control_l'],
    'left ctrl': ['control_l'],
    'right control': ['control_r'],
    'right ctrl': ['control_r'],

    'esc': ['escape'],
    ' ': ['space'],

    'minus': ['minus', 'kp_subtract'],
    '-': ['minus', 'kp_subtract'],
    'plus': ['plus', 'kp_add'],
    '+': ['plus', 'kp_add'],

    '0': ['0', 'kp_0'],
    '1': ['1', 'kp_1'],
    '2': ['2', 'kp_2'],
    '3': ['3', 'kp_3'],
    '4': ['4', 'kp_4'],
    '5': ['5', 'kp_5'],
    '6': ['6', 'kp_6'],
    '7': ['7', 'kp_7'],
    '8': ['8', 'kp_8'],
    '9': ['9', 'kp_9'],

    'any key': ['any'],
}
def onkey(*keys: str):
    '''
    The `@onkey()` decorator can be applied to a function at global scope
    or a method definition inside a stage or turtle
    to make that function run whenever the user presses a key on the keyboard.

    The special `'any'` or `'any key'` values (equivalent) can be used to catch any key press.

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
        key = key.lower()
        mapped_keys.extend(_KEYSYM_MAPS.get(key, [key]))
    proj =  _get_proj_handle()
    return _add_gui_event_wrapper('__run_on_key', proj.add_key_event, mapped_keys)

def onclick(*, when: str = 'down', anywhere: bool = False):
    '''
    The `@onclick()` decorator can be applied to a function to make it run
    when a user clicks on the turtle or display.
    The function you apply it to will receive the `x` and `y` position of the click.

    When used on sprite methods, by default this will only be triggered when the user
    clicks on the sprite itself, rather than anywhere on the display.
    If you want a sprite method to run when clicking anywhere on the display,
    pass the `anywhere = True` keyword argument (see examples below).

    The `when` keyword argument controls when the function is called - there are the following options:
     - 'down' (default) - run when the mouse button is pressed down.
     - 'up' - run when the mouse button is released.

    ```
    @onclick()
    def mouse_click_1(self, x, y):
        pass

    @onclick(anywhere = True)
    def mouse_click_2(self, x, y):
        pass

    @onclick(when = 'up')
    def mouse_click_3(self, x, y):
        pass
    ```
    '''
    if when not in ['down', 'up']:
        raise ValueError(f'Unknown @onclick when mode: "{when}". Expected "down" or "up".')
    proj = _get_proj_handle()
    return _add_gui_event_wrapper('__run_on_click', proj.add_mouse_event, [(when, anywhere)])

_WATCH_UPDATE_INTERVAL = 500
_watch_tk = None
_watch_tree = None
_watch_watchers = {}
_watch_changed = False
_watch_started = False
_watch_killed_permanently = False
def _watch_update() -> None:
    global _watch_tk, _watch_watchers, _watch_changed, _watch_tree
    if not _watch_changed and len(_watch_watchers) == 0: return
    _watch_changed = False

    open_paths = set()
    def compute_open_paths(root, root_path):
        for child in _watch_tree.get_children(root):
            info = _watch_tree.item(child)
            child_path = f'{root_path}@?{info["text"]}'
            if info['open']:
                open_paths.add(child_path)
            compute_open_paths(child, child_path)

    if _watch_tk is None:
        _watch_tk = _tk.Tk()
        _watch_tk.protocol('WM_DELETE_WINDOW', _watch_kill_permanently)
        _watch_tk.title('PyBlox Watchers')
        _watch_tk.geometry('400x300')

        _watch_tree = _ttk.Treeview(_watch_tk, columns = 1, show = 'tree')
        scroll = _tk.Scrollbar(_watch_tk, command = _watch_tree.yview)
        _watch_tree.configure(yscrollcommand = scroll.set)

        scroll.pack(side = _tk.RIGHT, fill = _tk.Y, expand = True)
        _watch_tree.pack(fill = _tk.BOTH, expand = True)
    else:
        compute_open_paths(None, '') # record open paths before we delete them
        _watch_tree.delete(*_watch_tree.get_children())

    iid_pos = [-1]
    def get_iid():
        iid_pos[0] += 1
        return iid_pos[0]
    def add_value(parent_path: str, text: str, value: Any, *, parent: Union[Tuple[int, int], None] = None):
        my_path = f'{parent_path}@?{text}'
        is_open = my_path in open_paths
        iid = get_iid()

        t = type(value)
        if t is list or t is tuple:
            _watch_tree.insert('', _tk.END, iid = iid, text = text, open = is_open, values = [f'{t.__name__} ({len(value)} items)'])
            for i, v in enumerate(value):
                add_value(my_path, f'item {i}', v, parent = (iid, i))
        elif t is dict:
            _watch_tree.insert('', _tk.END, iid = iid, text = text, open = is_open, values = [f'{t.__name__} ({len(value)} items)'])
            for i, (k, v) in enumerate(value.items()):
                add_value(my_path, f'key {repr(k)}', v, parent = (iid, i))
        else:
            _watch_tree.insert('', _tk.END, iid = iid, text = text, open = is_open, values = [repr(value)])

        if parent is not None:
            _watch_tree.move(iid, parent[0], parent[1])

    for name, watcher in _watch_watchers.items():
        add_value('', name, watcher['getter']())

def _watch_start():
    global _watch_started
    if _watch_started: return
    _watch_started = True # no lock needed cause watch functions are all on the ui thread

    if _watch_killed_permanently: return

    def do_update():
        _traceback_wrapped(_watch_update)()
        if _watch_killed_permanently:
            _watch_tk.destroy()
        else:
            _watch_tk.after(_WATCH_UPDATE_INTERVAL, do_update)
    do_update()
def _watch_kill_permanently():
    global _watch_killed_permanently
    _watch_killed_permanently = True

def _watch_add(name: str, getter: Callable, setter: Union[Callable, None]) -> None:
    global _watch_changed

    if type(name) != str:
        raise TypeError(f'watcher name should be a string, got type {type(name)}')
    if name in _watch_watchers:
        raise ValueError(f'a watcher with name \"{name}\" already exists')
    str(getter()) # make sure value is callable and stringifiable

    _watch_watchers[name] = { 'getter': getter, 'setter': setter }
    _watch_changed = True
    _watch_start()

def watch(name: str, *, getter: Optional[Callable] = None, setter: Optional[Callable] = None) -> None:
    '''
    Registers a variable watcher with the given name, which should not already be taken by another watcher.
    If getter is specified, the watcher will watch the value returned by getter (see below).
    Otherwise, the watcher will watch a variable at global scope with the given name.

    getter - A function taking no arguments which gets the up-to-date value to watch each time it is called.
    If not provided, the new watcher will watch a global variable with the same name as the watcher.

    setter - A function taking one argument (new value) which when called updates the value watched by getter.
    If setter is not provided, the watcher will be readonly (users cannot change the value).
    '''
    if getter is None:
        their_globals = _inspect.stack()[1][0].f_globals
        their_globals[name] # make sure a global with that name exists
        getter = lambda: their_globals[name]
    _qinvoke_defer(_watch_add, name, getter, setter)

_did_setup_stdio = False
_print_lock = _threading.Lock()
def setup_stdio():
    global _did_setup_stdio
    if _did_setup_stdio: return
    _did_setup_stdio = True

    def new_input(prompt: Any = '?') -> Optional[str]:
        prompt = str(prompt)
        return _qinvoke_wait(lambda: _simpledialog.askstring(title = 'User Input', prompt = prompt))
    _builtins.input = new_input

    old_print = print
    def new_print(*args, **kwargs) -> None:
        with _print_lock:
            old_print(*args, **kwargs)
    _builtins.print = new_print
