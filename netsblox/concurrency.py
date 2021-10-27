import threading as _threading
import time as _time

from typing import Any

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

# maps thread id to warp counter
# because we use raii and split on thread id, these are basically thread-local, so no mutex needed
_warp_counters = {}
def is_warping() -> bool:
    '''
    Checks if the caller is currently warping.
    You can begin warping by creating a new instance of `Warp` and using it in a `with` clause:

    ```
    with Warp():
        print('should be true:', is_warping())
    ```
    '''
    tid = _threading.current_thread().ident
    return _warp_counters.get(tid, 0) > 0

class Warp:
    '''
    This type can be used in a `with` clause to put the current thread into "warping" mode.
    While a thread is warping, it will ignore most default yield points.
    When you enter warp mode, you should always create a new instance of `Warp`, rather than reusing one.

    ```
    with Warp():
        print('do something during warp')
    ```
    '''
    def __init__(self):
        self.tid = _threading.current_thread().ident
    def __enter__(self):
        _warp_counters[self.tid] = _warp_counters.get(self.tid, 0) + 1
    def __exit__(self, *args):
        v = _warp_counters[self.tid] - 1
        if v != 0:
            _warp_counters[self.tid] = v
        else:
            del _warp_counters[self.tid]

class Mutex:
    '''
    Mutex is short for "Mutual Exclusion" which means that multiple scripts that
    try to access the content will automatically be forced to wait so that only one script has access at a time.

    A Mutex object "wraps" (holds) the actual data that you want to protect.
    When you want to access the data, you need to use the mutex in a `with` clause like so:

    ```
    data_mutex = Mutex([])   # wrap a list
    with data_mutex as data: # access the wrapped data
        data.append(5)
    ```

    Note that the wrapped data object given by a with clause should not be used outside of the with clause.
    Python will allow you to violate this, but it is up to you not to do so.

    If you want to actually overwrite (replace) the wrapped value,
    you can use the `set` function on the mutex, but you must do this within a `with` clause.

    ```
    with data_mutex as data:
        data_mutex.set('something completely different')
    ```
    '''
    def __init__(self, wrapped):
        self.__wrapped = wrapped
        self.__owner = None
        self.__lock = _threading.RLock()

    def __enter__(self):
        self.__lock.acquire()
        self.__owner = _threading.get_ident()
        return self.__wrapped
    def __exit__(self, *args):
        self.__owner = None
        self.__lock.release()

    def set(self, new_value: Any) -> None:
        '''
        Sets the wrapped object to an entirely new value.

        Just like for accessing the wrapped object, you must have the
        mutex in a with clause in order to call this.

        ```
        with data_mutex as data:
            data_mutex.set('something completely different')
        ```
        '''
        if self.__owner != _threading.get_ident():
            raise RuntimeError(f'attempt to use Mutex.set() outside of a with clause')
        self.__wrapped = new_value

_did_yield_setup = False
def setup_yielding() -> None:
    global _did_yield_setup
    if _did_yield_setup:
        return

    old_sleep = _time.sleep
    def new_sleep(t: float) -> None:
        if t > 0:
            return old_sleep(t)
        if not is_warping():
            return old_sleep(0)
    _time.sleep = new_sleep

    _did_yield_setup = True
