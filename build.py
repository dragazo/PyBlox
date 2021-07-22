#!/usr/bin/env python

import aiohttp
import asyncio
import re

from string import Template

SERVICE_CLASS_TEMPLATE = None
with open('template/service-class.py', 'r') as f:
    SERVICE_CLASS_TEMPLATE = Template(f.read())

CLIENT_CLASS_TEMPLATE = None
with open('template/client-class.py', 'r') as f:
    CLIENT_CLASS_TEMPLATE = Template(f.read())

FN_NAME_SPECIAL_RULES = {
    'PhoneIoT': 'phone_iot',
}
FN_NAME_KEYWORD_FIXES = {
    'from': '_from',
}

def clean_fn_name(name: str) -> str:
    if name in FN_NAME_SPECIAL_RULES:
        return FN_NAME_SPECIAL_RULES[name]

    name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid
    name = re.sub('([A-Z]+)', lambda m: f'_{m.group(1).lower()}', name) # convert cammel case to snake case
    name = name if not name.startswith('_') else name[1:]
    name = FN_NAME_KEYWORD_FIXES.get(name) or name
    return name
def clean_class_name(name: str) -> str:
    name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid
    return name

def indent(input: str, spaces: int) -> str:
    pad = ' ' * spaces
    return '\n'.join([ f'{pad}{line}' for line in input.split('\n') ])

assert clean_fn_name('getSensors') == 'get_sensors'
assert clean_fn_name('getCO2Data') == 'get_co2_data'
assert clean_fn_name('city*') == 'city'
assert clean_fn_name('HelloKitty2021') == 'hello_kitty2021'
assert clean_fn_name('PhoneIoT') == 'phone_iot'

assert clean_class_name('Merp') == 'Merp'
assert clean_class_name('MerpDerp') == 'MerpDerp'
assert clean_class_name('MerpDerp203') == 'MerpDerp203'
assert clean_class_name('MerpDerp203*') == 'MerpDerp203'

# returns either a string containing a class definition for the given service, or None if it should be omitted
async def generate_service(session, base_url, service_name):
    async with session.get(f'{base_url}/services/{service_name}') as res:
        meta = await res.json(content_type=None) # ignore content type in case response mime type is wrong
        if 'servicePath' not in meta or not meta['servicePath']:
            return None # only generate code for fs services
        
        rpcs = []
        for rpc_name, rpc_meta in meta['rpcs'].items():
            if 'deprecated' in rpc_meta and rpc_meta['deprecated']:
                continue

            required, non_required = [], []
            for arg_meta in rpc_meta['args']:
                (non_required if 'optional' in arg_meta and arg_meta['optional'] else required).append(arg_meta)

            args = ['self'] + [clean_fn_name(x['name']) for x in required] + [f"{clean_fn_name(x['name'])}=None" for x in non_required]
            payloads = [f"'{x['name']}': {clean_fn_name(x['name'])}" for x in required + non_required]
            desc = indent(f"'''\n{rpc_meta['description']}\n'''", 8) + '\n' if 'description' in rpc_meta and rpc_meta['description'] else ''
            rpcs.append(f"    def {clean_fn_name(rpc_name)}({', '.join(args)}):\n{desc}        return self._client._call('{service_name}', '{rpc_name}', {{ {', '.join(payloads)} }})")

        service_desc = indent(f"'''\n{meta['description']}\n'''", 4) if 'description' in meta and meta['description'] else ''
        formatted = SERVICE_CLASS_TEMPLATE.substitute({ 'service_name': clean_class_name(service_name), 'service_desc': service_desc, 'rpcs': '\n'.join(rpcs) })
        return (service_name, formatted)

async def generate_client(base_url, client_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{base_url}/services') as res:
            services_meta = await res.json(content_type=None) # ignore content type in case response mime type is wrong
            services = await asyncio.gather(*[asyncio.ensure_future(generate_service(session, base_url, x['name'])) for x in services_meta])
            services = sorted([x for x in services if x]) # remove None values (omitted services) and sort to make sure they're in a consistent order

            service_classes = '\n'.join([x[1] for x in services])
            service_instances = '\n'.join([f'        self.{clean_fn_name(x[0])} = {clean_class_name(x[0])}(self)' for x in services])

            return CLIENT_CLASS_TEMPLATE.substitute({ 'client_name': client_name, 'base_url': base_url,
                'service_classes': service_classes, 'service_instances': service_instances })

async def generate_client_save(base_url, client_name, save_path):
    content = await generate_client(base_url, client_name)
    with open(save_path, 'w') as f:
        f.write(content)
async def main():
    args = [
        ('https://editor.netsblox.org', 'Editor', 'netsblox/editor.py'),
        ('https://dev.netsblox.org', 'Dev', 'netsblox/dev.py'),
    ]
    await asyncio.gather(*[asyncio.ensure_future(generate_client_save(*x)) for x in args])

asyncio.run(main())
