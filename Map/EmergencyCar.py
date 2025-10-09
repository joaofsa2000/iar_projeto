import math
import random
import time
import pygame
from Models.Directions import Directions

AMBULANCE = ['Map/Resources/Cars/ambulance_1.png', 'Map/Resources/Cars/ambulance_2.png']
POLICE = ['Map/Resources/Cars/police_1.png', 'Map/Resources/Cars/police_2.png']

directions_options = [Directions.RIGHT, Directions.LEFT, Directions.FORWARD]
spawning_points = [
    ((310, 780), 0), ((669, 780), 0), ((1034, 780), 0),  # bottom roads
    ((244, -50), 180), ((603, -50), 180), ((969, -50), 180),  # top roads
    ((-50, 201), -90), ((-50, 552), -90),  # left roads
    ((1340, 135), 90), ((1340, 486), 90)  # right roads
]


class EmergencyCar(pygame.sprite.Sprite):
    def __init__(self, screen, id):
        super().__init__()

        self.animation_index = 0
        self.animation_count = 1
        self.car_type = random.choice([POLICE, AMBULANCE])

        # Inicializa todas as variáveis do objeto
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

        # Desenha o veiculo no mapa
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()
        self.rect = self.image.get_rect(midtop=spawning_point[0])
        self.fires_car()

        # Randomiza a imagem do carro que vai ser usada e desenha no mapa
        self.activate_switching_lane()

        self.stopped_at_tl_id = False

    # Sinaliza que o carro está num semáforo
    def set_car_at_tl(self, flag=True):
        self.car_at_traffic_light = flag

    # Retorna a posição atual do carro no mapa
    def get_car_position(self):
        return (self.rect.centerx, self.rect.centery, self.angle)

    # Ativa a flag de mudança de faixa quando a viragem do carro terminar
    def flag_car_is_turning(self, flag):
        if self.car_is_turning and not flag: self.activate_switching_lane()
        self.car_is_turning = flag

    # Quando o carro sair do mapa retorna True para que seja removido do mapa
    def is_car_done(self):
        if self.rect.x < -160: return True
        if self.rect.x > 1500: return True
        if self.rect.y > 900: return True
        if self.rect.y < -160: return True

        return False

    # Ativa o carro, dando velocidade ao mesmo
    def fires_car(self, speed=2):
        self.is_car_stopped = False
        self.car_speed = speed

    # Para o carro, tirando a sua velocidade
    def stop_car(self):
        self.is_car_stopped = True
        self.car_speed = 0

    # Move o carro em frente, tendo em conta o seu angulo
    def go_forward(self):
        if self.angle > 360: self.angle = 0 + self.angle - 360
        if self.angle < -360: self.angle = 0 + self.angle + 360

        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        self.rect.x -= horizontal
        self.rect.y -= vertical

    # Calcula a próxima coordenada do carro, tendo em conta o angulo em que este se encontra
    def get_next_position(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.car_speed
        horizontal = math.sin(radians) * self.car_speed

        return ((self.rect.x - horizontal), (self.rect.y - vertical))

    # Ativa a flag de viragem
    def activate_turning(self):
        if not self.car_is_turning:
            self.is_turning = (True, self.next_turn_direction)
            self.car_is_turning = True
            self.fires_car()

    # Desativa a flag de viragem
    def ending_turning(self):
        self.is_turning = (False, '')
        self.fires_car()

    # Ativa a flag de troca de faixa e randomiza a próxima direção que o carro vai tomar
    def activate_switching_lane(self):
        self.fires_car()
        self.next_turn_direction = random.choice(directions_options)

        self.is_switching_lane = (True, self.next_turn_direction)

    # Desativa a flag de troca de faixa
    def end_switching_lane(self):
        self.is_switching_lane = (False, '')
        self.fires_car()

    # Trata da viragem do carro, chamando o método reponsável por virar o carro para a direção pretendida
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
        # Deixa o carro avançar um pouco dentro do cruzamento e só depois começa a virar
        if self.turning_ticks < 58:
            self.go_forward()
            return

        if self.turning_ticks == 60:
            self.stop_car()
            return

        # Para uma viragem fluida no mapa, o carro faz uma rotação de 90 graus, sendo que a cada update do mapa faz uma rotação de 6 graus
        if self.turning_rotation_done < 90:
            self.angle += 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # Após ser feita toda a rotação, o carro desativa a flag de viragem e segue em frente
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    def turn_right(self):
        # Deixa o carro avançar um pouco dentro do cruzamento e só depois começa a virar
        if self.turning_ticks < 25:
            self.go_forward()
            return

        if self.turning_ticks == 26:
            self.stop_car()
            return

        # Para uma viragem fluida no mapa, o carro faz uma rotação de 90 graus, sendo que a cada update do mapa faz uma rotação de 6 graus
        if self.turning_rotation_done < 90:
            self.angle -= 6
            self.turning_rotation_done += 6

            self.fires_car()
            self.go_forward()
            self.stop_car()

            self.draw()

        # Após ser feita toda a rotação, o carro desativa a flag de viragem e segue em frente
        if self.turning_rotation_done >= 90:
            self.ending_turning()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0
            self.turning_ticks = 0

    # Muda o carro de faixa
    def switch_lane(self, direction):
        # Caso o carro queira seguir em frente, não precisa de mudar de faixa
        if direction == Directions.FORWARD:
            self.fires_car()
            self.go_forward()
            self.end_switching_lane()
            return

        # Para uma viragem fluida no mapa, o carro faz uma rotação de 65 graus, sendo que a cada update do mapa faz uma rotação de 5 graus
        if self.turning_rotation_done < 65:
            self.angle = self.angle + 5 if direction == Directions.LEFT else self.angle - 5
            self.turning_rotation_done += 5

            self.fires_car(speed=3)
            self.go_forward()
            self.stop_car()

            self.draw()

        # Após ser feita toda a rotação, o carro desativa a flag de mudança de faixa e segue em frente
        if self.turning_rotation_done >= 65:
            self.angle = self.angle - self.turning_rotation_done if direction == Directions.LEFT else self.angle + self.turning_rotation_done
            self.draw()

            self.end_switching_lane()
            self.fires_car()
            self.go_forward()

            self.turning_rotation_done = 0

    # Desenha o carro no ecrã
    def draw(self):
        self.image = pygame.image.load(self.car_type[self.get_next_animation_index()]).convert_alpha()

        rotated_image = pygame.transform.rotate(self.image, self.angle)
        self.rect = rotated_image.get_rect(center=self.rect.center)

        self.screen.blit(rotated_image, self.rect.topleft)

    # Atualiza a posição do carro no mapa
    def update(self):
        if self.is_turning[0]:
            self.handle_turning()
        elif self.is_switching_lane[0]:
            self.switch_lane(self.is_switching_lane[1])
        else:
            if not self.is_car_stopped: self.fires_car(speed=4)
            self.go_forward()

    # Altera a imagem do veiculo sequencialmente para simular animação na sirene
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

    # Ativa a flag de mudança de direção
    def activate_changing_direction(self):
        self.is_changing_direction = True

    # Desativa a flag de mudança de direção
    def disable_changing_direction(self):
        self.is_changing_direction = False

    # Retorna se o carro está a mudar de direção
    def is_car_changing_direction(self):
        return self.is_changing_direction

    # Força o veiculo a mudar de faixa para seguir uma direção diferente aquela que ia seguir anteriormente
    def change_direction(self, lane):
        # Desativa a flag de viragem para cancelar a direção que ia tomar
        self.flag_car_is_turning(False)

        # Para a posição atual define para que faixas pode ir
        POSSIBLE_LANES = {
            "l": ["r"],
            "c": ["l", "r"],
            "r": ["l"],
        }

        # Dada posição atual, randomiza para que faixa vai mudar
        new_direction = random.choice(POSSIBLE_LANES[lane])

        # Dependendo da direção e do angulo do carro define em que coordenada tem que incrementar para que possa mudar de faixa
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

            # Muda a variável do objeto onde fica a direção que o carro vai tomar para a nova direção escolhida
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

            # Muda a variável do objeto onde fica a direção que o carro vai tomar para a nova direção escolhida
            self.next_turn_direction = Directions.RIGHT if lane == "c" else Directions.FORWARD