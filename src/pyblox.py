#!/usr/bin/env python

import time
import websocket
import threading
import requests
import json
import re

websocket.enableTrace(False) # disable auto-outputting of socket events

class UnavailableService(Exception):
    pass
class UnavailableRPC(Exception):
    pass
class InvokeError(Exception):
    pass
class ServerError(Exception):
    pass

def small_json(obj):
    return json.dumps(obj, separators=(',', ':'))

class Client:
    def __init__(self, *, run_forever = False, host = 'https://editor.netsblox.org'):
        self._client_id = f'_pyblox{round(time.time() * 1000)}'
        self._base_url = host

        self._lock = threading.Lock()
        self._message_handlers = {}
        self._ws = websocket.WebSocketApp(host.replace('http', 'ws'),
            on_open = self._ws_open, on_close = self._ws_close, on_error = self._ws_error, on_message = self._ws_message)
        self._ws_thread = threading.Thread(target = self._ws.run_forever)
        self._ws_thread.setDaemon(not run_forever)
        self._ws_thread.start()

        res = requests.post(f'{self._base_url}/api/newProject',
            small_json({ 'clientId': self._client_id, 'name': None }),
            headers = { 'Content-Type': 'application/json' })
        res = json.loads(res.text)
        self._project_id = res['projectId']
        self._project_name = res['name']
        self._role_id = res['roleId']
        self._role_name = res['roleName']

        self._services = {}
        self._services_info = {}
        for service_info in json.loads(requests.get(f'{self._base_url}/services').text):
            self._services_info[service_info['name']] = service_info

    def close(self):
        print('closing client')
        self._ws.close() # closing the websocket will kill the deamon thread
    def _ws_open(self, ws):
        print('ws open')
        with self._lock:
            ws.send(small_json({ 'type': 'set-uuid', 'clientId': self._client_id }))

    def _ws_close(self, ws, status, message):
        print('ws close', status, message)

    def _ws_error(self, ws, error):
        print('ws error', error)

    def _ws_message(self, ws, message):
        print('ws message', message)
        try:
            message = json.loads(message)
            ty = message['type']

            if ty == 'connected': # currently unused
                return
            elif ty == 'room-roles': # currenly unused
                return
            elif ty == 'ping':
                with self._lock:
                    ws.send(small_json({ 'type': 'pong' }))
                    return
            
            handler = None
            with self._lock:
                if ty in self._message_handlers:
                    handler = self._message_handlers[ty]
            if handler is not None:
                handler(self, message)
        except:
            pass
    

    def _call(self, service, rpc, payload):
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = requests.post(url,
            small_json(payload), # if the json has unnecessary white space, request on the server will hang for some reason
            headers = { 'Content-Type': 'application/json' })

        if res.status_code == 200:
            return json.loads(res.text)
        elif res.status_code == 404:
            raise UnavailableRPC(f'{service}.{rpc} is not available')
        elif res.status_code == 500:
            raise ServerError(res.text)
        else:
            raise Exception(f'Unknown error: {res.status_code}\n{res.text}')

    def get_service(self, service):
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
                        raise InvokeError(f'argument {pyname} was specified multiple times')
                    elif i < len(args):
                        payload[rawname] = args[i]
                    elif pyname in kwargs:
                        payload[rawname] = kwargs[pyname]
                        del payload[pyname]
                    else:
                        payload[rawname] = None
                    
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
    client = Client()

    phoneiot = client.get_service('PhoneIoT')
    assert phoneiot is client.get_service('PhoneIoT')
    assert phoneiot.get_name() == 'PhoneIoT'
    assert type(phoneiot.get_desc()) == str

    assert type(phoneiot.get_sensors()) == list
    assert phoneiot.get_sensors.get_name() == 'getSensors'
    assert type(phoneiot.get_sensors.get_desc()) == str

    assert phoneiot.get_color("12", "34", "54", "34") == 571220534
