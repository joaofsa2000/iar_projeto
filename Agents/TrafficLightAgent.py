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
        
        # Traffic light pairs: vertical (top-bottom) and horizontal (left-right)
        self.vertical_lights = []    # top and bottom lights (synchronized)
        self.horizontal_lights = []  # left and right lights (synchronized)
        
        # Current state for each pair
        self.vertical_state = LightStatus.RED
        self.horizontal_state = LightStatus.RED
        
        # Which pair is currently active (has green)
        self.active_pair = "vertical"  # or "horizontal"
        
        # Timing configuration (can be adjusted dynamically)
        self.green_duration = 8   # seconds for green phase
        self.yellow_duration = 2  # seconds for yellow phase
        self.cycle_period = self.green_duration + self.yellow_duration  # total per pair
        
        # Controlo de subscrições (FIPA Subscribe Protocol)
        self.subscribers = {}  # {car_jid: subscription_id}

        # Criação dos 12 semáforos do cruzamento, grouped by pairs
        directions = ['bottom', 'left', 'top', 'right']
        positions = ['left_tl', 'center_tl', 'right_tl']

        for dir in directions:
            for pos in positions:
                tl_obj = getattr(getattr(traffic_lights, f"{dir}_tl"), pos)
                tl = self.environment.add_traffic_light(
                    jid, f"{traffic_lights.id}_{dir[0]}_{pos[0]}",
                    tl_obj.coordinate, tl_obj.angle
                )
                self.traffic_lights.append(tl)
                
                # Group into pairs: vertical (top-bottom) or horizontal (left-right)
                if dir in ['top', 'bottom']:
                    self.vertical_lights.append(tl)
                else:  # left, right
                    self.horizontal_lights.append(tl)

    def _set_pair_status(self, pair: str, status: LightStatus):
        """Set the status for a pair of traffic lights."""
        if pair == "vertical":
            self.vertical_state = status
            for tl in self.vertical_lights:
                tl.change_status(status)
                self.environment.update_traffic_light_status(tl.id, status)
        else:  # horizontal
            self.horizontal_state = status
            for tl in self.horizontal_lights:
                tl.change_status(status)
                self.environment.update_traffic_light_status(tl.id, status)

    async def setup(self):
        print(f"[TRAFFIC LIGHT {self.jid}] Agente iniciado com offset de {self.offset_seconds}s")
        print(f"[TRAFFIC LIGHT {self.jid}] Semáforos verticais: {len(self.vertical_lights)}, horizontais: {len(self.horizontal_lights)}")

        # ============================================================
        # COMPORTAMENTO PERIÓDICO – CICLO NORMAL COM PARES E AMARELO
        # ============================================================
        class NormalCycleBehaviour(CyclicBehaviour):
            async def run(self):
                if not self.agent.normal_cycle:
                    await asyncio.sleep(1)
                    return

                # Cycle: Active pair GREEN -> YELLOW -> RED, then switch pairs
                active = self.agent.active_pair
                inactive = "horizontal" if active == "vertical" else "vertical"
                
                # Phase 1: Active pair goes GREEN, inactive stays RED
                self.agent._set_pair_status(active, LightStatus.GREEN)
                self.agent._set_pair_status(inactive, LightStatus.RED)
                
                print(f"[TRAFFIC LIGHT {self.agent.jid}] {active.upper()} pair: GREEN | {inactive.upper()} pair: RED")
                await self.notify_subscribers(f"{active.upper()}_GREEN")
                
                # Wait for green duration
                await asyncio.sleep(self.agent.green_duration)
                
                if not self.agent.normal_cycle:
                    return
                
                # Phase 2: Active pair goes YELLOW (transition warning)
                self.agent._set_pair_status(active, LightStatus.YELLOW)
                
                print(f"[TRAFFIC LIGHT {self.agent.jid}] {active.upper()} pair: YELLOW | {inactive.upper()} pair: RED")
                await self.notify_subscribers(f"{active.upper()}_YELLOW")
                
                # Wait for yellow duration
                await asyncio.sleep(self.agent.yellow_duration)
                
                if not self.agent.normal_cycle:
                    return
                
                # Phase 3: Active pair goes RED, switch to other pair
                self.agent._set_pair_status(active, LightStatus.RED)
                
                # Switch active pair for next cycle
                self.agent.active_pair = inactive
                
                print(f"[TRAFFIC LIGHT {self.agent.jid}] Switching active pair to {inactive.upper()}")

            async def notify_subscribers(self, status_info: str):
                """Envia notificação INFORM para todos os subscritores"""
                for subscriber_jid, subscription_id in self.agent.subscribers.items():
                    msg = Message(to=subscriber_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("protocol", "fipa-subscribe")
                    msg.set_metadata("conversation-id", subscription_id)
                    msg.body = f"STATUS_UPDATE: {status_info} | Vertical: {self.agent.vertical_state.name} | Horizontal: {self.agent.horizontal_state.name}"

                    await self.send(msg)

        # Start cycle with offset
        await asyncio.sleep(self.offset_seconds)
        self.add_behaviour(NormalCycleBehaviour())

        # ============================================================
        # FIPA REQUEST PROTOCOL - Pedidos de Emergência e Ajuste de Tempos
        # ============================================================
        class EmergencyRequestBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg and msg.get_metadata("protocol") == "fipa-request":
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")
                    tl_id = msg.get_metadata("traffic_light_id")
                    action = msg.get_metadata("action")

                    print(f"[TRAFFIC LIGHT {self.agent.jid}] REQUEST recebido de {msg.sender}")
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Conversation-ID: {conv_id}")

                    if performative == "request":
                        # Check if this is a timing adjustment request
                        if action == "adjust_timing":
                            await self.send_agree(msg.sender, conv_id)
                            success = await self.process_timing_adjustment(msg.body)
                            if success:
                                await self.send_inform(msg.sender, conv_id, "Timing adjusted successfully")
                            else:
                                await self.send_failure(msg.sender, conv_id, "Failed to adjust timing")
                        # Check if this is a car requesting green light
                        elif action == "request_green":
                            await self.send_agree(msg.sender, conv_id)
                            success = await self.process_car_green_request(msg.sender, tl_id)
                            if success:
                                await self.send_inform(msg.sender, conv_id, "Request noted - prioritizing traffic flow")
                            else:
                                await self.send_refuse(msg.sender, conv_id, "Cannot prioritize at this time")
                        else:
                            # Emergency vehicle request
                            await self.send_agree(msg.sender, conv_id)
                            success = await self.process_emergency_request(tl_id)
                            if success:
                                await self.send_inform(msg.sender, conv_id, f"Green light activated at {tl_id}")
                            else:
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

            async def send_refuse(self, recipient, conv_id, reason):
                """Envia mensagem REFUSE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "refuse")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = reason
                await self.send(msg)
                print(f"[TRAFFIC LIGHT {self.agent.jid}] REFUSE enviado para {recipient}")

            async def process_emergency_request(self, tl_id):
                """Processa pedido de emergência"""
                try:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Processando pedido de emergência")

                    # Interrompe ciclo normal
                    self.agent.normal_cycle = False

                    # Coloca todos os semáforos a vermelho
                    self.agent._set_pair_status("vertical", LightStatus.RED)
                    self.agent._set_pair_status("horizontal", LightStatus.RED)

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

            async def process_timing_adjustment(self, body):
                """Process timing adjustment request from MapUpdater."""
                try:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Ajustando tempos: {body}")
                    
                    # Parse the congestion info and adjust timing
                    # Increase green duration for congested directions
                    if "CONGESTION_ALERT" in body:
                        # Increase green duration temporarily
                        original_green = self.agent.green_duration
                        self.agent.green_duration = min(15, self.agent.green_duration + 3)
                        print(f"[TRAFFIC LIGHT {self.agent.jid}] Green duration: {original_green}s -> {self.agent.green_duration}s")
                        
                        # Reset after 60 seconds
                        await asyncio.sleep(60)
                        self.agent.green_duration = original_green
                        print(f"[TRAFFIC LIGHT {self.agent.jid}] Green duration reset to {original_green}s")
                    
                    return True
                except Exception as e:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Erro ao ajustar tempos: {e}")
                    return False

            async def process_car_green_request(self, sender, tl_id):
                """Process request from car that has been waiting too long."""
                try:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Car {sender} requesting priority at {tl_id}")
                    # Note: We don't immediately switch, but this info can be used for adaptive timing
                    # The system will naturally cycle, but this could influence future timing decisions
                    return True
                except Exception as e:
                    print(f"[TRAFFIC LIGHT {self.agent.jid}] Erro ao processar pedido de carro: {e}")
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
                        agree_msg.body = f"Subscription accepted. Vertical: {self.agent.vertical_state.name}, Horizontal: {self.agent.horizontal_state.name}"
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

        # ============================================================
        # FIPA INFORM PROTOCOL - Receber alertas de broadcast
        # ============================================================
        class ReceiveBroadcastBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                
                if msg and msg.get_metadata("protocol") == "fipa-inform":
                    performative = msg.get_metadata("performative")
                    
                    if performative == "inform":
                        print(f"[TRAFFIC LIGHT {self.agent.jid}] Broadcast recebido: {msg.body}")
                        # React to system alerts if needed

        template_inform = Template()
        template_inform.set_metadata("protocol", "fipa-inform")
        self.add_behaviour(ReceiveBroadcastBehaviour(), template_inform)
