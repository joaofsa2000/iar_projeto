import math
import random
import time
import pygame
from Models.Directions import Directions

AMBULANCE = ['Map/Resources/Cars/ambulancia-1.png', 'Map/Resources/Cars/ambulancia-2.png']
POLICE = ['Map/Resources/Cars/policia-1.png', 'Map/Resources/Cars/policia-2.png']

directions_options = [Directions.RIGHT, Directions.LEFT, Directions.FORWARD]
spawning_points = [
    ((310, 780), 0), ((669, 780), 0), ((1034, 780), 0),  # faixas inferiores
    ((244, -50), 180), ((603, -50), 180), ((969, -50), 180),  # faixas superiores
    ((-50, 201), -90), ((-50, 552), -90),  # faixas esquerdas
    ((1340, 135), 90), ((1340, 486), 90)  # faixas direitas
]


class EmergencyCar(pygame.sprite.Sprite):
    def __init__(self, screen, id):
        super().__init__()

        self.animation_index = 0
        self.animation_count = 1
        self.car_type = random.choice([POLICE, AMBULANCE])

        # configura os parâmetros iniciais da instância
        self.id = id
        self.contador = 0
        spawning_point = random.choice(spawning_points)

        self.screen = screen
        self.car_speed = 0
        self.angle = spawning_point[1]

        self.next_turn_direction = random.choice(directions_options)

        self.is_car_stopped = False
        self.car_is_turning = False
        self.car_at_traffic_light = False

        self.is_turning = (False, '')
        self.is_switching_lane = (False, '')
        self.is_changing_direction = False

        self.turning_ticks = 0
        self.turning_rotation_done = 0

        # carrega a textura inicial do veículo de emergência
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        self.rect = self.image.get_rect(midtop=spawning_point[0])
        self.fires_car()

        # inicializa mudança de faixa para preparar primeira decisão
        self.activate_switching_lane()

        self.stopped_at_tl_id = False

    # atualiza o indicador de presença em zona de semáforo
    def set_car_at_tl(self, flag=True):
        self.car_at_traffic_light = flag

    # obtém as coordenadas e orientação atual do veículo
    def get_car_position(self):
        return (self.rect.centerx, self.rect.centery, self.angle)

    # dispara mudança de carril ao concluir manobra de curva
    def flag_car_is_turning(self, flag):
        if self.car_is_turning and not flag: self.activate_switching_lane()
        self.car_is_turning = flag

    # verifica se o veículo saiu dos limites do mapa
    def is_car_done(self):
        if self.rect.x < -160: return True
        if self.rect.x > 1500: return True
        if self.rect.y > 900: return True
        if self.rect.y < -160: return True

        return False

    # atribui velocidade ao veículo e marca como ativo
    def fires_car(self, speed=2):
        self.is_car_stopped = False
        self.car_speed = speed

    # anula a velocidade e marca veículo como parado
    def stop_car(self):
        self.is_car_stopped = True
        self.car_speed = 0

    # desloca o veículo segundo a direção angular atual
    def go_forward(self):
        if self.angle > 360: self.angle = 0 + self.angle - 360
        if self.angle < -360: self.angle = 0 + self.angle + 360

        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        self.rect.x -= horizontal
        self.rect.y -= vertical

    # determina futura posição baseada em velocidade e orientação
    def get_next_position(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        return ((self.rect.x - horizontal), (self.rect.y - vertical))

    # começa processo de conversão na interseção
    def activate_turning(self):
        if not self.car_is_turning:
            self.is_turning = (True, self.next_turn_direction)
            self.car_is_turning = True
            self.fires_car()

    # encerra estado de rotação ativa
    def ending_turning(self):
        self.is_turning = (False, '')
        self.fires_car()

    # inicia transição entre faixas e define próxima trajetória
    def activate_switching_lane(self):
        self.fires_car()
        self.next_turn_direction = random.choice(directions_options)

        self.is_switching_lane = (True, self.next_turn_direction)

    # completa mudança de carril
    def end_switching_lane(self):
        self.is_switching_lane = (False, '')
        self.fires_car()

    # coordena lógica de execução das curvas
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
        # avança parcialmente no cruzamento antes de iniciar rotação
        if self.turning_ticks < 58:
            self.go_forward()
            return

        if self.turning_ticks == 60:
            self.stop_car()
            return

        # efetua rotação progressiva de 90° em passos de 6° por atualização
        if self.turning_rotation_done < 90:
            self.angle += 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # finaliza manobra e retoma deslocamento linear
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    def turn_right(self):
        # permite entrada controlada na interseção antes de curvar
        if self.turning_ticks < 25:
            self.go_forward()
            return

        if self.turning_ticks == 26:
            self.stop_car()
            return

        # aplica rotação gradual de 90° através de incrementos de 6°
        if self.turning_rotation_done < 90:
            self.angle -= 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # conclui viragem e prossegue em linha reta
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    # executa reposicionamento lateral na via
    def switch_lane(self, direction):
        # mantém curso reto quando não há necessidade de ajuste lateral
        if direction == Directions.FORWARD:
            self.fires_car()
            self.go_forward()
            self.end_switching_lane()
            return

        # realiza ajuste angular de 65° para transição de faixa
        if self.turning_rotation_done < 65:
            self.angle = self.angle + 5 if direction == Directions.LEFT else self.angle - 5
            self.turning_rotation_done += 5

            self.fires_car(speed=3)
            self.go_forward()
            self.stop_car()

            self.draw()

        # restaura orientação original após reposicionamento
        if self.turning_rotation_done >= 65:
            self.angle = self.angle - self.turning_rotation_done if direction == Directions.LEFT else self.angle + self.turning_rotation_done
            self.draw()

            self.end_switching_lane()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0

    # renderiza sprite com rotação e frame de animação adequados
    def draw(self):
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()

        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)

        self.screen.blit(rotated_image, self.rect.topleft)

    # ciclo principal de comportamento do veículo emergência
    def update(self):
        if self.is_turning[0]:
            self.handle_turning()
        elif self.is_switching_lane[0]:
            self.switch_lane(self.is_switching_lane[1])
        else:
            if not self.is_car_stopped: self.fires_car(speed=4)
            self.go_forward()

    # alterna frames da textura para simular piscar das sirenes
    def get_next_animation_index(self):
        animation_frame = 20
        max_index = len(self.car_type) - 1

        if (animation_frame / self.animation_count) == 1:
            self.animation_index += 1
            if self.animation_index > max_index: self.animation_index = 0
            self.animation_count = 1
        else:
            self.animation_count += 1

        return self.animation_index

    # marca início de alteração de trajetória
    def activate_changing_direction(self):
        self.is_changing_direction = True

    # remove marca de alteração de trajetória
    def disable_changing_direction(self):
        self.is_changing_direction = False

    # verifica se há mudança de direção em progresso
    def is_car_changing_direction(self):
        return self.is_changing_direction

    # força ajuste de trajetória para faixa diferente da planeada
    def change_direction(self, lane):
        # cancela direção previamente configurada
        self.flag_car_is_turning(False)

        # mapeia transições válidas entre faixas
        POSSIBLE_LANES = {
            "l": ["r"],
            "c": ["l", "r"],
            "r": ["l"],
        }

        # escolhe aleatoriamente destino de mudança de faixa
        new_direction = random.choice(POSSIBLE_LANES[lane])

        # ajusta posição horizontal/vertical conforme ângulo e faixa destino
        if new_direction == "l":
            if self.angle == 0:
                self.rect.x -= 24
            elif self.angle == 90:
                self.rect.y += 24
            elif self.angle == 180:
                self.rect.x += 24
            elif self.angle == 270:
                self.rect.y -= 24
            elif self.angle == 360:
                self.rect.x -= 24
            elif self.angle == -90:
                self.rect.y -= 24
            elif self.angle == -180:
                self.rect.x += 24
            elif self.angle == -270:
                self.rect.y += 24
            elif self.angle == -360:
                self.rect.x -= 24

            # redefine próxima conversão baseada na faixa atual
            self.next_turn_direction = Directions.LEFT if lane == "c" else Directions.FORWARD

        if new_direction == "r":
            if self.angle == 0:
                self.rect.x += 24
            elif self.angle == 90:
                self.rect.y -= 24
            elif self.angle == 180:
                self.rect.x -= 24
            elif self.angle == 270:
                self.rect.y += 24
            elif self.angle == 360:
                self.rect.x += 24
            elif self.angle == -90:
                self.rect.y += 24
            elif self.angle == -180:
                self.rect.x -= 24
            elif self.angle == -270:
                self.rect.y -= 24
            elif self.angle == -360:
                self.rect.x += 24

            # atualiza próxima manobra de acordo com nova posição
            self.next_turn_direction = Directions.RIGHT if lane == "c" else Directions.FORWARD