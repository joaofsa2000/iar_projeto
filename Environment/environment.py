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
        # estabelece janela de visualização e recursos gráficos base
        self.screen = pygame.display.set_mode((1280, 720))
        self.bg_surf = pygame.image.load('Map/Resources/fundo.png').convert()
        self.clock = pygame.time.Clock()

        # cria conjunto de cruzamentos no mapa
        self.intersections = pygame.sprite.Group()
        self.intersections.add(Intersection(193, 450))  # cruzamento inferior esquerdo
        self.intersections.add(Intersection(552, 450))  # cruzamento inferior central
        self.intersections.add(Intersection(917, 450))  # cruzamento inferior direito
        self.intersections.add(Intersection(193, 100))  # cruzamento superior esquerdo
        self.intersections.add(Intersection(552, 100))  # cruzamento superior central
        self.intersections.add(Intersection(917, 100))  # cruzamento superior direito

        # estruturas de dados para gestão de veículos
        self.cars = []
        self.emergency_cars = []
        self.emergency_cars_awaiting_time = {}
        self.car_positions = {}
        self.cars_stopped_at_tl = {}

        # estruturas de dados para gestão de semáforos
        self.traffic_lights = pygame.sprite.Group()
        self.traffic_lights_objects = {}
        self.traffic_lights_agents_tl = {}
        self.traffic_lights_status = {}

        self.cars_stopped_times = []


        self.map_crash = False
        self.crash_position = (0, 0)
        self.crash_location = ""

    def collision_sprite(self, sprite):
        if pygame.sprite.spritecollide(sprite, self.intersections, False):
            return True
        else:
            return False


    # persiste dados de espera em ficheiro CSV para análise posterior
    def write_on_csv(self, data):
        file_name = "espera_carros_lista.csv"

        with open(file_name, 'a', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(data)

        print('Records saved on file with name: ' + file_name)

    # deteta colisão entre veículo e zona de semáforo
    def collision_traffic_light(self, sprite):
        coll = pygame.sprite.spritecollide(sprite, self.traffic_lights, False)
        if coll:
            return (True, coll[0].id)
        else:
            return (False, 0)

    # processa ciclo de renderização da simulação
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

        # renderiza todos os semáforos ativos
        for tl in self.traffic_lights:
            tl.draw()

        # renderiza veículos comuns
        for car in self.cars:
            car.sprites()[0].draw()

        # renderiza veículos de emergência
        for emergency_car in self.emergency_cars:
            emergency_car.sprites()[0].draw()

        pygame.display.update()
        self.clock.tick(60)


    def add_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(Car(self.screen, str(car_id).replace("car_", "").replace("@localhost", "")))
        self.cars.append(car)

        self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    def get_car_by_id(self, car_id):
        for car_group in self.cars:
            if car_group.sprites() and car_group.sprites()[0].id:
                car_full_id = 'car_' + car_group.sprites()[0].id + "@localhost"
                if car_full_id == car_id:
                    return car_group
        return None

    # atualiza coordenadas e orientação de veículo específico
    def update_car_position(self, car_id, car_pos):
        self.car_positions[car_id] = (car_pos[0], car_pos[1], car_pos[2])
        #print(car_id, self.car_positions[car_id])

    # retorna dicionário com localização de todos os veículos
    def get_car_positions(self):
        return self.car_positions

    def add_traffic_light(self, tl_jid, tl_id, tl_pos, angle):
        tl = TrafficLight(self.screen, tl_id, tl_pos, angle)
        self.traffic_lights.add(tl)

        self.traffic_lights_objects[str(tl_id)] = tl
        self.traffic_lights_agents_tl[str(tl_id)] = tl_jid
        self.traffic_lights_status[str(tl_id)] = tl.get_status()

        return tl

    # modifica fase luminosa de semáforo específico
    def update_traffic_light_status(self, tl_id, status):
        self.traffic_lights_status[tl_id] = status

    # consulta estado atual de semáforo por identificador
    def get_traffic_light_status(self, tl_id):
        return self.traffic_lights_status[str(tl_id)]

    # obtém identificador do agente responsável por semáforo
    def get_traffic_light_jid_by_id(self, tl_id):
        return self.traffic_lights_agents_tl[str(tl_id)]

    # instancia novo veículo de emergência no ambiente
    # devolve referência para controlo pelo agente correspondente
    def add_emergency_car(self, car_id):
        car = pygame.sprite.GroupSingle()
        car.add(EmergencyCar(self.screen, str(car_id).replace("car_", "").replace("@localhost", "")))
        self.emergency_cars.append(car)

        #self.car_positions[str(car_id)] = car.sprites()[0].get_car_position()

        return car

    # ativa condição de bloqueio por acidente em cruzamento
    def activate_map_crash(self, crossing):
        self.map_crash = True
        self.crash_position = random.choice(CRASH_POSITIONS[crossing])

        self.crash_location = crossing + "_" + self.crash_position[0]

        self.collisions = pygame.sprite.Group()
        self.collisions.add(Crash(self.crash_position[1]))

    # remove condição de bloqueio por acidente
    def deactivate_map_crash(self):
        self.map_crash = False

    # calcula faixa bloqueada baseada em posição relativa do acidente
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

    # verifica se veículo enfrenta restrição de trajetória devido a acidente
    def get_blocked_turn(self, tl, crash):
        tl_to_open_txt_arr = str(tl).split("_")
        crash_location_txt_arr = str(crash).split("_")

        blocked_turn = ""
        if self.map_crash and (tl_to_open_txt_arr[0] + tl_to_open_txt_arr[1]) == (crash_location_txt_arr[0] + crash_location_txt_arr[1]):
            blocked_turn = self.determine_restricted_turn(crash_location_txt_arr[2], tl_to_open_txt_arr[2])

        return blocked_turn