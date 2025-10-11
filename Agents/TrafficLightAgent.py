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
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_l",
                                                                      traffic_lights.bottom_tl.left_tl.coordinate,
                                                                      traffic_lights.bottom_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_c",
                                                                      traffic_lights.bottom_tl.center_tl.coordinate,
                                                                      traffic_lights.bottom_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_b_r",
                                                                      traffic_lights.bottom_tl.right_tl.coordinate,
                                                                      traffic_lights.bottom_tl.right_tl.angle))

        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_l",
                                                                      traffic_lights.left_tl.left_tl.coordinate,
                                                                      traffic_lights.left_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_c",
                                                                      traffic_lights.left_tl.center_tl.coordinate,
                                                                      traffic_lights.left_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_l_r",
                                                                      traffic_lights.left_tl.right_tl.coordinate,
                                                                      traffic_lights.left_tl.right_tl.angle))

        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_l",
                                                                      traffic_lights.top_tl.left_tl.coordinate,
                                                                      traffic_lights.top_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_c",
                                                                      traffic_lights.top_tl.center_tl.coordinate,
                                                                      traffic_lights.top_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_t_r",
                                                                      traffic_lights.top_tl.right_tl.coordinate,
                                                                      traffic_lights.top_tl.right_tl.angle))

        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_l",
                                                                      traffic_lights.right_tl.left_tl.coordinate,
                                                                      traffic_lights.right_tl.left_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_c",
                                                                      traffic_lights.right_tl.center_tl.coordinate,
                                                                      traffic_lights.right_tl.center_tl.angle))
        self.traffic_lights.append(self.environment.add_traffic_light(jid, traffic_lights.id + "_r_r",
                                                                      traffic_lights.right_tl.right_tl.coordinate,
                                                                      traffic_lights.right_tl.right_tl.angle))

    async def setup(self):
        print(f"[{self.jid}] Agente de semáforo iniciado com offset de {self.offset_seconds}s.")

        # ============================================================
        #   COMPORTAMENTO PERIÓDICO — CICLO NORMAL (VERDE/VERMELHO)
        # ============================================================
        class PeriodicCycle(PeriodicBehaviour):
            async def run(self):
                if not self.agent.normal_cycle:
                    return  # pausa durante emergência

                # alterna o estado atual
                self.agent.current_state = (
                    LightStatus.GREEN if self.agent.current_state == LightStatus.RED else LightStatus.RED
                )

                # aplica o novo estado a todos os semáforos deste cruzamento
                for tl in self.agent.traffic_lights:
                    tl.change_status(self.agent.current_state)
                    self.agent.environment.update_traffic_light_status(tl.id, self.agent.current_state)

                print(f"[{self.agent.jid}] Ciclo normal: semáforos a {self.agent.current_state.name}")

        # arranque do ciclo com desfasamento (offset)
        start_at = datetime.now() + timedelta(seconds=self.offset_seconds)
        self.add_behaviour(PeriodicCycle(period=10, start_at=start_at))

        # ============================================================
        #   COMPORTAMENTO DE EMERGÊNCIA
        # ============================================================
        class ReceiveEmergency(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=60)
                if msg and msg.metadata.get("action") == "change_status":
                    print(f"[{self.agent.jid}] Pedido de emergência recebido.")

                    # interrompe o ciclo normal
                    self.agent.normal_cycle = False

                    # coloca todos os semáforos deste cruzamento a vermelho
                    for tl in self.agent.traffic_lights:
                        tl.change_status(LightStatus.RED)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                    # identifica e abre o semáforo pedido
                    tl_id = msg.metadata.get("traffic_light")
                    if tl_id and tl_id in self.agent.environment.traffic_lights_objects:
                        tl = self.agent.environment.traffic_lights_objects[tl_id]
                        tl.change_status(LightStatus.GREEN)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                        print(f"[{self.agent.jid}] Semáforo {tl.id} aberto para emergência.")

                    # mantém o estado de emergência por 10 segundos
                    await asyncio.sleep(10)

                    # retoma o ciclo normal
                    self.agent.normal_cycle = True
                    print(f"[{self.agent.jid}] Emergência concluída. Retoma ciclo normal.")

        # define o template de mensagens para o comportamento de emergência
        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(ReceiveEmergency(), template)
