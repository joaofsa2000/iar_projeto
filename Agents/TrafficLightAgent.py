import asyncio
from datetime import datetime, timedelta
import uuid
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.template import Template
from spade.message import Message
from Models.LightStatus import LightStatus


class TrafficLightAgent(Agent):
    def __init__(self, jid, password, traffic_lights, environment, offset_seconds=0):
        super().__init__(jid, password)
        self.environment = environment
        self.traffic_lights = []
        self.offset_seconds = offset_seconds
        self.normal_cycle = True
        self.current_state = LightStatus.RED

        # Controlo de subscrições (FIPA Subscribe Protocol)
        self.subscribers = {}  # {car_jid: subscription_id}

        # Criação dos 12 semáforos do cruzamento
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
        print(f"[TRAFFIC LIGHT {self.jid}] Agente iniciado com offset de {self.offset_seconds}s")

        # ============================================================
        # COMPORTAMENTO PERIÓDICO – CICLO NORMAL (VERDE/VERMELHO)
        # ============================================================
        class NormalCycleBehaviour(PeriodicBehaviour):
            async def run(self):
                if not self.agent.normal_cycle:
                    return

                # Alterna o estado
                self.agent.current_state = LightStatus.GREEN if self.agent.current_state == LightStatus.RED else LightStatus.RED

                # Aplica o novo estado a todos os semáforos
                for tl in self.agent.traffic_lights:
                    tl.change_status(self.agent.current_state)
                    self.agent.environment.update_traffic_light_status(tl.id, self.agent.current_state)

                print(f"[TRAFFIC LIGHT {self.agent.jid}] Ciclo normal: {self.agent.current_state.name}")

                # Notifica todos os subscritores sobre a mudança (FIPA Subscribe Protocol)
                await self.notify_subscribers()

            async def notify_subscribers(self):
                """Envia notificação INFORM para todos os subscritores"""
                for subscriber_jid, subscription_id in self.agent.subscribers.items():
                    msg = Message(to=subscriber_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("protocol", "fipa-subscribe")
                    msg.set_metadata("conversation-id", subscription_id)
                    msg.body = f"STATUS_UPDATE: Traffic lights now {self.agent.current_state.name}"

                    await self.send(msg)

        start_at = datetime.now() + timedelta(seconds=self.offset_seconds)
        self.add_behaviour(NormalCycleBehaviour(period=10, start_at=start_at))

        # ============================================================
        # FIPA REQUEST PROTOCOL - Pedidos de Emergência
        # ============================================================
        class EmergencyRequestBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-request":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")
                    tl_id = msg.get_metadata("traffic_light_id")

                    print(f"[TRAFFIC LIGHT {self.agent.jid}] REQUEST recebido de {msg.sender}")
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Conversation-ID: {conv_id}")

                    if performative == "request":
                        # Envia AGREE (concordo em processar o pedido)
                        await self.send_agree(msg.sender, conv_id)

                        # Processa o pedido de emergência
                        success = await self.process_emergency_request(tl_id)

                        if success:
                            # Envia INFORM (ação concluída com sucesso)
                            await self.send_inform(msg.sender, conv_id, f"Green light activated at {tl_id}")
                        else:
                            # Envia FAILURE (falha ao processar)
                            await self.send_failure(msg.sender, conv_id, "Unable to activate green light")

            async def send_agree(self, recipient, conv_id):
                """Envia mensagem AGREE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "agree")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = "Request accepted and will be processed"
                await self.send(msg)
                print(f"[TRAFFIC LIGHT {self.agent.jid}] AGREE enviado para {recipient}")

            async def send_inform(self, recipient, conv_id, result):
                """Envia mensagem INFORM com resultado"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "inform")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = result
                await self.send(msg)
                print(f"[TRAFFIC LIGHT {self.agent.jid}] INFORM enviado para {recipient}")

            async def send_failure(self, recipient, conv_id, reason):
                """Envia mensagem FAILURE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "failure")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = reason
                await self.send(msg)
                print(f"[TRAFFIC LIGHT {self.agent.jid}] FAILURE enviado para {recipient}")

            async def process_emergency_request(self, tl_id):
                """Processa pedido de emergência"""
                try:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Processando pedido de emergência")

                    # Interrompe ciclo normal
                    self.agent.normal_cycle = False

                    # Coloca todos os semáforos a vermelho
                    for tl in self.agent.traffic_lights:
                        tl.change_status(LightStatus.RED)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.RED)

                    # Abre o semáforo solicitado
                    if tl_id and tl_id in self.agent.environment.traffic_lights_objects:
                        tl = self.agent.environment.traffic_lights_objects[tl_id]
                        tl.change_status(LightStatus.GREEN)
                        self.agent.environment.update_traffic_light_status(tl.id, LightStatus.GREEN)
                        print(f"[TRAFFIC LIGHT {self.agent.jid}] Semáforo {tl.id} aberto para emergência")

                    # Mantém estado de emergência por 10 segundos
                    await asyncio.sleep(10)

                    # Retoma ciclo normal
                    self.agent.normal_cycle = True
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Emergência concluída. Retoma ciclo normal")

                    return True
                except Exception as e:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Erro ao processar emergência: {e}")
                    return False

        template_request = Template()
        template_request.set_metadata("protocol", "fipa-request")
        self.add_behaviour(EmergencyRequestBehaviour(), template_request)

        # ============================================================
        # FIPA SUBSCRIBE PROTOCOL - Gestão de Subscrições
        # ============================================================
        class SubscriptionBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-subscribe":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")

                    if performative == "subscribe":
                        # Carro quer subscrever atualizações
                        subscription_id = str(uuid.uuid4())
                        self.agent.subscribers[str(msg.sender)] = subscription_id

                        # Envia AGREE
                        agree_msg = Message(to=str(msg.sender))
                        agree_msg.set_metadata("performative", "agree")
                        agree_msg.set_metadata("protocol", "fipa-subscribe")
                        agree_msg.set_metadata("conversation-id", conv_id)
                        agree_msg.set_metadata("subscription-id", subscription_id)
                        agree_msg.body = f"Subscription accepted. Current status: {self.agent.current_state.name}"
                        await self.send(agree_msg)

                        print(f"[TRAFFIC LIGHT {self.agent.jid}] Subscrição aceite de {msg.sender}")

                    elif performative == "cancel":
                        # Carro quer cancelar subscrição
                        if str(msg.sender) in self.agent.subscribers:
                            del self.agent.subscribers[str(msg.sender)]

                            # Envia INFORM de cancelamento
                            inform_msg = Message(to=str(msg.sender))
                            inform_msg.set_metadata("performative", "inform")
                            inform_msg.set_metadata("protocol", "fipa-subscribe")
                            inform_msg.set_metadata("conversation-id", conv_id)
                            inform_msg.body = "Subscription cancelled"
                            await self.send(inform_msg)

                            print(f"[TRAFFIC LIGHT {self.agent.jid}] Subscrição cancelada de {msg.sender}")

        template_subscribe = Template()
        template_subscribe.set_metadata("protocol", "fipa-subscribe")
        self.add_behaviour(SubscriptionBehaviour(), template_subscribe)