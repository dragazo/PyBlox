#!/usr/bin/env python

from setuptools import setup

# source: https://packaging.python.org/guides/making-a-pypi-friendly-readme/
from os import path
with open(path.join(path.dirname(__file__), 'README.md'), encoding = 'utf-8') as f:
    long_description = f.read()

setup(
    name = 'netsblox',
    version = '0.4.2',
    description = 'A python interface for accessing NetsBlox services',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/dragazo/NetsBlox-python',
    author = 'Devin Jean',
    author_email = 'devin.c.jean@vanderbilt.edu',
    license = 'Apache 2.0',
    packages = [ 'netsblox' ],
    install_requires = [
        'websocket-client',
        'darkdetect',
        'requests',
        'pillow',
        'numpy',
        'parso',
        'jedi',
        'mss',
    ],
    classifiers = [
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Intended Audience :: Education',
        'Topic :: Education',
        'Topic :: Internet',
    ],
)
