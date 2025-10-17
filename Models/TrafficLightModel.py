#Models/TrafficLightModel.py

class CrossingTrafficLightModel:
    def __init__(self, id, bottom_tl, top_tl, left_tl, right_tl):
        # identificador único do cruzamento
        self.id = id

        # semáforo da aproximação inferior
        self.bottom_tl = bottom_tl
        # semáforo da aproximação superior
        self.top_tl = top_tl
        # semáforo da aproximação esquerda
        self.left_tl = left_tl
        # semáforo da aproximação direita
        self.right_tl = right_tl

class SideTrafficLightModel:
    def __init__(self, left_tl, center_tl, right_tl):
        # semáforo da faixa esquerda
        self.left_tl = left_tl
        # semáforo da faixa central
        self.center_tl = center_tl
        # semáforo da faixa direita
        self.right_tl = right_tl

class TrafficLightModel:
    def __init__(self, coordinate, angle, status):
        # posição espacial do semáforo
        self.coordinate = coordinate
        # orientação angular em graus
        self.angle = angle
        # estado luminoso atual
        self.status = status