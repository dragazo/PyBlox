import netsblox as _netsblox

import randomname as _randomname
import threading as _threading
import requests as _requests
import difflib as _difflib
import inspect as _inspect
import base64 as _base64
import numpy as _np
import json as _json
import sys as _sys
import io as _io
import os as _os
from PIL import Image as _Image, ImageTk as _ImageTk

from typing import Tuple, List, Any, Optional

_NETSBLOX_PY_PATH = _os.path.dirname(_netsblox.__file__)

class NetsBloxError(Exception):
    'An error from calling a NetsBlox RPC'
    pass

_SCRIPT_CONTEXT = _threading.local()
def get_error() -> Optional[str]:
    '''
    Gets the most recent error from a nothrow function that was run by the calling script, or `None` if there was no error.

    Typically, you want to see errors as exceptions when they happen so as not to let them "hide" in your code.
    However, this is still useful for cases where you want to allow (and ignore errors),
    for instance if you need to call an RPC that might fail, but you don't actually care if it succeeds (or what the return value would be).

    ```
    nothrow(nb.chart.draw)(my_data)
    if get_error() is not None:
        print('uh-oh, there was an error!')
    ```
    '''
    return getattr(_SCRIPT_CONTEXT, 'error', None)

def nothrow(f):
    '''
    A wrapper that can be applied to a function to make it a nothrow variant.
    The most recent error from a nothrow variant is accessible via `get_error()`.
    Additionally, if an error occurs, the return value is the error message string.

    Note that only `NetsBloxError` exceptions are caught in this way - all others are thrown as true (python) exception.

    ```
    # normal (throwing) version
    nb.air_quality.quality_index('invalid', 'input')
    # nothrow version
    nothrow(nb.air_quality.quality_index)('invalid', 'input')
    # you can save the nothrow version
    quality_index = nothrow(nb.air_quality.quality_index)
    quality_index('invalid', 'input')
    ```
    '''
    def wrapped(*args, **kwargs):
        try:
            _SCRIPT_CONTEXT.error = None
            return f(*args, **kwargs)
        except NetsBloxError as e:
            msg = str(e)
            _SCRIPT_CONTEXT.error = msg
            return msg
    return wrapped

def get_antialias_mode():
    # for god knows why, the pillow devs decided to break everything that used Image.ANTIALIAS when they added different resampling modes
    # so we need this wrapper to get whichever one works on the installed version of the package at runtime... eww...
    res = getattr(_Image, 'ANTIALIAS', None)
    return res if res is not None else _Image.Resampling.BICUBIC

def scale_image(img: _Image.Image, scale: float = 1) -> _Image.Image:
    if scale == 1: return img
    new_size = tuple(round(v * scale) for v in img.size)
    return img.resize(new_size, resample = get_antialias_mode())

_img_lock = _threading.Lock()
_img_cache = {}
_error_image = _Image.new('RGB', (50, 50), (252, 3, 244))
def load_image(uri: str) -> _Image.Image:
    img = _error_image
    protocol = uri[:uri.find('://')]
    with _img_lock:
        if uri in _img_cache:
            return _img_cache[uri]
        elif protocol == 'netsblox':
            img = _Image.open(f'{_NETSBLOX_PY_PATH}/{uri[11:]}')
        elif protocol == 'base64':
            return decode_image(uri[9:]) # return so we don't cache local data (also the uri is long)
        elif protocol in ['https', 'http']:
            res = _requests.get(uri)
            if res.status_code == 200:
                img = _Image.open(_io.BytesIO(res.content))
            else:
                print(f'Failed to load image {uri} (error code {res.status_code})\n\nMake sure the web host allows direct downloads.', file = _sys.stderr)
        else:
            print(f'Failed to load image {uri} (unknown protocol)', file = _sys.stderr)

        _img_cache[uri] = img
        return img
def load_tkimage(uri: str, *, scale: float = 1) -> _ImageTk.PhotoImage:
    return _ImageTk.PhotoImage(scale_image(load_image(uri), scale))

_text_lock = _threading.Lock()
_text_cache = {}
def load_text(uri: str) -> str:
    txt = None
    protocol = uri[:uri.find('://')]
    with _text_lock:
        if uri in _text_cache:
            return _text_cache[uri]
        elif protocol == 'netsblox':
            with open(f'{_NETSBLOX_PY_PATH}/{uri[11:]}', 'r') as f:
                txt = f.read()
        elif protocol in ['https', 'http']:
            res = _requests.get(uri)
            if res.status_code == 200:
                txt = res.content
            else:
                raise RuntimeError(f'Failed to download file at {uri} (error code {res.status_code})\n\nMake sure the web host allows direct downloads.')
        else:
            raise RuntimeError(f'Failed to download file at {uri} (unknown protocol)')

        assert txt is not None
        _text_cache[uri] = txt
        return txt

def generate_project_id() -> str:
    return f'_py-{_randomname.get_name()}'

def small_json(obj):
    def prep_value(obj):
        if type(obj) in [list, tuple]:
            return [prep_value(x) for x in obj]
        if type(obj) is dict:
            return { prep_value(k): prep_value(v) for k,v in obj.items() }
        if type(obj) is _np.ndarray:
            return obj.tolist()
        return obj
    return _json.dumps(prep_value(obj), separators=(',', ':'))

def prep_send(val):
    if val is None:
        return '' # NetsBlox expects empty string for no value
    if any(isinstance(val, t) for t in [list, tuple, set]):
        return [prep_send(v) for v in val]
    elif isinstance(val, dict):
        return [[prep_send(k), prep_send(v)] for k,v in val.items()]
    elif isinstance(val, _Image.Image):
        return f'<costume image="data:image/png;base64,{encode_image(val)}"/>'
    else:
        return val

def vectorize(f):
    return lambda v: [f(x) for x in v]

def is_method(f): # inspect.ismethod doesn't work at annotation time, so we use args list directly
    info = _inspect.getfullargspec(f)
    return len(info.args) != 0 and info.args[0] == 'self'

def inclusive_splitlines(src: str) -> List[str]:
    res = src.splitlines()
    if src and src[-1] == '\n':
        res.append('')
    return res

def get_location() -> Tuple[float, float]:
    '''
    Get the current physical location of the client.
    This is returned as a (latitude, longitude) pair.

    Note that an internet connection is required for this to work.
    '''
    res = _requests.post('https://reallyfreegeoip.org/json/', headers = { 'Content-Type': 'application/json' })

    if res.status_code == 200:
        parsed = _json.loads(res.text)
        return parsed['latitude'], parsed['longitude']
    else:
        raise Exception(f'Failed to get location: {res.status_code}\n{res.text}')

def encode_image(img: _Image.Image) -> str:
    res = _io.BytesIO()
    img.save(res, 'png')
    return _base64.b64encode(res.getvalue()).decode('ascii')
def decode_image(img: str) -> _Image.Image:
    raw = _base64.decodebytes(img.encode('ascii'))
    return _Image.open(_io.BytesIO(raw))

def paginate_str(text: str, max_len: int) -> List[str]:
    res = ['']
    pos = 0
    while pos < len(text):
        ch = text[pos]
        if ch.isspace():
            pos += 1
            if ch == '\n': res.append('')
            elif len(res[-1]) + 1 <= max_len: res[-1] += ch
            else: res.append(ch)
            continue

        end = pos + 1
        while end < len(text) and not text[end].isspace():
            end += 1
        word = text[pos:end]
        pos = end

        # if len(res[-1]) == 0: res[-1] = word
        if len(res[-1]) + len(word) <= max_len: res[-1] += word
        else: res.append(word)
    return [x.strip() for x in res]

class PointerSet:
    def __init__(self):
        self.__items = []

    def __len__(self) -> int:
        return len(self.__items)

    def __contains__(self, obj: Any) -> bool:
        return any(x is obj for x in self.__items)

    def add(self, obj: Any) -> bool:
        do_add = obj not in self
        if do_add: self.__items.append(obj)
        return do_add

    def remove(self, obj: Any) -> bool:
        for i in range(len(self.__items)-1,-1,-1):
            if self.__items[i] is not obj: continue
            del self.__items[i]
            return True
        return False

if __name__ == '__main__':
    import sys
    failures = [0]
    total = [0]
    def assert_eq(a, b):
        total[0] += 1
        if a == b: return
        print(f'ASSERTION ERROR: a == b failed\n    a = {a}\n    b = {b}', file = sys.stderr)
        failures[0] += 1

    assert_eq(paginate_str('hello world', 20), ['hello world'])
    assert_eq(paginate_str('hello\nworld', 20), ['hello', 'world'])
    assert_eq(paginate_str('hello\nworld\n', 20), ['hello', 'world', ''])
    assert_eq(paginate_str('hello world', 10), ['hello', 'world'])
    assert_eq(paginate_str('hello world this is a long message', 15), ['hello world', 'this is a long', 'message'])
    assert_eq(paginate_str('hello world this is a long message', 16), ['hello world this', 'is a long', 'message'])
    assert_eq(paginate_str('hello world this is a long message', 17), ['hello world this', 'is a long message'])
    assert_eq(paginate_str('empty                     space', 10), ['empty', '', '', 'space'])
    assert_eq(paginate_str('hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh', 10), ['hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh'])
    assert_eq(paginate_str('h hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh', 10), ['h', 'hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh'])

    ps = PointerSet()
    assert_eq(len(ps), 0)
    x = [1, 2, 3]
    assert x not in ps
    assert_eq(ps.add(x), True)
    assert_eq(len(ps), 1)
    assert_eq(ps.add(x), False)
    assert_eq(x in ps, True)
    assert_eq(len(ps), 1)
    assert_eq(x in ps, True)
    assert_eq('hello'not in ps, True)
    assert_eq('hello' in ps, False)
    assert_eq([1,2,3] not in ps, True)
    assert_eq([1,2,3] in ps, False)
    assert_eq((1,2,3) not in ps, True)
    assert_eq((1,2,3) in ps, False)
    assert_eq(ps.remove([1,2,3]), False)
    assert_eq(len(ps), 1)
    assert_eq(x in ps, True)
    assert_eq(ps.remove(x), True)
    assert_eq(x not in ps, True)
    assert_eq(x in ps, False)
    assert_eq(len(ps), 0)

    foo0 = list(range(10))
    foo1 = [foo0]
    foo2 = [foo1]
    foo0.append(foo2)
    assert_eq(ps.add(foo0), True)
    assert_eq(foo0 in ps, True)
    assert_eq(foo1 in ps, False)
    assert_eq(foo2 in ps, False)

    if failures[0] != 0:
        print(f'FAILED TESTS: {failures[0]}', file = sys.stderr)
        sys.exit(1)
    print(f'passed all {total[0]} tests')

def unified_diff(before: str, after: str, *, n: int = 3) -> str:
    before = [f'{x}\n' for x in before.splitlines()]
    after = [f'{x}\n' for x in after.splitlines()]
    return ''.join(_difflib.unified_diff(before, after, n = n))
