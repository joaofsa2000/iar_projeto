#Map/Intersection.py

import pygame


class Intersection(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()

        #Desenha a interseção no mapa
        self.image = pygame.image.load('Map/Resources/Intersection.png').convert_alpha()
        self.rect = self.image.get_rect(topleft=(x, y))
