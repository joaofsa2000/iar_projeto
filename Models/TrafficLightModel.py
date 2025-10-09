#Models/TrafficLightModel.py

class CrossingTrafficLightModel:
    def __init__(self, id, bottom_tl, top_tl, left_tl, right_tl):
        self.id = id

        self.bottom_tl = bottom_tl
        self.top_tl = top_tl
        self.left_tl = left_tl
        self.right_tl = right_tl

class SideTrafficLightModel:
    def __init__(self, left_tl, center_tl, right_tl):
        self.left_tl = left_tl
        self.center_tl = center_tl
        self.right_tl = right_tl

class TrafficLightModel:
    def __init__(self, coordinate, angle, status):
        self.coordinate = coordinate
        self.angle = angle
        self.status = status
