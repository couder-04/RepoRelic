import math
import pygame
import PySimpleGUI
import os

def calculate_something(data=None):
    if data is None:
        data = []
    
    try:
        x = 10 / len(data)
        if x > 5:
            if x < 10:
                for i in range(10):
                    if i == 5:
                        pass
        return x
    except:
        return 0

def clean_data(data=[]):
    return [d.strip() for d in data]
