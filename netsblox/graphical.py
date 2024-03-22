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

from typing import Any, Union, Tuple, Optional, List, Callable, Sequence, Dict

from PIL import Image, ImageTk, ImageDraw, ImageFont

_INITIAL_SIZE = (1080, 720)

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
_SAY_PAGINATE_LEN = 30 # max length of a paginated line in sprite.say()
_SAY_PAGINATE_MAX_LINES = 8 # max number of lines to show before ...-ing the rest

_SECRET_CENTER_FIELD_NAME = '__nb_cst_center' # field name of our secret center point on an image
_SECRET_DELTA_FIELD_NAME = '__nb_cst_delta' # field name pf our secret delta point on an image

def set_center(img: Image.Image, center: Tuple[float, float]) -> Image.Image:
    '''
    Sets the center point of the image when used as a sprite costume.
    Returns the same image, but with its center point updated.
    '''
    assert len(center) == 2, f'center must be a pair of numbers'
    assert isinstance(img, Image.Image), f'expected an image, got {type(img)}'
    setattr(img, _SECRET_CENTER_FIELD_NAME, (float(center[0]), float(center[1])))
    return img
def get_center(img: Image.Image) -> Tuple[float, float]:
    '''
    Gets the current center point of the image when used as a sprite costume.
    This can get set with `set_center`.
    '''
    assert isinstance(img, Image.Image), f'expected an image, got {type(img)}'
    return getattr(img, _SECRET_CENTER_FIELD_NAME, (0.0, 0.0))

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
    a_delta, b_delta = getattr(a[0], _SECRET_DELTA_FIELD_NAME, (0, 0)), getattr(b[0], _SECRET_DELTA_FIELD_NAME, (0, 0))
    other_center_x = float((b[1] + b_delta[0]) - (a[1] + a_delta[0]))
    other_center_y = -float((b[2] + b_delta[1]) - (a[2] + a_delta[1]))
    other_x = base.width / 2 + other_center_x - other.width / 2
    other_y = base.height / 2 + other_center_y - other.height / 2

    other_trans = Image.new('L', base.size, 0)
    other_trans.paste(other, (round(other_x), round(other_y)))

    return _np.bitwise_and(_np.array(base) >= _VIS_THRESH, _np.array(other_trans) >= _VIS_THRESH).any()

def _render_text(text: str, size: float, color: Tuple[int, int, int]) -> Image.Image:
    if len(text) == 0:
        return Image.new('RGBA', (1, round(size)))

    font = _get_font().font_variant(size = round(1.5 * size))

    text_mask = font.getmask(text, mode = 'L') # L mode here is 256-depth bitmap for antialiasing (not LTR) (see frombytes below)
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

_KEY_DEBOUNCE_TIME = 0.1 # seconds after key up (with no intervening key down) to register as a true key up event

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
def _map_keys(*keys: str) -> List[str]:
    mapped = []
    for key in keys:
        key = key.lower()
        mapped.extend(_KEYSYM_MAPS.get(key, [key]))
    return mapped

class _KeyManager:
    def __init__(self):
        self.__lock = _threading.RLock()

        self.__keys_down = {} # map<key str, [release timer]>

        self.__key_down_events = { 'any': [] } # map<key str, _EventWrapper[]>
        self.__key_hold_events = { 'any': [] } # map<key str, _EventWrapper[]>
        self.__key_up_events   = { 'any': [] } # map<key str, _EventWrapper[]>

    def add_event(self, keys: List[str], event: Callable, when: List[str]) -> None:
        wrapped = _events.get_event_wrapper(event)
        mapped = _map_keys(*keys)

        mode_map = { 'down': self.__key_down_events, 'hold': self.__key_hold_events, 'up': self.__key_up_events }
        targets = [mode_map[x] for x in set(when)]

        with self.__lock:
            for target in targets:
                for key in mapped:
                    if key not in target:
                        target[key] = []
                    target[key].append(wrapped)

    def raw_key_down(self, key: str) -> None:
        with self.__lock:
            info = self.__keys_down.get(key)
            if info is None:
                target = self.__key_down_events
                self.__keys_down[key] = [None]
            else:
                target = self.__key_hold_events
                if info[0] is not None:
                    info[0].cancel()
                info[0] = None
            events = target.get(key, []) + target['any']
        for event in events:
            event.schedule_no_queueing()

    def raw_key_up(self, key: str) -> None:
        def trigger():
            with self.__lock:
                del self.__keys_down[key]
                target = self.__key_up_events
                events = target.get(key, []) + target['any']
            for event in events:
                event.schedule_no_queueing()
        with self.__lock:
            info = self.__keys_down.get(key)
            if info is not None:
                if info[0] is not None:
                    info[0].cancel()
                info[0] = _threading.Timer(_KEY_DEBOUNCE_TIME, trigger)
                info[0].start()

    def is_key_down(self, key: str) -> bool:
        mapped = _map_keys(key)
        with self.__lock:
            return any(x in self.__keys_down for x in mapped)

class _Project:
    def __init__(self, *, logical_size: Tuple[int, int], physical_size: Tuple[int, int]):
        self.__lock = _threading.RLock()
        self.__stages = {}
        self.__sprites = {}

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

        self.__key_manager = _KeyManager()
        def raw_on_key(key, src, target):
            if src is not self.__tk_canvas: return
            target(key)
            return 'break'
        self.__tk_canvas.bind('<Tab>', lambda e: raw_on_key('tab', e.widget, self.__key_manager.raw_key_down))
        self.__tk_canvas.bind_all('<KeyPress>', lambda e: raw_on_key(e.keysym.lower(), e.widget, self.__key_manager.raw_key_down))
        self.__tk_canvas.bind_all('<KeyRelease>', lambda e: raw_on_key(e.keysym.lower(), e.widget, self.__key_manager.raw_key_up))

        self.__last_mouse_pos = (0, 0)
        self.__mouse_down_events = []
        self.__mouse_up_events = []
        self.__mouse_scroll_up_events = []
        self.__mouse_scroll_down_events = []
        self.__mouse_move_events = []

        def on_mouse(e, events):
            if e.widget is not self.__tk_canvas: return

            logical_size = _np.array(self.logical_size)
            physical_size = _np.array([self.__tk_canvas.winfo_width(), self.__tk_canvas.winfo_height()])
            scale = min(physical_size / logical_size)
            raw_pos = _np.array([e.x, e.y])
            x, y = (raw_pos - physical_size / 2) / scale * _np.array([1, -1])
            self.__last_mouse_pos = (x, y) # cache this for async access by other entities

            for event, anywhere in events:
                should_handle = True
                wrapped = event.wrapped()
                obj = getattr(wrapped, '__self__', None)
                if isinstance(obj, SpriteBase) and not anywhere:
                    obj_disp_img = getattr(obj, '_SpriteBase__display_image')
                    should_handle = _intersects((obj_disp_img, *obj.pos), (_CURSOR_KERNEL, x, y))

                if should_handle: event.schedule_no_queueing(x, y)

            return 'break'
        self.__tk_canvas.bind_all('<Button-1>', lambda e: on_mouse(e, self.__mouse_down_events))
        self.__tk_canvas.bind_all('<ButtonRelease-1>', lambda e: on_mouse(e, self.__mouse_up_events))
        self.__tk_canvas.bind_all('<MouseWheel>', lambda e: on_mouse(e, self.__mouse_scroll_up_events if e.delta > 0 else self.__mouse_scroll_down_events))
        self.__tk_canvas.bind_all('<Button-4>', lambda e: on_mouse(e, self.__mouse_scroll_up_events))
        self.__tk_canvas.bind_all('<Button-5>', lambda e: on_mouse(e, self.__mouse_scroll_down_events))
        self.__tk_canvas.bind_all('<Motion>', lambda e: on_mouse(e, self.__mouse_move_events))

        self.__tk_canvas.focus_set() # grab focus so we can get key events (click events work either way)

    def get_stage(self) -> Optional['StageBase']:
        with self.__lock:
            return self.__stages.get(0)

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
    def mouse_pos(self) -> Tuple[float, float]:
        return self.__last_mouse_pos

    def is_key_down(self, key: str) -> bool:
        return self.__key_manager.is_key_down(key)

    @property
    def sprites(self) -> List[Any]:
        with self.__lock:
            return [x['obj'] for x in self.__sprites.values()]

    def register_entity(self, ent):
        if isinstance(ent, StageBase): target = self.__stages
        elif isinstance(ent, SpriteBase): target = self.__sprites
        else: raise TypeError(f'expected stage or sprite - got {type(ent)}')

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
                resized = stage_img.resize(new_size, _common.get_antialias_mode())
                center_offset = tuple(round((frame.size[i] - new_size[i]) / 2) for i in range(2))
                frame.paste(resized, center_offset, resized)

            frame.paste(self.__drawings_img, (0, 0), self.__drawings_img)

            for info in self.__sprites.values():
                sprite = info['obj']
                if not sprite.visible: continue

                sprite_img = getattr(sprite, '_SpriteBase__display_image')
                d = getattr(sprite_img, _SECRET_DELTA_FIELD_NAME)
                p = sprite.pos
                sprite_pos = (p[0] + d[0], -p[1] - d[1])
                paste_pos = tuple(round(logical_size[i] / 2 + sprite_pos[i] - sprite_img.size[i] / 2) for i in range(2))
                frame.paste(sprite_img, paste_pos, sprite_img)

                say_img = getattr(sprite, '_SpriteBase__say_img')
                if say_img is not None:
                    radius = min(*getattr(sprite.costume, 'size', (40, 22.5))) * sprite.scale / 2 / _math.sqrt(2)
                    say_offset = (radius, -radius - say_img.height)
                    say_pos = tuple(round(logical_size[i] / 2 + sprite_pos[i] + say_offset[i]) for i in range(2))
                    frame.paste(say_img, say_pos, say_img)

            self.__last_frame = frame # keep track of this for the image grab functions

        canvas_size = (self.__tk_canvas.winfo_width(), self.__tk_canvas.winfo_height())
        final_scale = min(canvas_size[i] / logical_size[i] for i in range(2))
        final_size = tuple(round(v * final_scale) for v in frame.size)
        final_frame = ImageTk.PhotoImage(frame.resize(final_size, _common.get_antialias_mode()))
        self.__last_cached_frame = final_frame # we have to keep a ref around or it'll disappear

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

    def add_key_event(self, keys_info: Tuple[str,str], event: Callable) -> None:
        when, keys = keys_info
        self.__key_manager.add_event(keys, event, when)

    def add_mouse_event(self, mode: Tuple[str, bool], event: Callable) -> None:
        when, anywhere = mode

        target = None
        if when == 'down': target = self.__mouse_down_events
        elif when == 'up': target = self.__mouse_up_events
        elif when == 'scroll-down': target = self.__mouse_scroll_down_events
        elif when == 'scroll-up': target = self.__mouse_scroll_up_events
        elif when == 'move': target = self.__mouse_move_events
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
            _proj_handle_obj = _Project(logical_size = _INITIAL_SIZE, physical_size = _INITIAL_SIZE)
    return _proj_handle_obj

def start_project():
    '''
    Run sprite game logic.
    Sprites begin running as soon as they are created,
    but you must call this function for them to start moving around and interacting.
    This must be called from the main thread (global scope), not from within a sprite.

    The game can manually be stopped by calling stop_project() (e.g., from a sprite).

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

_CURSOR_KERNEL = Image.new('RGBA', (3, 3), 'black') # used for cursor click collision detection on sprites - should be roughly circle-ish

def _default_sprite_image(color: Tuple[int, int, int], scale: float) -> Image.Image:
    scale *= 1.25
    w, h = round(32 * scale), round(18 * scale)
    img = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(img)
    draw.polygon([(0, 0), (w, h / 2), (0, h), (w * 0.25, h / 2)], fill = color, outline = 'black')
    return img

def _apply_transforms(img: Optional[Image.Image], scale: float, rot: float) -> Image.Image:
    if img is None: return None
    w, h = img.size
    x, y = get_center(img)
    img = img.resize((round(w * scale), round(h * scale)))
    res = img.rotate((0.25 - rot) * 360, expand = True, resample = Image.BICUBIC)
    t = 2 * (0.25 - rot) * _math.pi
    sin_t = _math.sin(t) * scale
    cos_t = _math.cos(t) * scale
    setattr(res, _SECRET_DELTA_FIELD_NAME, (-x * cos_t + y * sin_t, -y * cos_t - x * sin_t))
    return res

class CostumeSet:
    def __init__(self):
        self.__ordered: List[str] = []
        self.__unordered: Dict[str, Image.Image] = {}

    def clear(self):
        '''
        Removes any defined costumes, effectively starting from scratch.
        '''
        self.__ordered.clear()
        self.__unordered.clear()

    def add(self, name: str, value: Image.Image):
        '''
        Adds a single new costume to the collection of costumes.
        `name` is the name of the costume and `value` is the actual image that should be used.
        '''
        if not isinstance(name, str):
            raise RuntimeError(f'costume name must be a string, got {type(name)}')
        if not isinstance(value, Image.Image):
            raise RuntimeError(f'costume value must be an image, got {type(value)}')
        if name in self.__unordered:
            raise RuntimeError(f'a costume with name \'{name}\' already exists')

        self.__unordered[name] = value
        self.__ordered.append(name)

    def lookup(self, value: Union[int, str, Image.Image, None]) -> Optional[Image.Image]:
        '''
        Attempts to look up a costume from the collection of costumes.
        The value can be specified as any of the following:

         - The name of a previously-added costume (or empty string for no costume)
         - The index of a previously-added costume
         - An image, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no costume
        '''

        if value is None:
            return None

        if isinstance(value, int):
            return self.__unordered[self.__ordered[value]]

        if isinstance(value, str):
            if value == '':
                return None
            if value in self.__unordered:
                return self.__unordered[value]
            raise RuntimeError(f'unknown costume \'{value}\'')

        if isinstance(value, Image.Image):
            return value

        raise RuntimeError(f'costumes must be either a string, int, or image - instead got \'{type(value)}\'')

    def index(self, value: Union[int, str, Image.Image, None], default: Optional[int] = None) -> Optional[int]:
        '''
        Attempts to get the index of provided costume (after lookup).
        If the costume is not found, the default value is returned (or None if not specified).
        '''
        value = self.lookup(value)
        for i, v in enumerate(self.__ordered):
            if self.__unordered[v] is value:
                return i
        return default

    def __len__(self) -> int:
        return len(self.__ordered)

    def __iter__(self) -> Sequence[Image.Image]:
        return (self.__unordered[x] for x in self.__ordered)

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

        self.__costume_set = CostumeSet()
        self.__costume = None

        self.__proj = _get_proj_handle()
        self.__proj.register_entity(self)

    @property
    def costume(self) -> Union[None, Image.Image]:
        '''
        Get or set the current stage costume (background).
        The value can be specified as any of the following:

         - The name of a previously-added costume (or empty string for no costume)
         - The index of a previously-added costume
         - An image, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no costume

        ```
        self.costume = None
        self.costume = img
        self.costume = 2         # assuming at least 3 costumes were already added
        self.costume = 'dog pic' # assuming a costume with this name was already added
        ```
        '''
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Union[None, Image.Image, str, int]) -> None:
        new_costume = self.__costume_set.lookup(new_costume)
        if new_costume is not None:
            assert new_costume.mode == 'RGBA', f'unsupported image encoding: {new_costume.mode}'

        self.__costume = new_costume
        self.__proj.invalidate()

    @property
    def costumes(self) -> CostumeSet:
        '''
        The collection of costumes associated with the stage.
        '''
        return self.__costume_set

    @property
    def size(self) -> Tuple[int, int]:
        '''
        Gets or sets the logical size of the stage (width, height).
        This controls the space in which sprites are visible.
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
    def mouse_pos(self) -> Tuple[float, float]:
        '''
        Gets the last known mouse location.
        Note that the mouse is not tracked outside of the stage window.

        ```
        x, y = self.mouse_pos
        ```
        '''
        return self.__proj.mouse_pos

    def is_key_down(self, key: str) -> bool:
        '''
        Checks if the specified key is currently pressed down.

        If you instead want to receive an event when a key is pressed, held, or released,
        consider using the `@onkey` decorator.

        ```
        is_sneaking = self.is_key_down('shift')
        ```
        '''
        return self.__proj.is_key_down(key)

    @property
    def gps_location(self) -> Tuple[float, float]:
        '''
        Approximates the gps location of this computer.
        Returns a tuple of `(latitude, longitude)`.

        ```
        lat, long = self.gps_location
        ```
        '''
        return _common.get_location()

    @property
    def turbo(self) -> bool:
        '''
        Get or set whether or not turbo mode is enabled (for all sprites).
        Turbo mode disables all implicit sleeping between calls to graphical functions like moving sprites.
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

    def clear_drawings(self) -> None:
        '''
        Clears (erases) all of the drawings on the stage.

        ```
        self.clear()
        ```
        '''
        self.__proj.clear_drawings() # invalidates project internally

def _get_meta_name(obj):
    cls = getattr(obj, '_Derived__DerivedFrom', None)
    return cls.__name__ if cls is not None else 'sprite'

class SpriteBase(_Ref):
    '''
    The base class for any custom sprite.
    Custom sprites should use this as their base class, and additionally use the `@sprite` decorator.

    ```
    @sprite
    class MySprite(SpriteBase):
        @onstart()
        def start(self):
            self.forward(75)

    t = MySprite() # create an instance of MySprite. start() is executed automatically
    ```
    '''
    def __init__(self):
        try:
            if self.__initialized:
                return # don't initialize twice (can happen from mixing @sprite decorator and explicit SpriteBase base class)
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
        self.__costume_set = CostumeSet()
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
        self.__display_image = _apply_transforms(src, self.__scale, self.__rot) if src is not None else _apply_transforms(_default_sprite_image(self.__pen_color, self.__scale), 1.0, self.__rot)
        self.__proj.invalidate()

    def clone(self) -> Any:
        '''
        Create and return a clone (copy) of this sprite.
        The created sprite will have a deep copy of any variables this sprite has set.
        The new sprite will be created at the same position and in the same direction as the current sprite (everything is identical).

        Cloning is a great way to reduce duplicated code.
        If you need many sprites which happen to do the same thing,
        consider writing a single sprite and making it clone itself several times at the beginning.

        ```
        my_clone = self.clone()
        ```
        '''
        Derived = getattr(self, '_Derived__Derived', None)
        if Derived is None:
            raise RuntimeError('Tried to clone a sprite type which was not defined with @sprite')
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

    def get_image(self) -> Image.Image:
        '''
        Gets an image of this sprite, with nothing else and a transparent background.
        This returned image will include effects like color, rotation, and any active graphical effects.

        ```
        img = self.get_image()
        ```
        '''
        return self.__display_image

    @property
    def costume(self) -> Any:
        '''
        Get or set the sprite's costume (image).
        The value can be specified as any of the following:

         - The name of a previously-added costume (or empty string for no costume)
         - The index of a previously-added costume
         - An image, which is returned directly (i.e., no lookup needed)
         - None, which is returned directly (i.e., no lookup needed) and represents no costume

        ```
        self.costume = None
        self.costume = img
        self.costume = 2         # assuming at least 3 costumes were already added
        self.costume = 'dog pic' # assuming a costume with this name was already added
        ```
        '''
        return self.__costume
    @costume.setter
    def costume(self, new_costume: Union[None, Image.Image, str, int]) -> None:
        new_costume = self.__costume_set.lookup(new_costume)
        if new_costume is not None:
            assert new_costume.mode == 'RGBA', f'unsupported image encoding: {new_costume.mode}'

        self.__costume = new_costume
        self.__update_costume() # invalidates project internally

    @property
    def costumes(self) -> CostumeSet:
        '''
        The collection of costumes associated with this sprite.
        '''
        return self.__costume_set

    @property
    def scale(self) -> float:
        '''
        Get or set the current sprite scale (default 1.0).
        Larger values make the sprite larger.

        This should be a positive number.

        ```
        self.scale = 2.5
        ```
        '''
        return self.__scale
    @scale.setter
    def scale(self, new_scale: float) -> None:
        new_scale = float(new_scale)
        if new_scale <= 0:
            raise RuntimeError(f'attempt to set sprite scale to non-positive value: {new_scale}')
        self.__scale = new_scale
        self.__update_costume() # invalidates project internally

    @property
    def pos(self) -> Tuple[float, float]:
        '''
        Get or set the position of the sprite, which is a pair of (x, y) coordinates.

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

    def goto(self, target: Union[Tuple[float, float], Any]) -> None:
        '''
        Goes to the specified location.
        The target can either be a tuple/list of `[x, y]` coordinates, or another sprite.

        ```
        self.goto([15, 23])
        self.goto(other_sprite)
        ```
        '''
        if isinstance(target, list) or isinstance(target, tuple):
            self.pos = target
        else:
            self.pos = target.pos

    @property
    def x_pos(self) -> float:
        '''
        Get or set the x position of the sprite.

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
        Get or set the y position of the sprite.

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
        Get or set the heading (direction) of the sprite.
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

        The apparent heading of the sprite is unchanged - this is just a way of measuring angles.

        ```
        self.degrees = 360         # switch to (normal) degrees mode
        self.degrees = 2 * math.pi # switch to radians mode
        ```
        '''
        return self.__degrees
    @degrees.setter
    def degrees(self, full_circle: float = 360.0) -> None:
        self.__degrees = float(full_circle)

    @property
    def visible(self) -> bool:
        '''
        Get or set whether or not the sprite is visible

        ```
        self.visible = True  # show the sprite
        self.visible = False # hide the sprite
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
        Get or set whether or not the sprite should draw a trail behind it as it moves.

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

        For setting, this can be specified as either a color name like `'red'`, an RGB tuple like `(200, 17, 98)`, or as a hex color code like `'#a0c8f0'`.

        ```
        self.pen_color = 'red'
        self.pen_color = '#a0c8f0'
        self.pen_color = (34, 23, 104)
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
        Turn the sprite to the left by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_left(45)
        ```
        '''
        self.heading -= float(angle) if angle is not None else self.__degrees / 4 # invalidates project internally
    def turn_right(self, angle: float = None) -> None:
        '''
        Turn the sprite to the right by the given angle.
        Note that this is affected by the current degrees mode.
        If no angle is specified, turns the equivalent of 90 degrees.

        ```
        self.turn_right(45)
        ```
        '''
        self.heading += float(angle) if angle is not None else self.__degrees / 4 # invalidates project internally

    def keep_on_stage(self, *, bounce: bool = False) -> None:
        '''
        Moves the sprite to ensure it is entirely within the bounds of the stage/screen.
        If the sprite is not at least partially off the stage/screen, this does nothing.

        It is common to use this immediately after moving the sprite, though this is not required.

        If the `bounce` keyword argument is set to true (default false), in addition to keeping the sprite on the stage,
        the sprite will also be rotated upon "colliding" with a wall to give the appearance of bouncing off the wall.

        ```
        self.forward(10)
        self.keep_on_stage() # no bouncing

        self.forward(10)
        self.keep_on_stage(bounce = True) # bouncing
        ```
        '''
        stage = self.__proj.get_stage()
        if stage is None: return

        logical_size = self.__proj.logical_size
        sprite_pos = self.pos
        sprite_img = self.__display_image
        top_left = tuple(round(logical_size[i] / 2 + sprite_pos[i] - sprite_img.size[i] / 2) for i in range(2))
        box = (top_left[0], top_left[1], top_left[0] + sprite_img.size[0], top_left[1] + sprite_img.size[1])

        h = self.__rot * 2 * _math.pi
        fx, fy = _math.sin(h), _math.cos(h)
        dx, dy = 0, 0

        if box[0] < 0: # left
            dx = -box[0]
            fx = abs(fx)
        elif box[2] > logical_size[0]: # right
            dx = logical_size[0] - box[2]
            fx = -abs(fx)

        if box[3] > logical_size[1]: # top
            dy = logical_size[1] - box[3]
            fy = -abs(fy)
        elif box[1] < 0: # bottom
            dy = -box[1]
            fy = abs(fy)

        self.pos = (self.__x + dx, self.__y + dy) # using pos wrapper so we draw lines
        if bounce: self.heading = (_math.atan2(fx, fy)) / (2 * _math.pi) * self.__degrees

    # -------------------------------------------------------

    def stamp(self) -> None:
        '''
        Stamps an image of the sprite on the background at the current position.
        Stamps can be deleted by calling `self.clear_drawings()`.

        ```
        self.stamp()
        ```
        '''
        self.__proj.stamp_img((self.__x, self.__y), self.__display_image)

    def write(self, text: str, *, size: float = 12, move = True):
        '''
        Draws text onto the background.
        The `size` argument sets the font size of the drawn text.
        The `move` argument specifies if the sprite should move to the end of the text after drawing.

        Text counts as a drawing, so it can be erased by calling `self.clear()`.

        ```
        self.write('normal hello world!')
        self.write('small hello world!', size = 8)
        ```
        '''
        self.__proj.draw_text((self.__x, self.__y), self.__rot, str(text), float(size), self.__pen_color, critical = self.forward if move else None)

    def say(self, *values: Any, duration: Optional[float] = None) -> None:
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
        text = ' '.join([str(x) for x in values])
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
        radius = 10
        res = Image.new('RGBA', res_size)
        draw = ImageDraw.Draw(res)
        draw.rectangle((0, res.height - 1 - radius, radius, res.height - 1), fill = (150, 150, 150))
        draw.rounded_rectangle((0, 0, res.width - 1, res.height - 1), fill = (255, 255, 255), outline = (150, 150, 150), width = 3, radius = radius)
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
        Checks if this sprite is touching the other sprite, that is, they are both visible overlapping.

        ```
        if self.is_touching(other_sprite):
            self.turn_right(180)
        ```
        '''
        if not isinstance(other, SpriteBase):
            raise TypeError(f'Attempt to check if a sprite is touching a non-sprite (type {type(other)})')

        return self.__visible and other.__visible and _intersects(
            (self.__display_image, self.__x, self.__y),
            (other.__display_image, other.__x, other.__y))
    def get_all_touching(self) -> List[Any]:
        '''
        Gets a list of all the sprites that this sprite is touching, other than itself.

        ```
        touch_count = len(self.get_all_touching())
        ```
        '''
        return [other for other in self.__proj.sprites if other is not self and self.is_touching(other)]

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

            exec_start_tag = 'clone' if self.__is_clone else 'now'
            start_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_start'))
            for _, start_script in start_scripts:
                for key in getattr(start_script, '__run_on_start'):
                    if key == exec_start_tag: _start_safe_thread(start_script)

            key_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_key'))
            for _, key_script in key_scripts:
                for key in getattr(key_script, '__run_on_key'):
                    self.__proj.add_key_event(key, key_script)

            mouse_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_mouse'))
            for _, mouse_script in mouse_scripts:
                for key in getattr(mouse_script, '__run_on_mouse'):
                    self.__proj.add_mouse_event(key, mouse_script)

            msg_scripts = _inspect.getmembers(self, predicate = lambda x: _inspect.ismethod(x) and hasattr(x, '__run_on_message'))
            for _, msg_script in msg_scripts:
                for inserter in getattr(msg_script, '__run_on_message'): # client gave us a list of convenient insertion functions
                    inserter(msg_script)

        def __clone_from(self, src):
            def filter_out(name):
                return any(name.startswith(x) for x in ['_Derived_', '_SpriteBase_', '_StageBase_'])
            fields = [x for x in vars(src).keys() if not filter_out(x)]
            for field in fields:
                setattr(self, field, _copy.deepcopy(getattr(src, field)))

            for base in bases: # recurse to child types for specialized cloning logic (like sprite repositioning)
                getattr(self, f'_{base.__name__}__clone_from')(src)

    return Derived

def sprite(cls):
    '''
    The `@sprite` decorator for a class creates a new type of sprite.
    This should be used in conjunction with the `SpriteBase` base class.

    You can use the `@onstart()` decorator on any method definition to make it run when a sprite of this type is created.

    ```
    @sprite
    class MySprite(SpriteBase):
        @onstart()
        def start(self):
            self.forward(75)

    t = MySprite() # create an instance of MySprite - start() is executed automatically
    ```
    '''
    return _derive([SpriteBase], cls)

def stage(cls):
    '''
    The `@stage` decorator for a class creates a new type of stage.
    This should be used in conjunction with the `StageBase` base class.
    Stages function much like the stage in NetsBlox - equivalent to a sprite/sprite except with no movement controls.
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

def onstart(when: str = 'now'):
    '''
    The `@onstart()` decorator can be applied to a method definition inside a stage or sprite
    to make that function run whenever the stage/sprite is created.

    The `when` keyword argument controls when the function should be called.
    The following options are available:
     - 'now' (default) - run immediately when the original (non-clone) sprite is created. This mode can also be used on stage methods or global functions.
     - 'clone' - run when a clone is created. Note that clone mode should only be used on a sprite method.

    ```
    @onstart()
    def start(self):
        self.forward(75)

    @onstart('clone')
    def cloned(self):
        self.pos = (0, 0)
    ```
    '''
    expected = ['now', 'clone']
    if when not in expected:
        raise ValueError(f'Unknown @onstart() when mode - got "{when}", expected: {", ".join(expected)}')
    return _add_gui_event_wrapper('__run_on_start', lambda _, f: _start_safe_thread(f), [when])

def onkey(*keys: str, when: Union[str, List[str]] = ['down', 'hold']):
    '''
    The `@onkey()` decorator can be applied to a function at global scope
    or a method definition inside a stage or sprite
    to make that function run whenever the user presses a key on the keyboard.

    The special `'any'` or `'any key'` values (equivalent) can be used to catch any key press.

    The `when` keyword argument controls when the event should be triggered.
    The following options are available:
     - `'down'` (co-default) - trigger when the key is first pressed down
     - `'hold'` (co-default) - trigger repeatedly when the key is held down
     - `'up` - trigger when the key is released

    To combine multiple `when` modes, you can specify `when` as a list of modes.
    For instance, the default is `when = ['down', 'hold']`.

    ```
    @onkey('space')
    def space_key_pressed():
        stop_project()

    @onkey('w', 'up arrow')
    def w_or_up_arrow_pressed(self):
        self.forward(50)
    ```
    '''
    if isinstance(when, str): when = [when]
    modes = ['down', 'hold', 'up']
    for mode in when:
        if mode not in modes:
            expected = ", ".join(f"\"{x}\"" for x in modes)
            raise ValueError(f'Unknown @onkey when mode: "{mode}". Expected {expected}.')
    proj = _get_proj_handle()
    return _add_gui_event_wrapper('__run_on_key', proj.add_key_event, [(when, keys)])

def onmouse(when: str, *, anywhere: bool = False):
    '''
    The `@onmouse()` decorator can be applied to a global function or sprite/stage method to make it run
    when a user interacts with the sprite or stage with their mouse.
    The function you apply it to will receive the `x` and `y` position of the mouse.

    When used on sprite methods, by default this will only be triggered when the user
    interacts with the sprite itself, rather than anywhere on the display.
    If you want a sprite method to run when interacting anywhere on the display,
    pass the `anywhere = True` keyword argument (see examples below).

    The `when` keyword argument controls when the function is called - there are the following options:
     - 'down' - run when the mouse button is pressed down (clicked).
     - 'up' - run when the mouse button is released (click released).
     - 'scroll-down' - run when the mouse wheel is scrolled down.
     - 'scroll-up' - run when the mouse wheel is scrolled up.
     - 'move' - run any time the mouse moves.

    ```
    @onmouse('down')
    def mouse_down_1(self, x, y):
        pass

    @onmouse('down', anywhere = True)
    def mouse_down_2(self, x, y):
        pass

    @onmouse('scroll-up')
    def mouse_scroll_up(self, x, y):
        pass
    ```
    '''
    modes = ['down', 'up', 'scroll-down', 'scroll-up', 'move']
    if when not in modes:
        expected = ", ".join(f"\"{x}\"" for x in modes)
        raise ValueError(f'Unknown @onmouse when mode: "{when}". Expected {expected}.')
    proj = _get_proj_handle()
    return _add_gui_event_wrapper('__run_on_mouse', proj.add_mouse_event, [(when, anywhere)])

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

        scroll.pack(side = _tk.RIGHT, fill = _tk.Y)
        _watch_tree.pack(side = _tk.RIGHT, fill = _tk.BOTH, expand = True)
    else:
        compute_open_paths(None, '') # record open paths before we delete them
        _watch_tree.delete(*_watch_tree.get_children())

    iid_pos = [-1]
    def get_iid():
        iid_pos[0] += 1
        return iid_pos[0]
    def add_value(parent_path: str, text: str, value: Any, visited: _common.PointerSet, *, parent: Union[Tuple[int, int], None] = None):
        my_path = f'{parent_path}@?{text}'
        is_open = my_path in open_paths
        iid = get_iid()

        t = type(value)
        if t is list or t is tuple or t is dict:
            expand = visited.add(value)
            mod_txt = text if expand else f'{text} (...)'
            _watch_tree.insert('', _tk.END, iid = iid, text = mod_txt, open = is_open, values = [f'{t.__name__} ({len(value)} items)'])
            if expand:
                def over_limit(i: int) -> bool:
                    if i >= 1024:
                        class Ellipses:
                            def __repr__(self): return '...'
                        add_value(my_path, '...', Ellipses(), visited, parent = (iid, i))
                        return True
                    return False
                if t is list or t is tuple:
                    for i, v in enumerate(value):
                        if over_limit(i): break
                        add_value(my_path, f'item {i}', v, visited, parent = (iid, i))
                else:
                    for i, (k, v) in enumerate(value.items()):
                        if over_limit(i): break
                        add_value(my_path, f'key {repr(k)}', v, visited, parent = (iid, i))
                visited.remove(value)
        else:
            _watch_tree.insert('', _tk.END, iid = iid, text = text, open = is_open, values = [repr(value)])

        if parent is not None:
            _watch_tree.move(iid, parent[0], parent[1])

    for name, watcher in _watch_watchers.items():
        add_value('', name, watcher['getter'](), _common.PointerSet())

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
