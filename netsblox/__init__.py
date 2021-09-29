'''
A python client for accessing NetsBlox
'''

from .editor import * # we import editor into global scope
from . import dev     # users can access dev explicitly if they want
from . import turtle  # our wraper around raw turtles

from .common import get_location

from pkg_resources import get_distribution as _get_distribution

__version__ = _get_distribution('netsblox').version
__author__ = 'Devin Jean'
__credits__ = 'Institute for Software Integrated Systems, Vanderbilt University'
