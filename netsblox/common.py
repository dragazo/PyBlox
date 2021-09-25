#!/user/bin/env python

import inspect
import json

class UnavailableService(Exception):
    pass
class NotFoundError(Exception):
    pass
class InvokeError(Exception):
    pass
class ServerError(Exception):
    pass

def small_json(obj):
    return json.dumps(obj, separators=(',', ':'))

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
    info = inspect.getfullargspec(f)
    return len(info.args) != 0 and info.args[0] == 'self'
