'''
$description
'''

from .editor import * # we import editor into global scope
from . import dev     # users can access dev explicitly if they want
from . import turtle
from . import snap
from . import rooms

from .common import get_location, get_error, nothrow

__version__ = '$version'
__author__ = '$author'
__credits__ = '$credits'
