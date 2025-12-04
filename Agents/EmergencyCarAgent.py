# EmergencyCarAgent.py
"""
Emergency vehicle agent that follows the same movement logic as CarAgent
but doesn't stop at red lights - sends FIPA requests instead.
"""

from datetime import datetime
import uuid

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from Models.LightStatus import LightStatus


class EmergencyCarAgent(Agent):
    def __init__(self, jid, password, environment):
        super().__init__(jid, password)
        self.environment = environment
        self.id = jid
        self.password = password
        self.guid = uuid.uuid4()
        self.car_obj = self.environment.add_emergency_car(self.id)

    async def setup(self):
        print(f"[VEÍCULO EMERGÊNCIA {self.jid}] Agente iniciado")

        class MovementBehaviour(CyclicBehaviour):
            def __init__(self, agent):
                super().__init__()
                self.agent = agent
                self.car = self.agent.car_obj
                self.env = self.agent.environment
                self.id = self.agent.id
                self.last_request_tl = None

            async def run(self):
                car_sprite = self.car.sprites()[0]
                
                # Check if vehicle has left the map
                if car_sprite.is_car_done():
                    # Cleanup from environment
                    if self.id in self.env.car_positions:
                        del self.env.car_positions[self.id]
                    if self.car in self.env.emergency_cars:
                        self.env.emergency_cars.remove(self.car)
                    print(f"[VEÍCULO EMERGÊNCIA {self.agent.jid}] Percurso concluído - agente parado")
                    await self.agent.stop()
                    return

                await self.move()
                
                # Update position in environment (like CarAgent does)
                self.env.update_car_position(self.id, car_sprite.get_car_position())
                
                car_sprite.update()

            async def move(self):
                """Movement logic - same as CarAgent but without stopping at red lights."""
                car_sprite = self.car.sprites()[0]
                is_tl_collided, tl_id = self.env.collision_traffic_light(car_sprite)

                if is_tl_collided:
                    tl_status = self.env.get_traffic_light_status(tl_id)
                    
                    # Request green light if red (but DON'T stop - emergency priority)
                    if tl_status == LightStatus.RED and self.last_request_tl != tl_id:
                        await self.send_request(tl_id)
                        self.last_request_tl = tl_id
                    
                    # Check for intersection collision - same logic as CarAgent
                    if self.env.collision_sprite(car_sprite):
                        car_sprite.fires_car(speed=2)
                        car_sprite.activate_turning()
                        car_sprite.flag_car_is_turning(True)
                    else:
                        car_sprite.flag_car_is_turning(False)
                        car_sprite.fires_car(speed=2)
                else:
                    self.last_request_tl = None
                    
                    # Check for intersection collision - same logic as CarAgent
                    if self.env.collision_sprite(car_sprite):
                        car_sprite.fires_car(speed=2)
                        car_sprite.activate_turning()
                        car_sprite.flag_car_is_turning(True)
                    else:
                        car_sprite.flag_car_is_turning(False)
                        car_sprite.fires_car(speed=2)

            async def send_request(self, tl_id):
                """Send FIPA Request for green light."""
                tl_jid = self.env.get_traffic_light_jid_by_id(tl_id)
                if not tl_jid:
                    return
                    
                request_id = str(uuid.uuid4())

                msg = Message(to=tl_jid)
                msg.set_metadata("performative", "request")
                msg.set_metadata("protocol", "fipa-request")
                msg.set_metadata("conversation-id", request_id)
                msg.set_metadata("traffic_light_id", str(tl_id))
                msg.body = f"EMERGENCY_REQUEST: Veículo {self.agent.guid} solicita luz verde em {tl_id}"

                await self.send(msg)
                print(f"[VEÍCULO EMERGÊNCIA {self.agent.jid}] REQUEST enviado para {tl_jid}")

        self.add_behaviour(MovementBehaviour(self))

        class ReceiveResponseBehaviour(CyclicBehaviour):
            async def run(self):
                msg = await self.receive(timeout=1)
                if msg:
                    performative = msg.get_metadata("performative")
                    if performative == "agree":
                        print(f"[VEÍCULO EMERGÊNCIA {self.agent.jid}] AGREE recebido")
                    elif performative == "inform":
                        print(f"[VEÍCULO EMERGÊNCIA {self.agent.jid}] INFORM: {msg.body}")

        template = Template()
        template.set_metadata("protocol", "fipa-request")
        self.add_behaviour(ReceiveResponseBehaviour(), template)
