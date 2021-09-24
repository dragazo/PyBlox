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
    'ThisXDoesNotExist': 'this_x_does_not_exist',
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

assert clean_fn_name('getSensors') == 'get_sensors'
assert clean_fn_name('getCO2Data') == 'get_co2_data'
assert clean_fn_name('city*') == 'city'
assert clean_fn_name('HelloKitty2021') == 'hello_kitty2021'
assert clean_fn_name('PhoneIoT') == 'phone_iot'

assert clean_class_name('Merp') == 'Merp'
assert clean_class_name('MerpDerp') == 'MerpDerp'
assert clean_class_name('MerpDerp203') == 'MerpDerp203'
assert clean_class_name('MerpDerp203*') == 'MerpDerp203'

def indent(input: str, spaces: int) -> str:
    pad = ' ' * spaces
    return '\n'.join([ f'{pad}{line}' for line in input.split('\n') ])

FIXED_TYPES = {
    'float': { 'number', 'boundednumber', 'latitude', 'longitude' },
    'int': { 'integer', 'boundedinteger' },
    'str': { 'string', 'boundedstring', 'date', 'enum' },
    'bool': { 'boolean' },
    'dict': { 'object' },
}

# returns type name, type parser
def parse_type(t, types_meta):
    if t is None:
        return 'Any', ''

    name = t['name'] if type(t) == dict else t
    name_lower = name.lower()
    if name_lower == 'array':
        if type(t) != dict:
            return 'list', ''
        params = t.get('params') or []
        if len(params) == 0 or len(params) > 1: # non-homogenous is ill-formed - just default to generic list
            return 'list', ''

        inner_t, inner_parse = parse_type(params[0].get('type') if type(params[0]) == dict else params[0], types_meta)
        inner_t = f'List[{inner_t}]' if inner_t != 'Any' else 'list'
        inner_parse = f'vectorize({inner_parse})' if inner_parse else ''
        return inner_t, inner_parse

    for k,v in FIXED_TYPES.items():
        if name_lower in v:
            return k, k

    return parse_type((types_meta.get(name) or {}).get('baseType'), types_meta)

# returns arg meta, type name, description, type parser
def parse_arg(arg_meta, types_meta, override_name: str = None):
    if arg_meta is None:
        return arg_meta, 'Any', '', ''

    t, t_parser = parse_type(arg_meta.get('type'), types_meta)
    if arg_meta.get('optional'):
        t = f'Optional[{t}]'

    desc = [f':{override_name or clean_fn_name(arg_meta["name"])}: {arg_meta.get("description") or ""}']
    if (arg_meta.get('type') or {}).get('name') == 'Object':
        for param_meta in arg_meta['type'].get('params') or []:
            desc.append(f'  - :{param_meta["name"]}: ({parse_type(param_meta.get("type"), types_meta)[0]}) {param_meta.get("description") or ""}')

    return arg_meta, t, '\n'.join(desc), t_parser

# returns either a string containing a class definition for the given service, or None if it should be omitted
async def generate_service(session, base_url: str, service_name: str, types_meta):
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
                (non_required if 'optional' in arg_meta and arg_meta['optional'] else required).append(parse_arg(arg_meta, types_meta))

            ret_info = parse_arg(rpc_meta.get('returns'), types_meta, 'returns')
            args = ['self'] + [f'{clean_fn_name(x[0]["name"])}: {x[1]}' for x in required] + [f'{clean_fn_name(x[0]["name"])}: {x[1]} = None' for x in non_required]
            payloads = [f"'{x[0]['name']}': {clean_fn_name(x[0]['name'])}" for x in required + non_required]
            
            desc = ([rpc_meta['description']] if rpc_meta.get('description') else []) + [x[2] for x in required + non_required] + ([ret_info[2]] if 'returns' in rpc_meta else [])
            desc = '\n\n'.join(desc)
            desc = indent(f"'''\n{desc}\n'''", 8)
            
            code = f"self._client._call('{service_name}', '{rpc_name}', {{ {', '.join(payloads)} }})"
            code = f'res = {code}\nreturn {ret_info[3]}(res)' if ret_info[3] else f'return {code}'

            fn_name = clean_fn_name(rpc_name)
            ret_str = f' -> {ret_info[1]}' if 'returns' in rpc_meta else ''
            rpcs.append((fn_name, f"    def {fn_name}({', '.join(args)}){ret_str}:\n{desc}\n{indent(code, 8)}"))

        rpcs = [x[1] for x in sorted(rpcs)] # sort rpcs so they'll be in alphabetical order by name
        service_desc = f"'''\n{meta['description']}\n'''" if 'description' in meta and meta['description'] else ''
        formatted = SERVICE_CLASS_TEMPLATE.substitute({ 'service_name': clean_class_name(service_name), 'service_desc': indent(service_desc, 4), 'rpcs': '\n'.join(rpcs) })
        return (service_name, formatted, service_desc)

async def generate_client(base_url, client_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{base_url}/services') as res:
            services_meta = await res.json(content_type=None) # ignore content type in case response mime type is wrong
            async with session.get(f'{base_url}/services/input-types') as tres:
                types_meta = await tres.json(content_type=None) # ignore content type in case response mime type is wrong
                services = await asyncio.gather(*[asyncio.ensure_future(generate_service(session, base_url, x['name'], types_meta)) for x in services_meta])
                services = sorted([x for x in services if x]) # remove None values (omitted services) and sort to make sure they're in a consistent order

                service_classes = '\n'.join([x[1] for x in services])
                service_instances = '\n'.join([f'        self.{clean_fn_name(x[0])} = {clean_class_name(x[0])}(self)\n{indent(x[2], 8)}\n' for x in services])

                return CLIENT_CLASS_TEMPLATE.substitute({ 'client_name': client_name, 'base_url': base_url,
                    'service_classes': service_classes, 'service_instances': service_instances })

async def generate_client_save(base_url, client_name, save_path):
    content = await generate_client(base_url, client_name)
    with open(save_path, 'w') as f:
        f.write(content)
async def main():
    args = [
        ('https://editor.netsblox.org', 'Client', 'netsblox/editor.py'),
        ('https://dev.netsblox.org', 'Client', 'netsblox/dev.py'),
        
        # ('http://localhost:8080', 'LocalHost', 'netsblox/localhost.py'), # for dev purposes only
    ]
    await asyncio.gather(*[asyncio.ensure_future(generate_client_save(*x)) for x in args])

asyncio.run(main())
