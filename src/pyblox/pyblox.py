#!/usr/bin/env python

import time
import websocket
import threading
import requests
import json
import re
import collections
import sys

websocket.enableTrace(False) # disable auto-outputting of socket events

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

class Client:
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
            small_json({ 'clientId': self._client_id, 'name': None }),
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
            elif ty == 'room-roles': # currenly unused
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

                if handlers is not None:
                    for handler in handlers:
                        handler(**message['content'])
            except:
                pass
    def on_message(self, msg_type, handler):
        with self._message_cv:
            handlers = self._message_handlers.get(msg_type)
            if handlers is None:
                handlers = []
                self._message_handlers[msg_type] = handlers
            handlers.append(handler)

    def _call(self, service, rpc, payload):
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = requests.post(url,
            small_json(payload), # if the json has unnecessary white space, request on the server will hang for some reason
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

            obj['get_name'] = lambda self: self._name
            obj['get_desc'] = lambda self: self._meta['description']

            def clean_name(name):
                name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid
                name = re.sub('([A-Z]+)', lambda m: f'_{m.group(1).lower()}', name) # convert cammel case to snake case
                return name
            for rpc_name, meta in obj['_meta']['rpcs'].items():
                rpc_obj = {}
                rpc_obj['_client'] = self
                rpc_obj['_meta'] = meta
                rpc_obj['_service'] = service
                rpc_obj['_name'] = rpc_name
                rpc_obj['_clean_name'] = clean_name(rpc_name)

                for arg_meta in meta['args']:
                    arg_meta['clean_name'] = clean_name(arg_meta['name'])

                rpc_obj['get_name'] = lambda self: self._name
                rpc_obj['get_desc'] = lambda self: self._meta['description']

                def invoke(self, *args, **kwargs):
                    payload = {}
                    for i, expect in enumerate(self._meta['args']):
                        rawname = expect['name']
                        pyname = expect['clean_name']

                        if i < len(args) and pyname in kwargs:
                            raise InvokeError(f'argument \'{pyname}\' was specified multiple times')
                        elif i < len(args):
                            payload[rawname] = args[i]
                        elif pyname in kwargs:
                            payload[rawname] = kwargs[pyname]
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

if __name__ == '__main__':
    client = Client(run_forever=True)
    phoneiot = client.get_service('PhoneIoT')
    public_roles = client.get_service('PublicRoles')

    assert phoneiot is client.get_service('PhoneIoT')
    assert phoneiot.get_name() == 'PhoneIoT'
    assert type(phoneiot.get_desc()) == str

    assert type(phoneiot.get_sensors()) == list
    assert phoneiot.get_sensors.get_name() == 'getSensors'
    assert type(phoneiot.get_sensors.get_desc()) == str

    assert phoneiot.get_color(12, 34, 54, 34) == 571220534
    assert phoneiot.get_color(12, 34, 54) == -15982026
    assert phoneiot.get_color(12, 34, blue=54) == -15982026
    assert phoneiot.get_color(12, blue=54, green=34) == -15982026

    assert public_roles is client.get_service('PublicRoles')
    assert public_roles.get_public_role_id() == client.get_public_role_id()
