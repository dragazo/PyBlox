'''
A python client for accessing NetsBlox
'''

from .client import *

from pkg_resources import get_distribution

__version__ = get_distribution('netsblox').version
__author__ = 'Devin Jean'
__credits__ = 'Institute for Software Integrated Systems, Vanderbilt University'
