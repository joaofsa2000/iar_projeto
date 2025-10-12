
import csv
import random
import pygame

from datetime import datetime
from Map.Car import Car
from Map.Crash import Crash
from Map.EmergencyCar import EmergencyCar

from Map.Intersection import Intersection
from Map.TrafficLight import TrafficLight

CRASH_POSITIONS = {
    "top_left": [("l", (153, 132)), ("r", (363, 198)), ("b", (225, 269)), ("t", (293, 59))],
    "top_mid": [("t", (651, 59)), ("l", (512, 131)), ("r", (722, 198)), ("b", (584, 268))],
    "top_right": [("b", (948, 269)), ("r", (1088, 197)), ("t", (1016, 59)), ("l", (876, 131))],
    "bottom_left": [("t", (291, 406)), ("r", (364, 546)), ("b", (225, 618)), ("l", (155, 482))],
    "bottom_mid": [("b", (583, 618)), ("r", (722, 547)), ("t", (649, 409)), ("l",(512, 481))],
    "bottom_right": [("l", (876, 480)), ("t", (1015, 409)), ("r", (1088, 547)), ("b", (948, 620))]
}

class Environment:
    def __init__(self):
        #Define o ecrã do ambiente
        self.screen = pygame.display.set_mode((1280, 720))
        self.bg_surf = pygame.image.load('Map/Resources/fundo.png').convert()
        self.clock = pygame.time.Clock()

        #Array com os dias da semana e horas do dia
        self.DAYS_OF_WEEK = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sabado']
        self.TIMES_OF_DAY = ['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12',
                             '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23']

        #Definição das interseções/cruzamentos
        self.intersections = pygame.sprite.Group()
        self.intersections.add(Intersection(193, 450))  # bottom_left_intersection
        self.intersections.add(Intersection(552, 450))  # bottom_mid_intersection
        self.intersections.add(Intersection(917, 450))  # bottom_right_intersection
        self.intersections.add(Intersection(193, 100))  # top_left_intersection
        self.intersections.add(Intersection(552, 100))  # top_mid_intersection
        self.intersections.add(Intersection(917, 100))  # top_right_intersection

        #Randomiza uma hora e um dia para a simulação
        self.day_of_week = random.choice(self.DAYS_OF_WEEK)
        self.time_of_day = random.choice(self.TIMES_OF_DAY)

        #Array com todos os carros e carros de emergencia do ambiente
        self.cars = []
        self.emergency_cars = []
        self.emergency_cars_awaiting_time = {}

        #Array com todos os semáforos do ambiente
        self.traffic_lights = pygame.sprite.Group()
        self.traffic_lights_objects = {}
        self.traffic_lights_agents_tl = {}

        #Array com as posições dos carros
        self.car_positions = {}

        #Array com os estados dos semáforos
        self.traffic_lights_status = {}

        # Carros parados nos semaforos
        self.cars_stopped_at_tl = {}

        # Tempos de expera para registar num ficheiro excel
        self.cars_stopped_times = []

        #Flag de acidente no mapa e localização da mesma caso exista
        self.map_crash = False
        self.crash_position = (0, 0)
        self.crash_location = ""

    #Valida se existe colisão de um carro com um cruzamento
    #Se sim, retorna True, se não retorno False
    def collision_sprite(self, sprite):
        if pygame.sprite.spritecollide(sprite, self.intersections, False):
            return True
        else:
            return False

    #Guarda registo em fx CSV
    def write_on_csv(self, data):
        file_name = "espera_carros_lista.csv"

        with open(file_name, 'a', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(data)

        print('Records saved on file with name: ' + file_name)

    #Verifica se um determinado carro está num semáforo
    def collision_traffic_light(self, sprite):
        coll = pygame.sprite.spritecollide(sprite, self.traffic_lights, False)
        if coll:
            return (True, coll[0].id)
        else:
            return (False, 0)

    #Atualiza o mapa pygame
    def update_map(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.write_on_csv(self.cars_stopped_times)
                pygame.quit()
                exit()

        self.intersections.draw(self.screen)

        self.screen.blit(self.bg_surf, (0, 0))

        if self.map_crash:
            self.collisions.draw(self.screen)

        #Desenha todos os semáforos no mapa
        for tl in self.traffic_lights:
            tl.draw()

        #Desenha todos os carros no mapa
        for car in self.cars:
            car.sprites()[0].draw()

        #Desenha todos os veiculos de emergencia no mapa
        for emergency_car in self.emergency_cars:
            emergency_car.sprites()[0].draw()

        #Apresenta no canto da janela a hora e o dia da simulação
        pygame.font.init()
        padding = 20
        font_size = 14
        font = pygame.font.SysFont('Sans', font_size, bold=True)
        clock = font.render(str(self.day_of_week) + ', ' + str(self.time_of_day) + ':00', True, (255, 255, 255))
        clock_surf = pygame.Surface((clock.get_size()[0] + padding, clock.get_size()[1] + padding))
        clock_surf.fill((0, 0, 0))
        clock_surf.blit(clock, (padding / 2, padding / 2))
        self.screen.blit(clock_surf, (0, 720 - font_size - padding))

        pygame.display.update()
        self.clock.tick(60)

    #Adiciona um novo carro ao ambiente
    #Retorna o objecto criado de volta para o agente, para que possam ser feitas alterações no seu estado
    def add_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(Car(self.screen, str(car_id).replace("car_", "").replace("@localhost", "")))
        self.cars.append(car)

        self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    #Obtem um carro pelo seu ID
    def get_car_by_id(self, car_id):
        for car_group in self.cars:
            if car_group.sprites() and car_group.sprites()[0].id:
                car_full_id = 'car_' + car_group.sprites()[0].id + "@localhost"
                if car_full_id == car_id:
                    return car_group
        return None

    #Atualiza a posição de um carro
    def update_car_position(self, car_id, car_pos):
        self.car_positions[car_id] = (car_pos[0], car_pos[1], car_pos[2])
        #print(car_id, self.car_positions[car_id])

    #Devolve o array com as posições de todos os carros:
    def get_car_positions(self):
        return self.car_positions

    #Adiciona um novo semáforo ao ambiente
    #Retorna o objecto criado de volta para o agente, para que possam ser feitas alterações no seu estado
    def add_traffic_light(self, tl_jid, tl_id, tl_pos, angle):
        tl = TrafficLight(self.screen, tl_id, tl_pos, angle)
        self.traffic_lights.add(tl)

        self.traffic_lights_objects[str(tl_id)] = tl
        self.traffic_lights_agents_tl[str(tl_id)] = tl_jid
        self.traffic_lights_status[str(tl_id)] = tl.get_status()

        return tl

    #Atualiza o estado do semáforo
    def update_traffic_light_status(self, tl_id, status):
        self.traffic_lights_status[tl_id] = status

    #Retorna o estado do semáforo pelo ID
    def get_traffic_light_status(self, tl_id):
        return self.traffic_lights_status[str(tl_id)]

    #Retorna o JID do agente pelo id do semáforo
    def get_traffic_light_jid_by_id(self, tl_id):
        return self.traffic_lights_agents_tl[str(tl_id)]

    #Adiciona um novo carro de emergencia ao ambiente
    #Retorna o objecto criado de volta para o agente, para que possam ser feitas alterações no seu estado
    def add_emergency_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(EmergencyCar(self.screen, str(car_id).replace("car_", "").replace("@localhost", "")))
        self.emergency_cars.append(car)

        #self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    #Ativa a flag de acidente no mapa
    def activate_map_crash(self, crossing):
        self.map_crash = True
        self.crash_position = random.choice(CRASH_POSITIONS[crossing])

        self.crash_location = crossing + "_" + self.crash_position[0]

        self.collisions = pygame.sprite.Group()
        self.collisions.add(Crash(self.crash_position[1]))

    #Desativa a flag de acidente no mapa
    def deactivate_map_crash(self):
        self.map_crash = False

    #Dada posição do acidente e do carro no cruzamento, retorna a direção bloqueada que o carro não pode seguir
    def determine_restricted_turn(self, crash_position, car_position):
        restrictions = {
            ('r', 't'): "l",
            ('r', 'b'): "r",
            ('r', 'l'): "c",
            ('l', 't'): "r",
            ('l', 'b'): "l",
            ('l', 'r'): "c",
            ('t', 'l'): "l",
            ('t', 'r'): "r",
            ('t', 'b'): "c",
            ('b', 'l'): "r",
            ('b', 'r'): "l",
            ('b', 't'): "c",
        }

        return restrictions.get((crash_position, car_position), "")

    #Dada um acidente e um carro, retorna se o carro possui alguma restrição no seu percurso
    def get_blocked_turn(self, tl, crash):
        tl_to_open_txt_arr = str(tl).split("_")
        crash_location_txt_arr = str(crash).split("_")

        blocked_turn = ""
        if self.map_crash and (tl_to_open_txt_arr[0] + tl_to_open_txt_arr[1]) == (crash_location_txt_arr[0] + crash_location_txt_arr[1]):
            blocked_turn = self.determine_restricted_turn(crash_location_txt_arr[2], tl_to_open_txt_arr[2])

        return blocked_turn