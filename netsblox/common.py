#!/user/bin/env python

import threading
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

class Signal:
    '''
    A signal is a tool that can be used to control program execution.
    A program can wait() for other code to send() the signal before continuing.
    You can later clear() the signal to reset it to the initial state.

    For instance, this can be used to pause the main thread while message handlers work in the background.
    This is especially useful in Google Colab, as visible execution stops when the main thread stops.
    '''
    def __init__(self):
        self._cv = threading.Condition(threading.Lock())
        self._signal = False

    def clear(self):
        '''
        Clears the signal to the initial not-sent state so that it can be reused.
        '''
        with self._cv:
            self._signal = False
    def send(self):
        '''
        Sends the signal for waiting threads to resume execution.
        '''
        with self._cv:
            self._signal = True
            self._cv.notify_all()
    def wait(self):
        '''
        Waits for other code to send() the signal.
        If the signal has already been sent (but not cleared), this returns immediately.

        This can be used in place of wait_till_disconnect() on a NetsBlox client instance
        if you want the same behavior without actually having to disconnect the client.

        Note: you should avoid calling this from a message handler (or any function a message handler calls),
        as that would suspend the thread that handles messages.
        '''
        with self._cv:
            while not self._signal:
                self._cv.wait()
