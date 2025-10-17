# Map/TrafficLigth.py

import math
import random
import pygame

from Models.LightStatus import LightStatus

RED_LIGHT = 'Map/Resources/TrafficLights/vermelho.png'
YELLOW_LIGHT = 'Map/Resources/TrafficLights/carro-amarelo.png'
GREEN_LIGHT = 'Map/Resources/TrafficLights/verde.png'


class TrafficLight(pygame.sprite.Sprite):
    def __init__(self, screen, tl_id, tl_pos, angle):
        super().__init__()

        self.screen = screen

        # configura identificador, estado inicial e orientação do semáforo
        self.id = tl_id
        self.status = LightStatus.RED
        self.angle = angle

        self.image = pygame.image.load(RED_LIGHT).convert_alpha()
        self.rect = self.image.get_rect(topleft=tl_pos)

    # atualiza a fase do semáforo carregando a textura correspondente
    def change_status(self, status):
        if status == LightStatus.RED:
            self.image = pygame.image.load(RED_LIGHT).convert_alpha()
        elif status == LightStatus.YELLOW:
            self.image = pygame.image.load(YELLOW_LIGHT).convert_alpha()
        else:
            self.image = pygame.image.load(GREEN_LIGHT).convert_alpha()

        self.status = status

    # renderiza o semáforo com a rotação apropriada
    def draw(self):
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)

        self.screen.blit(rotated_image, self.rect.topleft)

    # obtém o estado luminoso atual
    def get_status(self):
        return self.status