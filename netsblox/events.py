import threading as _threading
import traceback as _traceback
import queue as _queue
import sys as _sys

class EventWrapper:
    def __init__(self, fn):
        self.__fn = fn
        self.__queue = _queue.Queue()
        self.__processing = False

        t = _threading.Thread(target = self.__process_queue)
        t.setDaemon(True)
        t.start()

    def wrapped(self):
        return self.__fn

    def schedule(self, *args, **kwargs) -> None:
        self.__queue.put((args, kwargs))
    def schedule_no_queueing(self, *args, **kwargs) -> None:
        if not self.__processing and self.__queue.qsize() == 0:
            self.__queue.put((args, kwargs))

    def __process_queue(self):
        while True:
            try:
                self.__processing = False
                args, kwargs = self.__queue.get()
                self.__processing = True
                self.__fn(*args, **kwargs)
            except: # we can't stop, so just log the error so user can see it
                print(_traceback.format_exc(), file = _sys.stderr) # print out directly so that the stdio wrappers are used

_event_wrappers = {}
_event_wrappers_lock = _threading.Lock()
def get_event_wrapper(f) -> EventWrapper:
    with _event_wrappers_lock:
        if f in _event_wrappers:
            return _event_wrappers[f]

        wrap = EventWrapper(f) # this spawns a thread
        _event_wrappers[f] = wrap
        return wrap
