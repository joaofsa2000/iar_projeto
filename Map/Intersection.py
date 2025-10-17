#Map/Intersection.py

import pygame


class Intersection(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()

        # carrega e posiciona o sprite da interseção nas coordenadas fornecidas
        self.image = pygame.image.load('Map/Resources/intersecao.png').convert_alpha()
        self.rect = self.image.get_rect(topleft=(x, y))