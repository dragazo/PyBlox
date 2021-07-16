#!/usr/bin/env python

import collections
import threading
import inspect
import time
import json
import sys
import re

import websocket
import requests

websocket.enableTrace(False) # disable auto-outputting of socket events

class UnavailableService(Exception):
    pass
class NotFoundError(Exception):
    pass
class InvokeError(Exception):
    pass
class ServerError(Exception):
    pass

def _small_json(obj):
    return json.dumps(obj, separators=(',', ':'))

class Client:
    '''
    Holds all the information and plumbing required to connect to netsblox, exchange messages, and call RPCs.
    '''

    def __init__(self, *, run_forever = False, host = 'https://editor.netsblox.org'):
        '''
        Opens a new client connection to NetsBlox, allowing you to access any of the NetsBlox services from python.

        :run_forever: prevents the python program from terminating even after the end of your script.
        This is useful if you have long-running programs that are based on message-passing rather than looping.

        :host: URL of the NetsBlox server to connect to.
        The default is appropriate for most usages.
        '''

        self._client_id = f'_pyblox{round(time.time() * 1000)}'
        self._base_url = host

        # set these up before the websocket since it might send us messages
        self._message_cv = threading.Condition(threading.Lock())
        self._message_queue = collections.deque()
        self._message_handlers = {}

        # create a websocket and start it before anything non-essential (has some warmup communication)
        self._ws_lock = threading.Lock()
        self._ws = websocket.WebSocketApp(host.replace('http', 'ws'),
            on_open = self._ws_open, on_close = self._ws_close, on_error = self._ws_error, on_message = self._ws_message)
        self._ws_thread = threading.Thread(target = self._ws.run_forever)
        self._ws_thread.setDaemon(not run_forever)
        self._ws_thread.start()

        # create a thread to manage the message queue
        self._message_thread = threading.Thread(target = self._message_router)
        self._message_thread.setDaemon(True)
        self._message_thread.start()

        res = requests.post(f'{self._base_url}/api/newProject',
            _small_json({ 'clientId': self._client_id, 'name': None }),
            headers = { 'Content-Type': 'application/json' })
        res = json.loads(res.text)
        self._project_id = res['projectId']
        self._project_name = res['name']
        self._role_id = res['roleId']
        self._role_name = res['roleName']

        self._service_lock = threading.Lock()
        self._services = {}
        self._services_info = {}
        for service_info in json.loads(requests.get(f'{self._base_url}/services').text):
            self._services_info[service_info['name']] = service_info
    
    def _ws_open(self, ws):
        with self._ws_lock:
            ws.send(_small_json({ 'type': 'set-uuid', 'clientId': self._client_id }))

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
                    ws.send(_small_json({ 'type': 'pong' }))
                    return
            elif ty == 'message':
                with self._message_cv:
                    self._message_queue.append(message)
                    self._message_cv.notify()
        except:
            pass
    
    def send_message(self, msg_type, **args):
        with self._ws_lock:
            self._ws.send(_small_json({
                'type': 'message', 'msgType': msg_type, 'content': args,
                'dstId': 'everyone in room', 'srcId': self.get_public_role_id()
            }))

    @staticmethod
    def _check_handler(handler, content):
        argspec = inspect.getfullargspec(handler)
        unused_params = set(content.keys())
        for arg in argspec.args + argspec.kwonlyargs:
            if arg not in content:
                return f'    unknown param: \'{arg}\' typo?\n    available params: {list(content.keys())}'
            unused_params.remove(arg)
        return { k: content[k] for k in content.keys() if k not in unused_params } if unused_params and argspec.varkw is None else content
    def _message_router(self):
        while True:
            try:
                message = None
                handlers = None
                with self._message_cv:
                    while not self._message_queue:
                        self._message_cv.wait()
                    message = self._message_queue.popleft()
                    handlers = self._message_handlers.get(message['msgType'])
                    handlers = handlers[:] if handlers is not None else [] # iteration without mutex needs a (shallow) copy

                content = message['content']
                for handler in handlers: # without mutex lock so we don't block new ws messages or on_message()
                    packet = Client._check_handler(handler, content)
                    if type(packet) == str:
                        print(f'\'{message["msgType"]}\' message handler error:\n{packet}', file=sys.stderr)
                        continue

                    try:
                        handler(**packet) # the handler could be arbitrarily long and is fallible
                    except:
                        pass
            except:
                pass
    
    def _on_message(self, msg_type, handler):
        with self._message_cv:
            handlers = self._message_handlers.get(msg_type)
            if handlers is None:
                handlers = []
                self._message_handlers[msg_type] = handlers
            handlers.append(handler)
    def on_message(self, msg_type, handler=None):
        '''
        Adds a new message handler for incoming messages of the given type.
        If :handler: is specified, it is used as the message handler.
        Otherwise, this returns an annotation type that can be applied to a function definition.
        For example, the following would cause on_start to be called on every incoming 'start' message.

        client = Client()

        @client.on_message('start')
        def on_start():
            print('started')
        '''
        if handler is not None:
            self._on_message(msg_type, handler)
        else:
            def wrapper(f):
                self._on_message(msg_type, f)
                return f
            return wrapper
        
    @staticmethod
    def _prep_send(val):
        t = type(val)
        if t == list or t == tuple:
            return [Client._prep_send(v) for v in val]
        elif t == dict:
            return [[Client._prep_send(k), Client._prep_send(v)] for k,v in val.items()]
        else:
            return val
    @staticmethod
    def _clean_name(name):
        name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid
        name = re.sub('([A-Z]+)', lambda m: f'_{m.group(1).lower()}', name) # convert cammel case to snake case
        return name

    def _call(self, service, rpc, payload):
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = requests.post(url,
            _small_json(payload), # if the json has unnecessary white space, request on the server will hang for some reason
            headers = { 'Content-Type': 'application/json' })

        if res.status_code == 200:
            try:
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
        If the client was created with :run_forever:, this will allow the program to terminate.
        '''
        with self._ws_lock:
            self._ws.close() # closing the websocket will kill the deamon thread

    def get_public_role_id(self):
        return f'{self._role_name}@{self._project_name}@{self._client_id}'

    def get_service(self, service):
        with self._service_lock:
            if service in self._services:
                return self._services[service]
            if service not in self._services_info:
                raise UnavailableService(f'Service {service} is not available')
            
            obj = {}
            obj['_client'] = self
            obj['_meta'] = json.loads(requests.get(f'{self._base_url}/services/{service}').text)
            obj['_name'] = service
            obj['__doc__'] = obj['_meta'].get('description', '')

            for rpc_name, meta in obj['_meta']['rpcs'].items():
                rpc_obj = {}
                rpc_obj['_client'] = self
                rpc_obj['_meta'] = meta
                rpc_obj['_service'] = service
                rpc_obj['_name'] = rpc_name
                rpc_obj['_clean_name'] = Client._clean_name(rpc_name)

                for arg_meta in meta.get('args', []):
                    arg_meta['clean_name'] = Client._clean_name(arg_meta['name'])

                docstr = meta.get('description', '')
                if meta.get('args'):
                    docstr += '\n\nArguments:\n'
                    for arg in meta['args']:
                        docstr += f'\n:{arg["clean_name"]}: {arg.get("description", "")}'
                if meta.get('returns'):
                    docstr += f'\n\nreturns: {meta["returns"].get("description", "")}'
                rpc_obj['__doc__'] = docstr

                def invoke(self, *args, **kwargs):
                    payload = {}
                    for i, expect in enumerate(self._meta['args']):
                        rawname = expect['name']
                        pyname = expect['clean_name']

                        if i < len(args) and pyname in kwargs:
                            raise InvokeError(f'argument \'{pyname}\' was specified multiple times')
                        elif i < len(args):
                            payload[rawname] = Client._prep_send(args[i])
                        elif pyname in kwargs:
                            payload[rawname] = Client._prep_send(kwargs[pyname])
                            del kwargs[pyname]
                        elif not expect['optional']:
                            raise InvokeError(f'required argument \'{pyname}\' was not specified')
                        else:
                            payload[rawname] = '' # the server expects empty string as no value
                    
                    expected_count = len(self._meta['args'])
                    if kwargs:
                        raise InvokeError(f'unused keyword arguments: {kwargs}')
                    if len(args) > expected_count:
                        raise InvokeError(f'unused arguments: {args[expected_count:]}')

                    return self._client._call(self._service, self._name, payload)

                rpc_obj['__call__'] = invoke

                obj[rpc_obj['_clean_name']] = type(f'{service}.{rpc_obj["_clean_name"]}', (object,), rpc_obj)()

            obj = type(service, (object,), obj)()
            self._services[service] = obj
            return obj
