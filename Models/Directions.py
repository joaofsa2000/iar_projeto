#Models/Directions.py

from enum import Enum

class Directions(Enum):
    # representa viragem à direita
    RIGHT = 1
    # representa viragem à esquerda
    LEFT = 2
    # representa movimento em linha reta
    FORWARD = 3