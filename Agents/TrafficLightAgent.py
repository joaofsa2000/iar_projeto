import asyncio
from datetime import datetime, timedelta
import uuid
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.template import Template
from spade.message import Message
from Models.LightStatus import LightStatus


class TrafficLightAgent(Agent):
    def __init__(self, jid, password, traffic_lights, environment, offset_seconds=0, debug_mode=False):
        super().__init__(jid, password)
        self.environment = environment
        self.traffic_lights = []
        self.offset_seconds = offset_seconds
        self.normal_cycle = True
        self.debug_mode = debug_mode  # Debug mode: keep lights always red
        
        # Traffic light pairs: vertical (top-bottom) and horizontal (left-right)
        self.vertical_lights = []    # top and bottom lights (synchronized)
        self.horizontal_lights = []  # left and right lights (synchronized)
        
        # Current state for each pair
        self.vertical_state = LightStatus.RED
        self.horizontal_state = LightStatus.RED
        
        # Which pair is currently active (has green)
        self.active_pair = "vertical"  # or "horizontal"
        
        # Timing configuration (can be adjusted dynamically)
        # These are in SIMULATION TIME, not real time
        self.green_duration = 8   # seconds for green phase (simulation time)
        self.yellow_duration = 2  # seconds for yellow phase (simulation time)
        self.cycle_period = self.green_duration + self.yellow_duration  # total per pair
        
        # Track phase start times in simulation time
        self.current_phase_start_time = None

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
        print(f"[SEMÁFORO {self.jid}] Agente iniciado")
        # print(f"[SEMÁFORO {self.jid}] Semáforos verticais: {len(self.vertical_lights)}, horizontais: {len(self.horizontal_lights)}")

        # ============================================================
        # FIPA REQUEST PROTOCOL - Pedidos de Emergência e Ajuste de Tempos
        # Register this FIRST so it's ready to receive messages immediately
        # ============================================================
        class EmergencyRequestBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg:
                    protocol = msg.get_metadata("protocol")
                    performative = msg.get_metadata("performative")
                    conv_id = msg.get_metadata("conversation-id")
                    tl_id = msg.get_metadata("traffic_light_id")
                    action = msg.get_metadata("action")

                    print(f"[SEMÁFORO {self.agent.jid}] REQUEST recebido de {msg.sender}")

                    if performative == "request":
                        # Check if this is a timing adjustment request
                        if action == "adjust_timing":
                            await self.send_agree(msg.sender, conv_id)
                            success = await self.process_timing_adjustment(msg.body)
                            if success:
                                await self.send_inform(msg.sender, conv_id, "Tempos ajustados com sucesso")
                            else:
                                await self.send_failure(msg.sender, conv_id, "Falha ao ajustar tempos")
                        # Check if this is a car requesting green light
                        elif action == "request_green":
                            await self.send_agree(msg.sender, conv_id)
                            success = await self.process_car_green_request(msg.sender, tl_id)
                            if success:
                                await self.send_inform(msg.sender, conv_id, "Pedido registado - priorizando fluxo")
                            else:
                                await self.send_refuse(msg.sender, conv_id, "Não é possível priorizar neste momento")
                        else:
                            # Emergency vehicle request
                            await self.send_agree(msg.sender, conv_id)
                        success = await self.process_emergency_request(tl_id)
                        if success:
                                await self.send_inform(msg.sender, conv_id, f"Luz verde ativada em {tl_id}")
                        else:
                                await self.send_failure(msg.sender, conv_id, "Não foi possível ativar luz verde")

            async def send_agree(self, recipient, conv_id):
                """Envia mensagem AGREE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "agree")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = "Pedido aceite e será processado"
                await self.send(msg)
                # print(f"[SEMÁFORO {self.agent.jid}] AGREE enviado para {recipient}")

            async def send_inform(self, recipient, conv_id, result):
                """Envia mensagem INFORM com resultado"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "inform")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = result
                await self.send(msg)
                # print(f"[SEMÁFORO {self.agent.jid}] INFORM enviado para {recipient}")

            async def send_failure(self, recipient, conv_id, reason):
                """Envia mensagem FAILURE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "failure")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = reason
                await self.send(msg)
                # print(f"[SEMÁFORO {self.agent.jid}] FAILURE enviado para {recipient}")

            async def send_refuse(self, recipient, conv_id, reason):
                """Envia mensagem REFUSE"""
                msg = Message(to=str(recipient))
                msg.set_metadata("performative", "refuse")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", conv_id)
                msg.body = reason
                await self.send(msg)
                # print(f"[SEMÁFORO {self.agent.jid}] REFUSE enviado para {recipient}")

            async def process_emergency_request(self, tl_id):
                """Processa pedido de emergência"""
                try:
                    # print(f"[SEMÁFORO {self.agent.jid}] Processando pedido de emergência para {tl_id}")

                    # DEBUG MODE: Don't allow emergency vehicles to change lights
                    if self.agent.debug_mode:
                        # print(f"[SEMÁFORO {self.agent.jid}] DEBUG MODE: Emergency request ignored, keeping lights RED")
                        pass
                        return False  # Return False so calling code sends FAILURE message

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
                        # print(f"[SEMÁFORO {self.agent.jid}] Semáforo {tl.id} aberto para emergência")

                    # Mantém estado de emergência por 10 segundos (simulation time)
                    start_sim_time = self.agent.environment.simulation_time
                    target_sim_time = start_sim_time + timedelta(seconds=10)
                    base_sleep = 0.1
                    sim_speed = max(1, self.agent.environment.time_speed)
                    adjusted_sleep = base_sleep / sim_speed
                    adjusted_sleep = max(0.005, adjusted_sleep)
                    while self.agent.environment.simulation_time < target_sim_time:
                        await asyncio.sleep(adjusted_sleep)

                    # Retoma ciclo normal
                    self.agent.normal_cycle = True
                    # print(f"[SEMÁFORO {self.agent.jid}] Emergência concluída. Retoma ciclo normal")

                    return True
                except Exception as e:
                    print(f"[SEMÁFORO {self.agent.jid}] Erro ao processar emergência: {e}")
                    self.agent.normal_cycle = True
                    return False

            async def process_timing_adjustment(self, body):
                """Process timing adjustment request from MapUpdater."""
                try:
                    import json
                    
                    # Try to parse as JSON (new format)
                    try:
                        adjustment_data = json.loads(body)
                        vertical_adj = adjustment_data.get('vertical_adjustment', 0)
                        horizontal_adj = adjustment_data.get('horizontal_adjustment', 0)
                        duration = adjustment_data.get('duration', 45)
                        intersection = adjustment_data.get('intersection', 'unknown')
                        
                        # print(f"[SEMÁFORO {self.agent.jid}] Ajuste recebido para {intersection}: "
                        #       f"Vertical={vertical_adj:+d}s, Horizontal={horizontal_adj:+d}s")
                        
                        # Store original values
                        original_vertical_green = self.agent.green_duration
                        original_horizontal_green = self.agent.green_duration
                        
                        # Apply adjustments (clamp to reasonable values)
                        # Vertical pair (top-bottom)
                        new_vertical_green = max(5, min(15, original_vertical_green + vertical_adj))
                        # Horizontal pair (left-right)
                        new_horizontal_green = max(5, min(15, original_horizontal_green + horizontal_adj))
                        
                        # For now, apply to both pairs (can be enhanced to track separately)
                        # Use the average or the larger adjustment
                        avg_adjustment = (vertical_adj + horizontal_adj) / 2
                        if abs(vertical_adj) > abs(horizontal_adj):
                            self.agent.green_duration = new_vertical_green
                        else:
                            self.agent.green_duration = new_horizontal_green
                        
                        # print(f"[SEMÁFORO {self.agent.jid}] Duração verde ajustada: "
                        #       f"{original_vertical_green}s -> {self.agent.green_duration}s")
                        
                        # Reset after duration seconds (simulation time)
                        start_sim_time = self.agent.environment.simulation_time
                        target_sim_time = start_sim_time + timedelta(seconds=duration)
                        
                        # Wait for duration in background (non-blocking)
                        async def reset_timing():
                            base_sleep = 0.1
                            sim_speed = max(1, self.agent.environment.time_speed)
                            adjusted_sleep = base_sleep / sim_speed
                            adjusted_sleep = max(0.005, adjusted_sleep)
                            while self.agent.environment.simulation_time < target_sim_time:
                                await asyncio.sleep(adjusted_sleep)
                            self.agent.green_duration = original_vertical_green
                            print(f"[SEMÁFORO {self.agent.jid}] Duração verde resetada para {original_vertical_green}s")
                        
                        # Start reset task in background
                        asyncio.create_task(reset_timing())
                        
                    except (json.JSONDecodeError, KeyError):
                        # Fallback to old format
                        if "CONGESTION_ALERT" in body:
                            original_green = self.agent.green_duration
                            self.agent.green_duration = min(15, self.agent.green_duration + 3)
                            print(f"[SEMÁFORO {self.agent.jid}] Duração verde: {original_green}s -> {self.agent.green_duration}s")
                            
                            # Reset after 60 seconds (simulation time)
                            start_sim_time = self.agent.environment.simulation_time
                            target_sim_time = start_sim_time + timedelta(seconds=60)
                            base_sleep = 0.1
                            sim_speed = max(1, self.agent.environment.time_speed)
                            adjusted_sleep = base_sleep / sim_speed
                            adjusted_sleep = max(0.005, adjusted_sleep)
                            while self.agent.environment.simulation_time < target_sim_time:
                                await asyncio.sleep(adjusted_sleep)
                            self.agent.green_duration = original_green
                            print(f"[SEMÁFORO {self.agent.jid}] Duração verde resetada para {original_green}s")

                    return True
                except Exception as e:
                    print(f"[SEMÁFORO {self.agent.jid}] Erro ao ajustar tempos: {e}")
                    return False

            async def process_car_green_request(self, sender, tl_id):
                """Process request from car that has been waiting too long."""
                try:
                    # print(f"[SEMÁFORO {self.agent.jid}] Carro {sender} solicitando prioridade em {tl_id}")

                    # Check if there's an accident at this intersection
                    intersection_id = self._get_intersection_from_traffic_light(tl_id)
                    if intersection_id and self.environment.is_intersection_blocked(intersection_id):
                        # print(f"[SEMÁFORO {self.agent.jid}] Recusando pedido - acidente em {intersection_id}")
                        pass
                        return False

                    # Note: We don't immediately switch, but this info can be used for adaptive timing
                    # The system will naturally cycle, but this could influence future timing decisions
                    return True
                except Exception as e:
                    print(f"[SEMÁFORO {self.agent.jid}] Erro ao processar pedido de carro: {e}")
                    return False

            def _get_intersection_from_traffic_light(self, tl_id):
                """Extract intersection ID from traffic light ID."""
                # Traffic light IDs are like: "top_left_n_left_tl", "bottom_mid_s_center_tl", etc.
                # Extract the intersection part (e.g., "top_left", "bottom_mid")
                tl_id_str = str(tl_id)

                # Common patterns for intersection IDs in traffic light names
                intersection_patterns = [
                    "top_left", "top_mid", "top_right",
                    "bottom_left", "bottom_mid", "bottom_right"
                ]

                for intersection in intersection_patterns:
                    if intersection in tl_id_str:
                        return intersection

                return None

        template_request = Template()
        template_request.set_metadata("protocol", "fipa-request")
        self.add_behaviour(EmergencyRequestBehaviour(), template_request)

        # ============================================================
        # FIPA SUBSCRIBE PROTOCOL - Gestão de Subscrições
        # ============================================================
        class SubscriptionBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)

                if msg:
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
                        agree_msg.body = f"Subscrição aceite. Vertical: {self.agent.vertical_state.name}, Horizontal: {self.agent.horizontal_state.name}"
                        await self.send(agree_msg)

                        # print(f"[SEMÁFORO {self.agent.jid}] Subscrição aceite de {msg.sender}")

                    elif performative == "cancel":
                        # Carro quer cancelar subscrição
                        if str(msg.sender) in self.agent.subscribers:
                            del self.agent.subscribers[str(msg.sender)]

                            # Envia INFORM de cancelamento
                            inform_msg = Message(to=str(msg.sender))
                            inform_msg.set_metadata("performative", "inform")
                            inform_msg.set_metadata("protocol", "fipa-subscribe")
                            inform_msg.set_metadata("conversation-id", conv_id)
                            inform_msg.body = "Subscrição cancelada"
                            await self.send(inform_msg)

                            # print(f"[SEMÁFORO {self.agent.jid}] Subscrição cancelada de {msg.sender}")

        template_subscribe = Template()
        template_subscribe.set_metadata("protocol", "fipa-subscribe")
        self.add_behaviour(SubscriptionBehaviour(), template_subscribe)

        # ============================================================
        # FIPA INFORM PROTOCOL - Receber alertas de broadcast
        # ============================================================
        class ReceiveBroadcastBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                
                if msg:
                    performative = msg.get_metadata("performative")
                    
                     #if performative == "inform":
                        # print(f"[SEMÁFORO {self.agent.jid}] Broadcast recebido: {msg.body}")
                        # React to system alerts if needed

        template_inform = Template()
        template_inform.set_metadata("protocol", "fipa-inform")
        self.add_behaviour(ReceiveBroadcastBehaviour(), template_inform)

        # ============================================================
        # FIPA INFORM PROTOCOL - Processar informações de redução de tempo vermelho
        # ============================================================
        class ProcessRedTimeReductionBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                
                if msg:
                    protocol = msg.get_metadata("protocol")
                    performative = msg.get_metadata("performative")
                    action = msg.get_metadata("action")
                    
                    if protocol == "fipa-inform" and performative == "inform" and action == "reduce_red_time":
                        await self.process_red_time_reduction(msg.body)
            
            async def process_red_time_reduction(self, body):
                """
                Processa informação para reduzir tempo vermelho de uma direção.
                Aplica a todas as 3 faixas da direção especificada.
                """
                try:
                    import json
                    adjustment_data = json.loads(body)
                    
                    direction = adjustment_data.get('direction')  # 'vertical' ou 'horizontal'
                    red_reduction = adjustment_data.get('red_reduction_seconds', 0)
                    duration = adjustment_data.get('duration', 45)
                    intersection = adjustment_data.get('intersection', 'unknown')
                    apply_to_all_lanes = adjustment_data.get('apply_to_all_lanes', True)
                    
                    # print(f"[SEMÁFORO {self.agent.jid}] Reduzir tempo vermelho {direction} em {red_reduction}s "
                    #       f"para {intersection} (todas as 3 faixas: {apply_to_all_lanes})")
                    
                    # O tempo vermelho de uma direção = tempo verde + amarelo da direção oposta
                    # Para reduzir tempo vermelho, reduzimos o tempo verde da direção oposta
                    original_green = self.agent.green_duration
                    
                    # Reduz tempo verde (que reduz o tempo vermelho do par oposto)
                    new_green = max(5, original_green - red_reduction)
                    self.agent.green_duration = new_green
                    # print(f"[SEMÁFORO {self.agent.jid}] Tempo verde reduzido: {original_green}s -> {new_green}s "
                    #       f"(reduz tempo vermelho {direction} em {red_reduction}s)")
                    
                    # Reset after duration seconds (simulation time)
                    start_sim_time = self.agent.environment.simulation_time
                    target_sim_time = start_sim_time + timedelta(seconds=duration)
                    
                    # Wait for duration in background (non-blocking)
                    async def reset_timing():
                        base_sleep = 0.1
                        sim_speed = max(1, self.agent.environment.time_speed)
                        adjusted_sleep = base_sleep / sim_speed
                        adjusted_sleep = max(0.005, adjusted_sleep)
                        while self.agent.environment.simulation_time < target_sim_time:
                            await asyncio.sleep(adjusted_sleep)
                        self.agent.green_duration = original_green
                        print(f"[SEMÁFORO {self.agent.jid}] Tempo verde resetado para {original_green}s")
                    
                    # Start reset task in background
                    asyncio.create_task(reset_timing())
                    
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    print(f"[SEMÁFORO {self.agent.jid}] Erro ao processar redução de tempo vermelho: {e}")
        
        template_red_reduction = Template()
        template_red_reduction.set_metadata("protocol", "fipa-inform")
        template_red_reduction.set_metadata("action", "reduce_red_time")
        self.add_behaviour(ProcessRedTimeReductionBehaviour(), template_red_reduction)

        # ============================================================
        # COMPORTAMENTO PERIÓDICO – CICLO NORMAL COM PARES E AMARELO
        # Start this LAST and with the offset delay
        # Uses simulation time instead of real time
        # ============================================================
        class NormalCycleBehaviour(CyclicBehaviour):
            def __init__(self, offset_seconds):
                super().__init__()
                self.offset_seconds = offset_seconds
                self.started = False
                self.current_phase = None  # "green", "yellow", or None
                self.phase_start_sim_time = None

            async def run(self):
                # Apply offset only once at the start (in real time for initial delay)
                if not self.started:
                    if self.offset_seconds > 0:
                        await asyncio.sleep(self.offset_seconds)
                    self.started = True
                    self.current_phase = None
                    
                    # DEBUG MODE: Set all lights to red and keep them red
                    if self.agent.debug_mode:
                        self.agent._set_pair_status("vertical", LightStatus.RED)
                        self.agent._set_pair_status("horizontal", LightStatus.RED)
                        # print(f"[SEMÁFORO {self.agent.jid}] DEBUG MODE: All lights set to RED and will remain RED")
                        base_sleep = 0.1
                        sim_speed = max(1, self.agent.environment.time_speed)
                        await asyncio.sleep(base_sleep / sim_speed)
                        return

                # DEBUG MODE: Keep all lights red, skip normal cycle
                if self.agent.debug_mode:
                    # Ensure all lights stay red
                    self.agent._set_pair_status("vertical", LightStatus.RED)
                    self.agent._set_pair_status("horizontal", LightStatus.RED)
                    base_sleep = 0.1
                    sim_speed = max(1, self.agent.environment.time_speed)
                    await asyncio.sleep(base_sleep / sim_speed)
                    return

                if not self.agent.normal_cycle:
                    # Adjust sleep based on simulation speed
                    base_sleep = 0.1
                    sim_speed = max(1, self.agent.environment.time_speed)
                    adjusted_sleep = base_sleep / sim_speed
                    adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                    await asyncio.sleep(adjusted_sleep)
                    return

                # Get current active/inactive pairs
                active = self.agent.active_pair
                inactive = "horizontal" if active == "vertical" else "vertical"
                
                # State machine: green -> yellow -> red -> (switch) -> green (new pair)
                
                # Phase 1: GREEN phase
                if self.current_phase is None or self.current_phase == "red_complete":
                    # Start new cycle with active pair going green
                    self.agent._set_pair_status(active, LightStatus.GREEN)
                    self.agent._set_pair_status(inactive, LightStatus.RED)
                    
                    # print(f"[SEMÁFORO {self.agent.jid}] Par {active.upper()}: VERDE | Par {inactive.upper()}: VERMELHO")
                    await self.notify_subscribers(f"{active.upper()}_GREEN")
                    
                    self.current_phase = "green"
                    self.phase_start_sim_time = self.agent.environment.simulation_time
                
                # Wait for green duration (in simulation time)
                if self.current_phase == "green":
                    elapsed = (self.agent.environment.simulation_time - self.phase_start_sim_time).total_seconds()
                    if elapsed < self.agent.green_duration:
                        # Adjust sleep based on simulation speed
                        base_sleep = 0.1
                        sim_speed = max(1, self.agent.environment.time_speed)
                        adjusted_sleep = base_sleep / sim_speed
                        adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                        await asyncio.sleep(adjusted_sleep)
                        return
                    
                    if not self.agent.normal_cycle:
                        return
                    
                    # Transition to yellow - set yellow immediately
                    self.agent._set_pair_status(active, LightStatus.YELLOW)
                    self.current_phase = "yellow"
                    self.phase_start_sim_time = self.agent.environment.simulation_time
                    
                    # print(f"[SEMÁFORO {self.agent.jid}] Par {active.upper()}: AMARELO | Par {inactive.upper()}: VERMELHO")
                    await self.notify_subscribers(f"{active.upper()}_YELLOW")
                
                # Phase 2: YELLOW phase - wait for yellow duration
                if self.current_phase == "yellow":
                    # Wait for yellow duration (in simulation time)
                    elapsed = (self.agent.environment.simulation_time - self.phase_start_sim_time).total_seconds()
                    if elapsed < self.agent.yellow_duration:
                        # Adjust sleep based on simulation speed
                        base_sleep = 0.1
                        sim_speed = max(1, self.agent.environment.time_speed)
                        adjusted_sleep = base_sleep / sim_speed
                        adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                        await asyncio.sleep(adjusted_sleep)
                        return
                    
                    if not self.agent.normal_cycle:
                        return
                    
                    # Transition to red - set red immediately
                    self.agent._set_pair_status(active, LightStatus.RED)
                    self.current_phase = "red"
                    self.phase_start_sim_time = self.agent.environment.simulation_time
                    
                    # print(f"[SEMÁFORO {self.agent.jid}] Par {active.upper()}: VERMELHO | Par {inactive.upper()}: VERMELHO")
                
                # Phase 3: RED phase - wait briefly then switch pairs
                if self.current_phase == "red":
                    # Brief red phase to ensure both pairs are red (0.5 seconds simulation time)
                    elapsed = (self.agent.environment.simulation_time - self.phase_start_sim_time).total_seconds()
                    if elapsed < 0.5:
                        # Adjust sleep based on simulation speed
                        base_sleep = 0.1
                        sim_speed = max(1, self.agent.environment.time_speed)
                        adjusted_sleep = base_sleep / sim_speed
                        adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                        await asyncio.sleep(adjusted_sleep)
                        return
                    
                    if not self.agent.normal_cycle:
                        return
                    
                    # Switch active pair for next cycle
                    self.agent.active_pair = inactive
                    self.current_phase = "red_complete"  # Mark that we've completed red phase
                    
                    # print(f"[SEMÁFORO {self.agent.jid}] Alternando para par {inactive.upper()}")
                    # Adjust sleep based on simulation speed
                    base_sleep = 0.1
                    sim_speed = max(1, self.agent.environment.time_speed)
                    adjusted_sleep = base_sleep / sim_speed
                    adjusted_sleep = max(0.005, adjusted_sleep)  # Minimum sleep
                    await asyncio.sleep(adjusted_sleep)
                    return

            async def notify_subscribers(self, status_info: str):
                """Envia notificação INFORM para todos os subscritores"""
                for subscriber_jid, subscription_id in self.agent.subscribers.items():
                    msg = Message(to=subscriber_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("protocol", "fipa-subscribe")
                    msg.set_metadata("conversation-id", subscription_id)
                    msg.body = f"STATUS_UPDATE: {status_info} | Vertical: {self.agent.vertical_state.name} | Horizontal: {self.agent.horizontal_state.name}"

                    await self.send(msg)

        # Add the cycle behavior (offset is handled internally now)
        self.add_behaviour(NormalCycleBehaviour(self.offset_seconds))
