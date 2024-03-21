import threading as _threading
import inspect as _inspect
import time as _time

_local = _threading.local()

class Signal:
    '''
    A signal is a tool that can be used to control program execution.
    A program can wait() for other code to send() the signal before continuing.
    You can later clear() the signal to reset it to the initial state.

    For instance, this can be used to pause the main thread while message handlers work in the background.
    This is especially useful in Google Colab, as visible execution stops when the main thread stops.
    '''
    def __init__(self):
        self._cv = _threading.Condition(_threading.Lock())
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

class StepSignal:
    '''
    A StepSignal is similar to Signal except that it only steps forward (cannot be reset).
    When you wait() for a StepSignal, you will be resume after the next step().
    '''
    def __init__(self):
        self._cv = _threading.Condition(_threading.Lock())
        self._value = 0

    def step(self):
        '''
        Step forward and resume anyone who was waiting for the previous step to finish.
        '''
        with self._cv:
            self._value += 1
            self._cv.notify_all()
    def wait(self):
        '''
        Wait until the next step().
        '''
        with self._cv:
            v = self._value
            while self._value <= v:
                self._cv.wait()

def in_no_yield() -> bool:
    '''
    Checks if the caller is currently in no-yield mode.
    You can begin no-yield by creating a new instance of `NoYield` and using it in a `with` clause:

    ```
    with NoYield():
        print('should be true:', in_no_yield())
    ```
    '''
    return getattr(_local, 'no_yield_counter', 0) > 0

_no_yields = {} # map<(file, line), NoYield>
_no_yields_lock = _threading.Lock()

class NoYield:
    '''
    This type can be used in a `with` clause to put the current thread into "no-yield" mode.
    While a thread is in no-yield mode, it will ignore most default yield points.
    When you enter no-yield mode, you should always create a new instance of `NoYield`, rather than reusing one.

    ```
    with NoYield():
        print('do something without yielding')
    ```
    '''
    def __new__(cls):
        caller = _inspect.stack()[1]
        key = (caller.filename, caller.lineno)
        with _no_yields_lock:
            if key in _no_yields: return _no_yields[key]
            res = super(NoYield, cls).__new__(cls)
            res._lock = _threading.Lock()
            _no_yields[key] = res
            return res
    def __enter__(self):
        _local.no_yield_counter = getattr(_local, 'no_yield_counter', 0) + 1
        self._lock.__enter__()
    def __exit__(self, *args):
        _local.no_yield_counter -= 1
        self._lock.__exit__()

_did_yield_setup = False
def setup_yielding() -> None:
    global _did_yield_setup
    if _did_yield_setup:
        return

    old_sleep = _time.sleep
    def new_sleep(t: float) -> None:
        if t > 0:
            return old_sleep(t)
        if not in_no_yield():
            return old_sleep(0)
    _time.sleep = new_sleep

    _did_yield_setup = True

if __name__ == '__main__':
    w1 = NoYield() ; w2 = NoYield()
    w3 = NoYield()
    w4, w5 = NoYield(), NoYield()
    assert w1 is w2 and w4 is w5
    assert w1 is not w3 and w3 is not w4