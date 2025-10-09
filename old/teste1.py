import asyncio
from spade import agent, behaviour, message, template


class TrafficLight(agent.Agent):
    class LightBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            estados = ["VERDE", "AMARELO", "VERMELHO"]
            for estado in estados:
                self.agent.estado = estado
                print(f"[{self.agent.name}] Semáforo = {estado}")
                await asyncio.sleep(5)

        # este comportamento corre para responder aos carros
    class RespondBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                resposta = message.Message(
                    to=str(msg.sender),
                    body=self.agent.estado
                )
                await self.send(resposta)

    async def setup(self):
        self.estado = "VERMELHO"
        print(f"Semáforo {self.name} iniciado.")
        self.add_behaviour(self.LightBehaviour())
        self.add_behaviour(self.RespondBehaviour(), template.Template())


class Car(agent.Agent):
    class DriveBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            # ao chegar ao cruzamento, pergunta ao semáforo
            msg = message.Message(to="semaforo@localhost", body="Posso passar?")
            await self.send(msg)

            resposta = await self.receive(timeout=5)
            if resposta:
                if resposta.body == "VERDE":
                    print(f"[{self.agent.name}] Semáforo VERDE -> Avançar 🚗💨")
                else:
                    print(f"[{self.agent.name}] Semáforo {resposta.body} -> Parar 🛑")

            await asyncio.sleep(3)  # tempo até ao próximo cruzamento

    async def setup(self):
        print(f"Carro {self.name} iniciado.")
        self.add_behaviour(self.DriveBehaviour())


async def main():
    semaforo = TrafficLight("agent1@localhost", "12345", verify_security=False)
    carro = Car("agent2@localhost", "12345", verify_security=False)

    await semaforo.start()
    await carro.start()

    print("Simulação em execução. Ctrl+C para parar.")
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("A desligar...")