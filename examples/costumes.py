#!/usr/bin/env python

import netsblox
from netsblox.turtle import *
import time
import random

client = netsblox.Client()
google_maps = client.google_maps
this_x_dne = client.this_x_does_not_exist

@turtle
class MyTurtle:
    @onstart
    def start(self):
        while True:
            img = this_x_dne.get_cat()
            img = img.resize((img.width // 5, img.height // 5)) # a bit too big - make it smaller
            self.setcostume(img)

            x = (random.random() - 0.5) * 900
            y = (random.random() - 0.5) * 500
            self.goto(x, y)

            time.sleep(1)
t = MyTurtle()

@stage
class MyStage:
    @onstart
    def start(self):
        while True:
            lat = random.random() + 36.152056
            long = random.random() + -86.811432
            img = google_maps.get_map(lat, long, 1000, 600, 12)
            self.setcostume(img)

            time.sleep(2)
stage = MyStage()

start_project()
