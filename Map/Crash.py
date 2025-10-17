#Map/Crash.py

import pygame


class Crash(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__()

        # carrega e posiciona o sprite de bloqueio na localização especificada
        self.image = pygame.image.load('Map/Resources/bloqueio.png').convert_alpha()
        self.rect = self.image.get_rect(topleft=position)