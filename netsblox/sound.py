import threading as _threading
import time as _time
import os as _os
import sys as _sys

from typing import Union, Any

class _StdoutSilencer:
    def __enter__(self):
        self.__devnull = open(_os.devnull, 'w')
        self.__stdout = _sys.stdout
        _sys.stdout = self.__devnull
    def __exit__(self, *args):
        _sys.stdout = self.__stdout
        self.__devnull.close()

with _StdoutSilencer():
    import pygame as _pg

_SOUND_LOCK = _threading.Lock()
_SOUND_DID_INIT = False
_SOUND_IS_PAUSED = False

def init():
    '''
    Initializes the sound module for playback.
    When using PyBlox, this is done automatically.
    '''
    global _SOUND_DID_INIT
    with _SOUND_LOCK:
        if not _SOUND_DID_INIT:
            _pg.mixer.init()
            _pg.mixer.set_num_channels(256) # doing this in init seems to speed up playback for some reason
            _SOUND_DID_INIT = True

def stop():
    '''
    Stops the playback of any currently-playing sounds.
    This does not prevent future sounds from being played.
    '''
    with _SOUND_LOCK:
        _pg.mixer.stop()

def is_paused() -> bool:
    '''
    Checks if the playback of sounds is currently paused.
    '''
    with _SOUND_LOCK:
        return _SOUND_IS_PAUSED

def pause() -> None:
    '''
    Pauses the playback of sounds.
    Any sounds that are played while paused will begin upon unpausing.
    '''
    global _SOUND_IS_PAUSED
    with _SOUND_LOCK:
        _pg.mixer.pause()
        _SOUND_IS_PAUSED = True

def unpause() -> None:
    '''
    Unpauses and resumes the playback of sounds.
    Any sounds that were played while paused will begin upon unpausing.
    '''
    global _SOUND_IS_PAUSED
    with _SOUND_LOCK:
        _pg.mixer.unpause()
        _SOUND_IS_PAUSED = False

class Sound:
    def __init__(self, raw: Union['Sound', _pg.mixer.Sound, Any]):
        if type(raw) is Sound:
            raw = raw.__raw
        elif type(raw) is not _pg.mixer.Sound:
            raw = _pg.mixer.Sound(raw)
        assert type(raw) is _pg.mixer.Sound
        self.__raw = raw

    def play(self, wait: bool = False) -> None:
        '''
        Plays this sound.
        If `wait` is set to `True`, then this function will wait until the sound is finished playing.
        Otherwise, this function will return immediately and the sound will play in the background.
        '''
        with _SOUND_LOCK:
            channel = _pg.mixer.find_channel(force = True)
            channel.play(self.__raw)
        if wait:
            _time.sleep(self.__raw.get_length())

    @property
    def duration(self) -> float:
        '''
        The duration of the sound in seconds.
        '''
        return self.__raw.get_length()
