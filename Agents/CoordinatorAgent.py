# CoordinatorAgent.py

from datetime import datetime, timedelta

from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.message import Message
from spade.template import Template


class CoordinatorAgent(Agent):
    def __init__(self, jid, password, environment, phase_duration=8):
        super().__init__(jid, password)
        self.environment = environment
        self.phase_duration = phase_duration  # segundos

    async def setup(self):
        # Ativa modo coordenado no ambiente e regista o JID do coordenador
        self.environment.coordinator_enabled = True
        try:
            self.environment.coordinator_jid = str(self.jid)
        except Exception:
            self.environment.coordinator_jid = None

        class CoordinationBehaviour(PeriodicBehaviour):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer
                self.current_phase = "vertical"  # começa vertical por defeito

            async def run(self):
                await self.broadcast_phase(self.current_phase)
                # Alterna fase para próximo ciclo
                self.current_phase = (
                    "horizontal" if self.current_phase == "vertical" else "vertical"
                )

            async def broadcast_phase(self, phase):
                # Obter JIDs únicos dos agentes de semáforos a partir do ambiente
                agent_jids = set(self.outer.environment.traffic_lights_agents_tl.values())
                for jid in agent_jids:
                    msg = Message(to=jid)
                    msg.set_metadata("performative", "request")
                    msg.set_metadata("action", "set_phase")
                    msg.set_metadata("phase", phase)
                    msg.body = f"Coordinator sets phase to {phase}"
                    await self.send(msg)

        # Inicia comportamento periódico de coordenação
        start_at = datetime.now() + timedelta(seconds=2)
        behav = CoordinationBehaviour(self)
        behav.period = self.phase_duration
        behav.start_at = start_at
        self.add_behaviour(behav)

        # Comportamento para receber pedidos de emergência e reencaminhar para o TL correto
        class ReceiveEmergencyBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=30)
                if not msg:
                    return
                action = msg.metadata.get("action") if msg.metadata else None
                if action != "emergency_request":
                    return

                tl_id = msg.metadata.get("traffic_light") if msg.metadata else None
                if not tl_id:
                    return

                # Determina o agente de semáforo responsável por este TL
                tl_agent_jid = self.agent.environment.traffic_lights_agents_tl.get(str(tl_id))
                if not tl_agent_jid:
                    return

                # Reencaminha um pedido de alteração de estado para o agente do semáforo
                fwd = Message(to=tl_agent_jid)
                fwd.set_metadata("performative", "request")
                fwd.set_metadata("action", "change_status")
                fwd.set_metadata("traffic_light", str(tl_id))
                fwd.body = "Coordinator forwarding emergency request"
                await self.send(fwd)

        tmpl = Template()
        tmpl.set_metadata("performative", "request")
        tmpl.set_metadata("action", "emergency_request")
        self.add_behaviour(ReceiveEmergencyBehaviour(), tmpl)

class MapUpdaterAgent(Agent):
    """
    Agente legado solicitado por import existente em main.py:
    from Agents.CoordenatorAgent import MapUpdaterAgent

    Mantém compatibilidade sem interferir com a lógica atual. Pode ser usado
    futuramente para telemetria/heartbeat do ambiente.
    """

    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment

    async def setup(self):
        class NoopBehav(PeriodicBehaviour):
            async def run(self):
                # Não faz nada; placeholder de compatibilidade
                return

        # Executa de forma periódica apenas para manter o agente vivo
        self.add_behaviour(NoopBehav(period=5))