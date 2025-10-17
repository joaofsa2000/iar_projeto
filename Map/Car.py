# Map/Car.py

import math
import random
import time
import pygame
from Models.Directions import Directions

# imagens disponíveis para os veículos
RED_CAR = 'Map/Resources/Cars/carro-vermelho.png'
BLUE_CAR = 'Map/Resources/Cars/carro-azul.png'
GREEN_CAR = 'Map/Resources/Cars/carro-verde.png'
YELLOW_CAR = 'Map/Resources/Cars/carro-amarelo.png'

directions_options = [Directions.RIGHT, Directions.LEFT, Directions.FORWARD]
spawning_points = [
    ((310, 780), 0), ((669, 780), 0), ((1034, 780), 0),  # faixas inferiores
    ((244, -50), 180), ((603, -50), 180), ((969, -50), 180),  # faixas superiores
    ((-50, 201), -90), ((-50, 552), -90),  # faixas esquerdas
    ((1340, 135), 90), ((1340, 486), 90)  # faixas direitas
]


class Car(pygame.sprite.Sprite):
    def __init__(self, screen, id):
        super().__init__()

        # configura os atributos iniciais da instância
        self.id = id
        self.contador = 0
        spawning_point = random.choice(spawning_points)

        self.screen = screen
        self.car_speed = 0
        self.angle = spawning_point[1]

        self.next_turn_direction = random.choice(directions_options)

        self.car_is_turning = False
        self.car_at_traffic_light = False

        self.is_turning = (False, '')
        self.is_switching_lane = (False, '')

        self.turning_ticks = 0
        self.turning_rotation_done = 0

        # seleciona aleatoriamente uma cor e carrega a textura correspondente
        self.image = pygame.image.load(random.choice([RED_CAR, BLUE_CAR, GREEN_CAR, YELLOW_CAR])).convert_alpha()
        self.rect = self.image.get_rect(midtop=spawning_point[0])
        self.fires_car()

        # força uma mudança de faixa inicial para preparar a primeira interseção
        self.activate_switching_lane()

        self.stopped_at_tl_id = False
        self.stopped_at_tl_start_time = False

    # atualiza o estado de presença em semáforo
    def set_car_at_tl(self, flag=True):
        self.car_at_traffic_light = flag

    # devolve as coordenadas e orientação atuais
    def get_car_position(self):
        return (self.rect.centerx, self.rect.centery, self.angle)

    # inicia mudança de faixa quando a rotação termina
    def flag_car_is_turning(self, flag):
        if self.car_is_turning and not flag: self.activate_switching_lane()
        self.car_is_turning = flag

    # implementa comportamento de wraparound nas bordas do ecrã
    def infinite_car(self):
        if self.rect.x < -60: self.rect.x = 1280
        if self.rect.x > 1340: self.rect.x = 0
        if self.rect.y > 780: self.rect.bottom = 0
        if self.rect.y < -60: self.rect.top = 720

    # define a velocidade de movimento do veículo
    def fires_car(self, speed=2):
        self.car_speed = speed

    # remove toda a velocidade do veículo
    def stop_car(self):
        self.car_speed = 0

    # avança o veículo conforme a sua orientação atual
    def go_forward(self):
        if self.angle > 360: self.angle = 0 + self.angle - 360
        if self.angle < -360: self.angle = 0 + self.angle + 360

        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        self.rect.x -= horizontal
        self.rect.y -= vertical

    # prevê a próxima posição baseada na velocidade e ângulo
    def get_next_position(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        return ((self.rect.x - horizontal), (self.rect.y - vertical))

    # inicia o processo de curva no cruzamento
    def activate_turning(self):
        if not self.car_is_turning:
            self.is_turning = (True, self.next_turn_direction)
            self.car_is_turning = True

    # termina o estado de rotação ativa
    def ending_turning(self):
        self.is_turning = (False, '')

    # prepara o veículo para mudar de carril e escolhe nova direção
    def activate_switching_lane(self):
        self.next_turn_direction = random.choice(directions_options)

        self.is_switching_lane = (True, self.next_turn_direction)

    # finaliza o estado de mudança de carril
    def end_switching_lane(self):
        self.is_switching_lane = (False, '')

    # processa a lógica de rotação durante curvas
    def handle_turning(self):
        if self.is_turning[1] == Directions.FORWARD:
            self.ending_turning()
            return

        self.turning_ticks += 0 if self.car_speed == 0 else 1

        if self.is_turning[1] == Directions.RIGHT:
            self.turn_right()
            return

        if self.is_turning[1] == Directions.LEFT:
            self.turn_left()
            return

    def turn_left(self):
        # permite ao veículo entrar parcialmente na interseção antes de rodar
        if self.turning_ticks < 58:
            self.go_forward()
            return

        if self.turning_ticks == 60:
            self.stop_car()
            return

        # executa rotação gradual de 90° em incrementos de 6° por frame
        if self.turning_rotation_done < 90:
            self.angle += 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # conclui a manobra e retoma movimento linear
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    def turn_right(self):
        # aguarda posicionamento adequado antes de iniciar rotação
        if self.turning_ticks < 25:
            self.go_forward()
            return

        if self.turning_ticks == 26:
            self.stop_car()
            return

        # realiza curva suave através de rotação incremental de 6° por ciclo
        if self.turning_rotation_done < 90:
            self.angle -= 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # completa a viragem e restaura movimento normal
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    # executa transição entre faixas de rodagem
    def switch_lane(self, direction):
        # mantém trajetória reta se a direção escolhida for forward
        if direction == Directions.FORWARD:
            self.fires_car()
            self.go_forward()
            self.end_switching_lane()
            return

        # aplica rotação parcial de 65° para reposicionamento lateral
        if self.turning_rotation_done < 65:
            self.angle = self.angle + 5 if direction == Directions.LEFT else self.angle - 5
            self.turning_rotation_done += 5

            self.fires_car(speed=3)
            self.go_forward()
            self.stop_car()

            self.draw()

        # corrige orientação final e retoma trajeto principal
        if self.turning_rotation_done >= 65:
            self.angle = self.angle - self.turning_rotation_done if direction == Directions.LEFT else self.angle + self.turning_rotation_done
            self.draw()

            self.end_switching_lane()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0

    # renderiza o veículo com a rotação apropriada
    def draw(self):
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)

        self.screen.blit(rotated_image, self.rect.topleft)

    # ciclo principal de atualização do comportamento do veículo
    def update(self):
        if self.is_turning[0]:
            self.handle_turning()
        elif self.is_switching_lane[0]:
            self.switch_lane(self.is_switching_lane[1])
        else:
            self.go_forward()

        self.infinite_car()