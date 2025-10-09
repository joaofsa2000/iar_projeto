import time
from enum import Enum

# Modelos de luz
from enum import Enum

class LightStatus(Enum):
    RED = 1
    YELLOW = 2
    GREEN = 3


class TrafficLight:
    def __init__(self, red_duration=5, green_duration=5):
        self.status = LightStatus.RED
        self.red_duration = red_duration
        self.green_duration = green_duration
        self.timer = 0

    def change_status(self, status):
        if status == LightStatus.RED:
            # lógica para vermelho
            self.status = LightStatus.RED
        elif status == LightStatus.YELLOW:
            # lógica para amarelo
            self.status = LightStatus.YELLOW
        elif status == LightStatus.GREEN:
            # lógica para verde
            self.status = LightStatus.GREEN

    def can_vehicle_pass(self, is_emergency=False):
        """Veículos de emergência podem passar sempre"""
        if is_emergency:
            return True
        return self.status == LightStatus.GREEN

# Exemplo de simulação
if __name__ == "__main__":
    traffic_light = TrafficLight(red_duration=3, green_duration=3)

    for t in range(12):  # Simula 12 ciclos de tempo
        traffic_light.update()
        print(f"Tempo {t}: Luz {traffic_light.status.name}")
        print("Veículo normal pode passar?", traffic_light.can_vehicle_pass(False))
        print("Veículo de emergência pode passar?", traffic_light.can_vehicle_pass(True))
        time.sleep(1)
