import threading as _threading
import traceback as _traceback
import queue as _queue
import sys as _sys

class EventWrapper:
    def __init__(self, fn):
        self.fn = fn
        self.queue = _queue.Queue()
        
        t = _threading.Thread(target = self._process_queue)
        t.setDaemon(True)
        t.start()
    
    def schedule(self, *args, **kwargs) -> None:
        self.queue.put((args, kwargs))

    def _process_queue(self):
        while True:
            try:
                args, kwargs = self.queue.get()
                self.fn(*args, **kwargs)
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
