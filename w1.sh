#!/usr/bin/env bash

sleep 2
sudo rm -rf ./__pycache__

sudo python3 /home/pi/weather1.py $*

