#Models/CoordinateModel.py

class CoordinateModel:
    def __init__(self, x, y, size, angle):
        # armazena posição horizontal do elemento
        self.x = x
        # armazena posição vertical do elemento
        self.y = y
        # define dimensão ou raio de influência
        self.size = size
        # guarda orientação angular em graus
        self.angle = angle