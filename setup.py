#!/usr/bin/env python

from setuptools import setup

import meta

setup(
    name = meta.name,
    version = meta.version,
    description = meta.description,
    long_description = meta.long_description,
    long_description_content_type = 'text/markdown',
    url = meta.url,
    author = meta.author,
    author_email = meta.author_email,
    license = 'Apache 2.0',
    packages = [ 'netsblox' ],
    install_requires = [
        'websocket-client',
        'darkdetect',
        'randomname',
        'requests',
        'gelidum',
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
