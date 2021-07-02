#!/usr/bin/env python

import time
from websocket import WebSocket
import requests
import json
import re

class UnavailableService(Exception):
    pass
class UnavailableRPC(Exception):
    pass

class Client:
    def __init__(self, host='https://editor.netsblox.org'):
        self._client_id = f'_pyblox{round(time.time() * 1000)}'
        self._base_url = host

        self._ws_handlers = {}
        self._ws = WebSocket()
        self._ws.connect(host.replace('http', 'ws'))
        self._ws.send(json.dumps({ 'type': 'set-uuid', 'clientId': self._client_id }))

        res = requests.post(f'{self._base_url}/api/newProject', json.dumps({ 'clientId': self._client_id, 'name': None }))
        res = json.loads(res.text)
        self._project_id = res['projectId']
        self._project_name = res['name']
        self._role_id = res['roleId']
        self._role_name = res['roleName']

        self._services = {}
        self._services_info = {}
        for service_info in json.loads(requests.get(f'{self._base_url}/services').text):
            self._services_info[service_info['name']] = service_info

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

            rpc_obj['get_name'] = lambda self: self._name
            rpc_obj['get_desc'] = lambda self: self._meta['description']

            def invoke(self, *args):
                return self._client._call(self._service, self._name, *args)
            rpc_obj['__call__'] = invoke

            obj[rpc_obj['_clean_name']] = type(f'{service}.{rpc_obj["_clean_name"]}', (object,), rpc_obj)()

        obj = type(service, (object,), obj)()
        self._services[service] = obj
        return obj

    def _call(self, service, rpc, *args):
        state = f'uuid={self._client_id}&projectId={self._project_id}&roleId={self._role_id}&t={round(time.time() * 1000)}'
        url = f'{self._base_url}/services/{service}/{rpc}?{state}'
        res = requests.post(url, None, args)

        if res.status_code == 200:
            return json.loads(res.text)
        elif res.status_code == 404:
            raise UnavailableRPC(f'{service}.{rpc} is not available')
        else:
            raise Exception(f'Unknown error: {res.status_code}\n{res.text}')

if __name__ == '__main__':
    client = Client()
    assert type(client._call('PhoneIoT', 'getSensors')) == list

    phoneiot = client.get_service('PhoneIoT')
    assert phoneiot is client.get_service('PhoneIoT')
    assert phoneiot.get_name() == 'PhoneIoT'
    assert type(phoneiot.get_desc()) == str

    assert type(phoneiot.get_sensors()) == list
    assert phoneiot.get_sensors.get_name() == 'getSensors'
    assert type(phoneiot.get_sensors.get_desc()) == str

