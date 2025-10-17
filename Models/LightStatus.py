import time
from enum import Enum

# Enumeração dos estados luminosos
from enum import Enum

class LightStatus(Enum):
    # sinal de paragem obrigatória
    RED = 1
    # fase de transição antes de vermelho
    YELLOW = 2
    # autorização de passagem
    GREEN = 3


class TrafficLight:
    def __init__(self, red_duration=5, green_duration=5):
        self.status = LightStatus.RED
        self.red_duration = red_duration
        self.green_duration = green_duration
        self.timer = 0

    def change_status(self, status):
        if status == LightStatus.RED:
            # configura sinal para paragem
            self.status = LightStatus.RED
        elif status == LightStatus.YELLOW:
            # configura sinal para precaução
            self.status = LightStatus.YELLOW
        elif status == LightStatus.GREEN:
            # configura sinal para passagem livre
            self.status = LightStatus.GREEN

    def can_vehicle_pass(self, is_emergency=False):
        """Veículos prioritários têm passagem garantida independentemente do sinal"""
        if is_emergency:
            return True
        return self.status == LightStatus.GREEN

# Rotina de teste da lógica do semáforo
if __name__ == "__main__":
    traffic_light = TrafficLight(red_duration=3, green_duration=3)

    for t in range(12):  # Executa 12 iterações temporais
        traffic_light.update()
        print(f"Tempo {t}: Luz {traffic_light.status.name}")
        print("Veículo normal pode passar?", traffic_light.can_vehicle_pass(False))
        print("Veículo de emergência pode passar?", traffic_light.can_vehicle_pass(True))
        time.sleep(1)