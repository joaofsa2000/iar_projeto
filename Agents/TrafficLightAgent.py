import asyncio
from datetime import datetime, timedelta
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.template import Template
from Models.LightStatus import LightStatus


class TrafficLightAgent(Agent):
    def __init__(self, jid, password, traffic_lights, environment, offset_seconds=0):
        """
        :param offset_seconds: atraso inicial do ciclo deste cruzamento (para desfasar em relação aos outros)
        """
        super().__init__(jid, password)
        self.environment = environment
        self.traffic_lights = []
        self.offset_seconds = offset_seconds  # atraso inicial
        self.normal_cycle = True
        self.current_state = LightStatus.RED

        # Criação dos 12 semáforos do cruzamento e associação ao ambiente
        directions = ['bottom', 'left', 'top', 'right']
        positions = ['left_tl', 'center_tl', 'right_tl']

        for dir in directions:
            for pos in positions:
                tl_obj = getattr(getattr(traffic_lights, f"{dir}_tl"), pos)
                self.traffic_lights.append(
                    self.environment.add_traffic_light(jid, f"{traffic_lights.id}_{dir[0]}_{pos[0]}",
                                                       tl_obj.coordinate, tl_obj.angle)
                )

    async def setup(self):
        print(f"[{self.jid}] Agente de semáforo iniciado com offset de {self.offset_seconds}s.")

        # ============================================================
        # COMPORTAMENTO PERIÓDICO — CICLO NORMAL (VERDE/VERMELHO)
        # ============================================================
        class PeriodicCycle(PeriodicBehaviour):
            async def run(self):
                if not self.agent.normal_cycle:
                    return  # pausa durante emergência

                # alterna o estado atual
                self.agent.current_state = LightStatus.GREEN if self.agent.current_state == LightStatus.RED else LightStatus.RED

                # aplica o novo estado a todos os semáforos do cruzamento
                for tl in self.agent.traffic_lights:
                    tl.change_status(self.agent.current_state)
                    self.agent.environment.update_traffic_light_status(tl.id, self.agent.current_state)

                print(f"[{self.agent.jid}] Ciclo normal: semáforos a {self.agent.current_state.name}")

        # arranque do ciclo com desfasamento (offset)
        start_at = datetime.now() + timedelta(seconds=self.offset_seconds)
        self.add_behaviour(PeriodicCycle(period=10, start_at=start_at))

        # ============================================================
        # COMPORTAMENTO DE EMERGÊNCIA
        # ============================================================
        class ReceiveEmergency(CyclicBehaviour):
            async def run(self):
                # aguarda mensagens de emergência
                msg = await self.receive(timeout=60)
                if msg and msg.metadata.get("action") == "change_status":
                    print(f"[{self.agent.jid}] Pedido de emergência recebido.")

                    # interrompe o ciclo normal
                    self.agent.normal_cycle = False

                    # coloca todos os semáforos a vermelho
                    for tl in self.agent.traffic_lights:
                        tl.change_status(LightStatus.RED)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                    # identifica e abre o semáforo solicitado
                    tl_id = msg.metadata.get("traffic_light")
                    if tl_id and tl_id in self.agent.environment.traffic_lights_objects:
                        tl = self.agent.environment.traffic_lights_objects[tl_id]
                        tl.change_status(LightStatus.GREEN)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                        print(f"[{self.agent.jid}] Semáforo {tl.id} aberto para emergência.")

                    # mantém o estado de emergência por 10 segundos
                    await asyncio.sleep(10)

                    # retoma ciclo normal
                    self.agent.normal_cycle = True
                    print(f"[{self.agent.jid}] Emergência concluída. Retoma ciclo normal.")

        # define o template de mensagens para o comportamento de emergência
        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(ReceiveEmergency(), template)
