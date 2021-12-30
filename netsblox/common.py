#!/user/bin/env python

import randomname as _randomname
import requests as _requests
import inspect as _inspect
import base64 as _base64
import json as _json
import io as _io

from PIL import Image as _Image

from typing import Tuple, List

class UnavailableService(Exception):
    pass
class NotFoundError(Exception):
    pass
class InvokeError(Exception):
    pass
class ServerError(Exception):
    pass

def generate_proj_id() -> str:
    return f'py-{_randomname.get_name()}'

def small_json(obj):
    return _json.dumps(obj, separators=(',', ':'))

def prep_send(val):
    if val is None:
        return '' # NetsBlox expects empty string for no value
    t = type(val)
    if t == list or t == tuple:
        return [prep_send(v) for v in val]
    elif t == dict:
        return [[prep_send(k), prep_send(v)] for k,v in val.items()]
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

        if len(res[-1]) + len(word) <= max_len: res[-1] += word
        else: res.append(word)
    return res

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
    assert_eq(paginate_str('hello world', 10), ['hello ', 'world'])
    assert_eq(paginate_str('hello world this is a long message', 15), ['hello world ', 'this is a long ', 'message'])
    assert_eq(paginate_str('hello world this is a long message', 16), ['hello world this', ' is a long ', 'message'])
    assert_eq(paginate_str('hello world this is a long message', 17), ['hello world this ', 'is a long message'])
    assert_eq(paginate_str('empty                     space', 10), ['empty     ', '          ', '      ', 'space'])

    if failures[0] != 0:
        print(f'FAILED TESTS: {failures[0]}', file = sys.stderr)
        sys.exit(1)
    print(f'passed all {total[0]} tests')
