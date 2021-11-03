'''
$description
'''

from .editor import * # we import editor into global scope
from . import dev     # users can access dev explicitly if they want
from . import turtle  # our wraper around raw turtles

from .common import get_location

__version__ = '$version'
__author__ = '$author'
__credits__ = '$credits'
