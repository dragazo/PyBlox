import os

name = 'netsblox'
version = '0.6.4'
description = 'A python interface for accessing NetsBlox services'
url = 'https://github.com/dragazo/NetsBlox-python'
author = 'Devin Jean'
author_email = 'devin.c.jean@vanderbilt.edu'
credits = 'Institute for Software Integrated Systems, Vanderbilt University'

with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding = 'utf-8') as f:
    long_description = f.read()
