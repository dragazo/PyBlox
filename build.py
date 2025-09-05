import aiohttp
import asyncio
import certifi
import ssl
import sys
import re

import meta

from string import Template

ssl_context = ssl.create_default_context(cafile=certifi.where())

with open('template/init.py', 'r') as f:
    INIT_TEMPLATE = Template(f.read())
with open('template/service-class.py', 'r') as f:
    SERVICE_CLASS_TEMPLATE = Template(f.read())
with open('template/client-class.py', 'r') as f:
    CLIENT_CLASS_TEMPLATE = Template(f.read())

FN_NAME_SPECIAL_RULES = { # truly special cases go here
    'PhoneIoT': 'phone_iot',
    'IoTScape': 'iot_scape',
}
FN_NAME_KEYWORD_FIXES = { # in case we run into a reserved word
    'from': '_from',
}

def clean_fn_name(name: str) -> str:
    if name in FN_NAME_SPECIAL_RULES:
        return FN_NAME_SPECIAL_RULES[name]

    name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid

    pieces = ['']
    chars = [None, *name, None, None]
    for i in range(len(name)):
        prev_ch, curr_ch, next_ch, next_next_ch = chars[i:i+4]
        boundary = curr_ch.isupper() and (
            (prev_ch is not None and prev_ch.islower()) or
            (next_ch is not None and next_ch.islower() and next_next_ch is not None and next_next_ch.islower())
        )
        if boundary: pieces.append('')
        pieces[-1] += curr_ch
    name = '_'.join(x.lower() for x in pieces)

    name = re.sub(r'^_+|_+$', '', name) # remove lead/tail underscores
    name = FN_NAME_KEYWORD_FIXES.get(name) or name
    return name
def clean_class_name(name: str) -> str:
    name = re.sub('[^\w]+', '', name) # remove characters that make symbols invalid
    name = re.sub(r'^_+|_+$', '', name) # remove lead/tail underscores
    return name

tests = [
    ('PhoneID', 'phone_id'),
    ('PhoneIDs', 'phone_ids'),
    ('PhoneIoT', 'phone_iot'),
    ('IoTScape', 'iot_scape'),
    ('getMediaURLs', 'get_media_urls'),
    ('movieCastPersonIDs', 'movie_cast_person_ids'),
    ('getSensors', 'get_sensors'), ('ThisXDoesNotExist', 'this_x_does_not_exist'),
    ('getCO2Data', 'get_co2_data'), ('getCO*2*Data', 'get_co2_data'),
    ('city*', 'city'), ('_city*_', 'city'), ('__city*__', 'city'), ('___city*___', 'city'),
    ('HelloKitty2021', 'hello_kitty2021'), ('C6H5O6', 'c6h5o6'), ('P2PNetwork', 'p2p_network'),
    ('getXFromLongitude', 'get_x_from_longitude'), ('getYFromLatitude', 'get_y_from_latitude'),
]
failed_tests = 0
for a, b in tests:
    res = clean_fn_name(a)
    if res != b:
        print(f'clean_fn_name error: {a} -> {res} (expected {b})', file = sys.stderr)
        failed_tests += 1
if failed_tests != 0:
    raise RuntimeError(f'failed {failed_tests} fn rename tests!')

tests = [
    ('Merp', 'Merp'), ('_Me*rp*_', 'Merp'), ('__*Me*rp__', 'Merp'),
    ('MerpDerp', 'MerpDerp'), ('MerpDerp203', 'MerpDerp203'),
]
for a, b in tests:
    res = clean_class_name(a)
    if res != b: raise RuntimeError(f'clean_class_name error: {a} -> {res} (expected {b})')

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
    if t is None: return 'Any', ''

    name = t['name'] if type(t) == dict else t
    name_lower = name.lower()
    if name_lower == 'array':
        if type(t) != dict:
            return 'list', ''
        params = t.get('params') or []
        if len(params) == 0 or len(params) > 1: # non-homogeneous is ill-formed - just default to generic list
            return 'list', ''

        inner_t, inner_parse = parse_type(params[0].get('type') if type(params[0]) == dict else params[0], types_meta)
        inner_t = f'List[{inner_t}]' if inner_t != 'Any' else 'list'
        inner_parse = f'_common.vectorize({inner_parse})' if inner_parse else ''
        return inner_t, inner_parse
    elif name_lower == 'image':
        return 'Image.Image', ''

    for k, v in FIXED_TYPES.items():
        if name_lower in v:
            return k, k

    return parse_type(types_meta.get(name, {}).get('baseType'), types_meta)

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

    return arg_meta, t, '\n\n'.join(desc), t_parser

# returns either a string containing a class definition for the given service, or None if it should be omitted
async def generate_service(session, base_url: str, services_url: str, service_name: str, types_meta):
    async with session.get(f'{services_url}/{service_name}', ssl = ssl_context) as res:
        meta = await res.json(content_type=None) # ignore content type in case response mime type is wrong
        if 'servicePath' not in meta or not meta['servicePath']:
            return None # only generate code for fs services

        rpcs = []
        for rpc_name, rpc_meta in meta['rpcs'].items():
            is_deprecated = rpc_meta.get('deprecated', False)

            required, non_required = [], []
            for arg_meta in rpc_meta['args']:
                (non_required if 'optional' in arg_meta and arg_meta['optional'] else required).append(parse_arg(arg_meta, types_meta))

            ret_info = parse_arg(rpc_meta.get('returns'), types_meta, 'returns')
            args = ['self'] + [f'{clean_fn_name(x[0]["name"])}: {x[1]}' for x in required] + [f'{clean_fn_name(x[0]["name"])}: {x[1]} = None' for x in non_required]
            payloads = [f"'{x[0]['name']}': {clean_fn_name(x[0]['name'])}" for x in required + non_required]

            desc = ([rpc_meta['description']] if rpc_meta.get('description') else []) + [x[2] for x in required + non_required] + ([ret_info[2]] if 'returns' in rpc_meta else [])
            desc = '\n\n'.join(desc)
            desc = indent(f"'''\n{desc}\n'''", 8)

            code = f"self._client.call('{service_name}', '{rpc_name}', **{{ {', '.join(payloads)} }})"
            code = f'res = {code}\nreturn {ret_info[3]}(res)' if ret_info[3] else f'return {code}'

            fn_name = clean_fn_name(rpc_name)
            meta_name = f'_{fn_name}' if is_deprecated else fn_name
            prefix = '    @deprecated()\n' if is_deprecated else ''

            ret_str = f' -> {ret_info[1]}' if 'returns' in rpc_meta else ''
            rpcs.append((fn_name, f"{prefix}    def {meta_name}({', '.join(args)}){ret_str}:\n{desc}\n{indent(code, 8)}"))

        rpcs = [x[1] for x in sorted(rpcs)] # sort rpcs so they'll be in alphabetical order by name
        service_desc = f"'''\n{meta['description']}\n'''" if 'description' in meta and meta['description'] else ''
        formatted = SERVICE_CLASS_TEMPLATE.substitute({ 'service_name': clean_class_name(service_name), 'service_desc': indent(service_desc, 4), 'rpcs': '\n'.join(rpcs) })
        return (service_name, formatted, service_desc)

async def generate_client(base_url, client_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{base_url}/configuration', ssl = ssl_context) as res:
            services_url = (await res.json(content_type=None))['servicesHosts'][0]['url'] # ignore content type in case response type is wrong
        async with session.get(services_url, ssl = ssl_context) as res:
            services_meta = await res.json(content_type=None) # ignore content type in case response mime type is wrong
        async with session.get(f'{services_url}/input-types', ssl = ssl_context) as tres:
            types_meta = await tres.json(content_type=None) # ignore content type in case response mime type is wrong
            services = await asyncio.gather(*[asyncio.ensure_future(generate_service(session, base_url, services_url, x['name'], types_meta)) for x in services_meta])
            services = sorted([x for x in services if x]) # remove None values (omitted services) and sort to make sure they're in a consistent order

            service_classes = '\n'.join([x[1] for x in services])
            service_instances = '\n'.join([f'        self.{clean_fn_name(x[0])} = {clean_class_name(x[0])}(self)\n{indent(x[2], 8)}\n' for x in services])

            return CLIENT_CLASS_TEMPLATE.substitute({ 'client_name': client_name, 'base_url': base_url,
                'service_classes': service_classes, 'service_instances': service_instances })

async def generate_client_save(base_url, client_name, save_path):
    content = await generate_client(base_url, client_name)
    with open(save_path, 'w', encoding = 'utf-8') as f: # explicit encoding needed on windows
        f.write(content)
async def main():
    init_content = INIT_TEMPLATE.substitute({ 'description': meta.description, 'version': meta.version, 'author': meta.author, 'credits': meta.credits })
    with open('netsblox/__init__.py', 'w', encoding = 'utf-8') as f: # explicit encoding needed on windows
        f.write(init_content)

    args = [
        ('https://cloud.netsblox.org', 'Client', 'netsblox/editor.py'),
        # ('https://cloud.dev.netsblox.org', 'Client', 'netsblox/dev.py'),
    ]
    await asyncio.gather(*[asyncio.ensure_future(generate_client_save(*x)) for x in args])

def main_sync():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    loop.run_until_complete(asyncio.sleep(1)) # workaround needed on windows - for some reason they close the proactor event loop early otherwise
    loop.close()

if __name__ == '__main__':
    main_sync()
