#!/usr/bin/env python

from netsblox import *

client = Client()
phoneiot = client.get_service('PhoneIoT')
public_roles = client.get_service('PublicRoles')

assert phoneiot is client.get_service('PhoneIoT')
assert public_roles is client.get_service('PublicRoles')

assert type(phoneiot.get_sensors()) == list
assert public_roles.get_public_role_id() == client.get_public_role_id()

assert phoneiot.get_color(12, 34, 54, 34) == 571220534
assert phoneiot.get_color(12, 34, 54) == -15982026
assert phoneiot.get_color(12, 34, blue=54) == -15982026
assert phoneiot.get_color(12, blue=54, green=34) == -15982026

assert Client._prep_send(12) == 12
assert Client._prep_send(12.5) == 12.5
assert Client._prep_send([1, 2, 3]) == [1, 2, 3]
assert Client._prep_send((1, 2, 3)) == [1, 2, 3]
assert Client._prep_send({ 'key': 'value' }) == [['key', 'value']]
assert Client._prep_send({ 'key': { 'more': 'stuff' } }) == [[ 'key', [[ 'more', 'stuff' ]] ]]
assert Client._prep_send([{ 'a': 1 }, { 'b': 2 }]) == [ [[ 'a', 1 ]], [[ 'b', 2 ]] ]
assert Client._prep_send(({ 'a': 1 }, { 'b': 2 })) == [ [[ 'a', 1 ]], [[ 'b', 2 ]] ]
assert Client._prep_send({ (1, 2, 3): 4 }) == [[ [1, 2, 3], 4 ]]

assert Client._clean_name('getSensors') == 'get_sensors'
assert Client._clean_name('getCO2Data') == 'get_co2_data'
assert Client._clean_name('city*') == 'city'
