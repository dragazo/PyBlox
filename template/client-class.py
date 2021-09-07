import collections
import threading
import traceback
import inspect
import time
import json
import sys
import io

from PIL import Image

from typing import Optional, Any, List

import websocket
import requests

from .common import *

websocket.enableTrace(False) # disable auto-outputting of socket events

class $client_name:
    '''
    Holds all the information and plumbing required to connect to netsblox, exchange messages, and call RPCs.
    '''

    def __init__(self, *, run_forever = False):
        '''
        Opens a new client connection to NetsBlox, allowing you to access any of the NetsBlox services from python.

        run_forever prevents the python program from terminating even after the end of your script.
        This is useful if you have long-running programs that are based on message-passing rather than looping.
        Note: this does not stop the main thread of execution from terminating, which could be a problem in environments like Google Colab;
        instead, you can explicitly call wait_till_disconnect() at the end of your program.
        '''

        self._client_id = f'_pyblox{round(time.time() * 1000)}'
        self._base_url = '$base_url'

        # set these up before the websocket since it might send us messages
        self._message_cv = threading.Condition(threading.Lock())
        self._message_queue = collections.deque()
        self._message_handlers = {}
        self._message_last = {} # maps msg type to {received_count, last_content, waiters (count)}
        self._message_stream_stopped = False

        # create a websocket and start it before anything non-essential (has some warmup communication)
        self._ws_lock = threading.Lock()
        self._ws = websocket.WebSocketApp(self._base_url.replace('http', 'ws'),
            on_open = self._ws_open, on_close = self._ws_close, on_error = self._ws_error, on_message = self._ws_message)
        self._ws_thread = threading.Thread(target = self._ws.run_forever)
        self._ws_thread.setDaemon(not run_forever)
        self._ws_thread.start()

        # create a thread to manage the message queue
        self._message_thread = threading.Thread(target = self._message_router)
        self._message_thread.setDaemon(True)
        self._message_thread.start()

        res = requests.post(f'{self._base_url}/api/newProject',
            small_json({ 'clientId': self._client_id, 'name': None }),
            headers = { 'Content-Type': 'application/json' })
        res = json.loads(res.text)
        self._project_id = res['projectId']
        self._project_name = res['name']
        self._role_id = res['roleId']
        self._role_name = res['roleName']

$service_instances

    def _ws_open(self, ws):
        with self._ws_lock:
            ws.send(small_json({ 'type': 'set-uuid', 'clientId': self._client_id }))

    def _ws_close(self, ws, status, message):
        print('ws close', file=sys.stderr)
    def _ws_error(self, ws, error):
        print('ws error:', error, file=sys.stderr)

    def _ws_message(self, ws, message):
        try:
            message = json.loads(message)
            ty = message['type']

            if ty == 'connected': # currently unused
                return
            elif ty == 'ping':
                with self._ws_lock:
                    ws.send(small_json({ 'type': 'pong' }))
                    return
            elif ty == 'message':
                with self._message_cv:
                    self._message_queue.append(message)
                    self._message_cv.notify()
        except:
            pass
    
    def get_public_role_id(self):
        '''
        Returns the public role id, which can be used as a target for send_message() to send a message directly to yourself.
        This can be given to another client so that they can send messages directly to you.
        '''
        return f'{self._role_name}@{self._project_name}@{self._client_id}'
    def send_message(self, msg_type, target='everyone in room', **values):
        '''
        Sends a message of the given type to the target, which might represent multiple recipients.
        The default value for target, 'everyone in room', will send the message to everyone connected to this project (including yourself).
        You can receive messages by registering a receiver with on_message().
        '''
        with self._ws_lock:
            self._ws.send(small_json({
                'type': 'message',
                'msgType': msg_type,
                'content': values,
                'dstId': target,
                'srcId': self.get_public_role_id()
            }))

    @staticmethod
    def _check_handler(handler, content):
        argspec = inspect.getfullargspec(handler)
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

                def invoker(handler, content):
                    packet = $client_name._check_handler(handler, content)
                    if type(packet) == str:
                        print(f'\'{message["msgType"]}\' message handler error:\n{packet}', file=sys.stderr)
                        return

                    try:
                        handler(**packet) # the handler could be arbitrarily long and is fallible
                    except:
                        traceback.print_exc(file = sys.stderr)
                
                content = message['content']
                for handler in handlers: # without mutex lock so we don't block new ws messages or on_message()
                    t = threading.Thread(target = invoker, args = (handler, content))
                    t.setDaemon(True)
                    t.start()
            except:
                traceback.print_exc(file = sys.stderr)
    
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
            handlers.append(handler)
    def on_message(self, msg_type, handler=None):
        '''
        Adds a new message handler for incoming messages of the given type.
        If handler is specified, it is used as the message handler.
        Otherwise, this returns an annotation type that can be applied to a function definition.
        For example, the following would cause on_start to be called on every incoming 'start' message.

        ```
        client = $client_name()
        
        @client.on_message('start')
        def on_start():
            print('started')
        ```

        This can also be used on a method definition inside a custom turtle class,
        in which case every turtle of the given type will perform the action each time a message is received.

        ```
        client = $client_name()

        @turtle
        class MyTurtle:
            @client.on_message('start')
            def on_start(self):
                print('started')
        ```
        '''
        if handler is not None:
            self._on_message(msg_type, handler)
        else:
            def wrapper(f):
                info = inspect.getfullargspec(f)
                if len(info.args) != 0 and info.args[0] == 'self':
                    if not hasattr(f, '__run_on_message'):
                        setattr(f, '__run_on_message', [])
                    getattr(f, '__run_on_message').append(lambda x: self._on_message(msg_type, x)) # mark it for the constructor to handle when an instance is created
                else:
                    self._on_message(msg_type, f)
                
                return f
            return wrapper

    def _call(self, service, rpc, payload):
        payload = { k: prep_send(v) for k,v in payload.items() }
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = requests.post(url,
            small_json(payload), # if the json has unnecessary white space, request on the server will hang for some reason
            headers = { 'Content-Type': 'application/json' })

        if res.status_code == 200:
            try:
                if 'Content-Type' in res.headers:
                    ty = res.headers['Content-Type']
                    if ty.startswith('image/'):
                        return Image.open(io.BytesIO(res.content))
                return json.loads(res.text)
            except:
                return res.text # strings are returned unquoted, so they'll fail to parse as json
        elif res.status_code == 404:
            raise NotFoundError(res.text)
        elif res.status_code == 500:
            raise ServerError(res.text)
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