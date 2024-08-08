import netsblox
import threading
import time
import os
import sys

from typing import Union, Any

class StdoutSilencer:
    def __enter__(self):
        self.__devnull = open(os.devnull, 'w')
        self.__stdout = sys.stdout
        sys.stdout = self.__devnull
    def __exit__(self, *args):
        sys.stdout = self.__stdout
        self.__devnull.close()

with StdoutSilencer():
    import pygame as pg

SOUND_LOCK = threading.Lock()

_did_init_flag = False
def init():
    global _did_init_flag
    with SOUND_LOCK:
        if not _did_init_flag:
            pg.mixer.init()
            pg.mixer.set_num_channels(256) # doing this in init seems to speed up playback for some reason
            _did_init_flag = True

class Sound:
    def __init__(self, raw: Union['Sound', pg.mixer.Sound, Any]):
        if type(raw) is Sound:
            raw = raw.__raw
        elif type(raw) is not pg.mixer.Sound:
            raw = pg.mixer.Sound(raw)
        assert type(raw) is pg.mixer.Sound
        self.__raw = raw

    def play(self, wait: bool = False) -> None:
        '''
        Plays this sound.
        If `wait` is set to `True`, then this function will wait until the sound is finished playing.
        Otherwise, this function will return immediately and the sound will play in the background.
        '''
        with SOUND_LOCK:
            channel = pg.mixer.find_channel(force = True)
            channel.play(self.__raw)
        if wait:
            time.sleep(self.__raw.get_length())

    @property
    def duration(self) -> float:
        '''
        The length of the sound in seconds.
        '''
        return self.__raw.get_length()
