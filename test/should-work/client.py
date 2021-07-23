#!/usr/bin/env python

import netsblox

editor = netsblox.Editor()
phoneiot = editor.phone_iot
public_roles = editor.public_roles

assert type(phoneiot.get_sensors()) == list
assert public_roles.get_public_role_id() == editor.get_public_role_id()

assert phoneiot.get_color(12, 34, 54, 34) == 571220534
assert phoneiot.get_color(12, 34, 54) == -15982026
assert phoneiot.get_color(12, 34, blue=54) == -15982026
assert phoneiot.get_color(12, blue=54, green=34) == -15982026

assert type(editor.chart.default_options()) == dict
v = editor.hurricane_data.get_hurricane_data('katrina', 2005)
assert type(v) == list
for x in v:
    assert type(x) == dict

assert netsblox.prep_send(12) == 12
assert netsblox.prep_send(12.5) == 12.5
assert netsblox.prep_send([1, 2, 3]) == [1, 2, 3]
assert netsblox.prep_send((1, 2, 3)) == [1, 2, 3]
assert netsblox.prep_send({ 'key': 'value' }) == [['key', 'value']]
assert netsblox.prep_send({ 'key': { 'more': 'stuff' } }) == [[ 'key', [[ 'more', 'stuff' ]] ]]
assert netsblox.prep_send([{ 'a': 1 }, { 'b': 2 }]) == [ [[ 'a', 1 ]], [[ 'b', 2 ]] ]
assert netsblox.prep_send(({ 'a': 1 }, { 'b': 2 })) == [ [[ 'a', 1 ]], [[ 'b', 2 ]] ]
assert netsblox.prep_send({ (1, 2, 3): 4 }) == [[ [1, 2, 3], 4 ]]
assert netsblox.prep_send(None) == ''
