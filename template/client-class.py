import collections as _collections
import threading as _threading
import traceback as _traceback
import inspect as _inspect
import time as _time
import json as _json
import sys as _sys
import io as _io

from PIL import Image

from typing import Optional, Any, List

import websocket as _websocket
import requests as _requests

import netsblox.common as _common
import netsblox.events as _events

_websocket.enableTrace(False) # disable auto-outputting of socket events

_SEND_RETARGETS = {
    'myself': 'everyone in room',
}

class $client_name:
    '''
    Holds all the information and plumbing required to connect to netsblox, exchange messages, and call RPCs.
    '''

    def __init__(self, *, proj_name: Optional[str] = None, proj_id: Optional[str] = None, run_forever: bool = False):
        '''
        Opens a new client connection to NetsBlox, allowing you to access any of the NetsBlox services from python.

        `proj_name` and `proj_id` control the public name of your project from other programs.
        For instance, these are needed for other programs to send a message to your project.
        If you do not provide them, defaults will be generated (which will work),
        but the public id will change every time, which could be annoying if you need to frequently start/stop your project to make changes.

        `run_forever` prevents the python program from terminating even after the end of your script.
        This is useful if you have long-running programs that are based on message-passing rather than looping.
        Note: this does not stop the main thread of execution from terminating, which could be a problem in environments like Google Colab;
        instead, you can explicitly call `wait_till_disconnect()` at the end of your program.
        '''

        self._client_id = proj_id or _common.generate_proj_id()
        self._base_url = '$base_url'

        # set these up before the websocket since it might send us messages
        self._message_cv = _threading.Condition(_threading.Lock())
        self._message_queue = _collections.deque()
        self._message_handlers = {}
        self._message_last = {} # maps msg type to {received_count, last_content, waiters (count)}
        self._message_stream_stopped = False

        # create a websocket and start it before anything non-essential (has some warmup communication)
        self._ws_lock = _threading.Lock()
        self._ws = _websocket.WebSocketApp(self._base_url.replace('http', 'ws'),
            on_open = self._ws_open, on_close = self._ws_close, on_error = self._ws_error, on_message = self._ws_message)
        self._ws_thread = _threading.Thread(target = self._ws.run_forever)
        self._ws_thread.setDaemon(not run_forever)
        self._ws_thread.start()

        # create a thread to manage the message queue
        self._message_thread = _threading.Thread(target = self._message_router)
        self._message_thread.setDaemon(True)
        self._message_thread.start()

        res = _json.loads(_requests.post(f'{self._base_url}/api/newProject',
            _common.small_json({ 'clientId': self._client_id, 'roleName': 'monad' }),
            headers = { 'Content-Type': 'application/json' }).text)
        self._project_id = res['projectId']
        self._role_id = res['roleId']
        self._role_name = res['roleName']

        res = _json.loads(_requests.post(f'{self._base_url}/api/setProjectName',
            _common.small_json({ 'projectId': self._project_id, 'name': proj_name or 'untitled' }),
            headers = { 'Content-Type': 'application/json' }).text)
        self._project_name = res['name']

$service_instances

    def _ws_open(self, ws):
        with self._ws_lock:
            ws.send(_common.small_json({ 'type': 'set-uuid', 'clientId': self._client_id }))

    def _ws_close(self, ws, status, message):
        print('ws close', file = _sys.stderr)
    def _ws_error(self, ws, error):
        print('ws error:', error, file = _sys.stderr)

    def _ws_message(self, ws, message):
        try:
            message = _json.loads(message)
            ty = message['type']

            if ty == 'connected': # currently unused
                return
            elif ty == 'ping':
                with self._ws_lock:
                    ws.send(_common.small_json({ 'type': 'pong' }))
                    return
            elif ty == 'message':
                with self._message_cv:
                    self._message_queue.append(message)
                    self._message_cv.notify()
        except:
            pass
    
    def get_public_id(self):
        '''
        Gets the public id, which can be used as a target for `send_message()` to directly send a message to you.
        '''
        return f'{self._project_name}@{self._client_id}'
    def send_message(self, msg_type, target='myself', **values):
        '''
        Sends a message of the given type to the target, which might represent multiple recipients.
        The default value for target, `'myself'`, will send the message to yourself.
        You can receive messages by registering a receiver with on_message().
        '''
        if target in _SEND_RETARGETS:
            target = _SEND_RETARGETS[target]
        with self._ws_lock:
            self._ws.send(_common.small_json({
                'type': 'message',
                'msgType': msg_type,
                'content': values,
                'dstId': target,
                'srcId': self.get_public_id(),
            }))

    @staticmethod
    def _check_handler(handler, content):
        argspec = _inspect.getfullargspec(handler.wrapped())
        unused_params = set(content.keys())
        for arg in argspec.args + argspec.kwonlyargs:
            if arg not in content and arg != 'self':
                return f'    unknown param: \'{arg}\' typo?\n    available params: {list(content.keys())}'
            unused_params.discard(arg)
        return { k: content[k] for k in content.keys() if k not in unused_params } if unused_params and argspec.varkw is None else content
    def _message_get_last_assume_locked(self, msg_type):
        if msg_type not in self._message_last:
            self._message_last[msg_type] = { 'received_count': 0, 'last_content': {}, 'waiters': 0 }
        return self._message_last[msg_type]
    def _message_router(self):
        while True:
            try:
                message = None
                handlers = None
                with self._message_cv:
                    # if no more messages and stream has stopped, kill the thread
                    if not self._message_queue and self._message_stream_stopped:
                        return
                    # wait for a message or kill signal
                    while not self._message_queue and not self._message_stream_stopped:
                        self._message_cv.wait()
                    # if we didn't get a message, kill the thread
                    if not self._message_queue:
                        return

                    message = self._message_queue.popleft()
                    handlers = self._message_handlers.get(message['msgType'])
                    handlers = handlers[:] if handlers is not None else [] # iteration without mutex needs a (shallow) copy

                    last = self._message_get_last_assume_locked(message['msgType'])
                    last['received_count'] += 1
                    last['last_content'] = message['content']
                    if last['waiters'] > 0:
                        last['waiters'] = 0
                        self._message_cv.notify_all()
                
                content = message['content']
                for handler in handlers: # without mutex lock so we don't block new ws messages or on_message()
                    try:
                        packet = $client_name._check_handler(handler, content)
                        if type(packet) == str:
                            print(f'\'{message["msgType"]}\' message handler error:\n{packet}', file = _sys.stderr)
                            continue

                        handler.schedule(**packet)
                    except:
                        _traceback.print_exc(file = _sys.stderr)
            except:
                _traceback.print_exc(file = _sys.stderr)
    
    def wait_for_message(self, msg_type: str) -> dict:
        '''
        Waits until we receive the next message of the given type.
        Returns the received message upon resuming.

        You can trigger this manually by sending a message to yourself.
        '''
        with self._message_cv:
            last = self._message_get_last_assume_locked(msg_type)
            last['waiters'] += 1
            v = last['received_count']
            while last['received_count'] <= v:
                self._message_cv.wait()
            return last['last_content']

    def _on_message(self, msg_type: str, handler):
        with self._message_cv:
            handlers = self._message_handlers.get(msg_type)
            if handlers is None:
                handlers = []
                self._message_handlers[msg_type] = handlers
            handlers.append(_events.get_event_wrapper(handler))
    def on_message(self, *msg_types: str):
        '''
        This is a decorator that can be applied to a turtle/stage method or a function
        to cause the function to be executed when a message of the given type is received from NetsBlox.
        You can receive message fields by specifying input parameters.

        ```
        @nb.on_message('start')
        def on_start():
            print('started')

        @nb.on_message('left', 'right')
        def on_left_or_right(self, distance):
            print('moved', distance, 'cm')
        ```
        '''
        def wrapper(f):
            if _common.is_method(f):
                if not hasattr(f, '__run_on_message'):
                    setattr(f, '__run_on_message', [])
                # mark it for the constructor to handle when an instance is created
                def stupid_closure_semantics(_msg_type):
                    return lambda x: self._on_message(_msg_type, x)
                getattr(f, '__run_on_message').extend([stupid_closure_semantics(msg_type) for msg_type in msg_types])
            else:
                for msg_type in msg_types:
                    self._on_message(msg_type, f)

            return f
        return wrapper

    def _call(self, service, rpc, payload):
        payload = { k: _common.prep_send(v) for k,v in payload.items() }
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(_time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = _requests.post(url,
            _common.small_json(payload), # if the json has unnecessary white space, request on the server will hang for some reason
            headers = { 'Content-Type': 'application/json' })

        if res.status_code == 200:
            try:
                if 'Content-Type' in res.headers:
                    ty = res.headers['Content-Type']
                    if ty.startswith('image/'):
                        return Image.open(_io.BytesIO(res.content))
                return _json.loads(res.text)
            except:
                return res.text # strings are returned unquoted, so they'll fail to parse as json
        elif res.status_code == 404:
            raise _common.NotFoundError(res.text)
        elif res.status_code == 500:
            raise _common.ServerError(res.text)
        else:
            raise Exception(f'Unknown error: {res.status_code}\n{res.text}')

    def disconnect(self):
        '''
        Disconnects the client from the NetsBlox server.
        If the client was created with run_forever, this will allow the program to terminate.
        '''
        with self._ws_lock:
            self._ws.close() # closing the websocket will kill the ws thread
        with self._message_cv:
            self._message_stream_stopped = True # send the kill signal
            self._message_cv.notify()
    def wait_till_disconnect(self):
        '''
        This function waits until the client is disconnected and all queued messages have been handled.
        Other (non-waiting) code can call disconnect() to trigger this manually.
        This is useful if you have long-running code using messaging, e.g., a server.

        If you want similar behavior without having to actually disconnect the client, you can use a Signal instead.

        Note that calling this function is not equivalent to setting the run_forever option when creating the client, as that does not block the main thread.
        This can be used in place of run_forever, and is needed if other code waits for the main thread to finish (e.g., Google Colab).

        Note: you should not call this from a message handler (or any function that a message handler calls),
        as that will suspend the thread that handles messages, and since this waits until all messages have been handled, it will end up waiting forever.
        '''
        self._message_thread.join()

$service_classes