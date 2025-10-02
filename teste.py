import asyncio
from spade import agent, behaviour, message, template

class Agent1(agent.Agent):
    class ControlBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:

                try:
                    valor = float(msg.body)
                except ValueError:
                    print(f"[{self.agent.name}] recebeu valor inválido: {msg.body}")
                    return

                setpoint = 22

                erro = setpoint - valor

                acao = "Aumentar" if erro > 0 else "Diminuir"
                print(f"[{self.agent.name}] temperatura={valor}, ação: {acao}")

                resposta = message.Message(
                    to=str(msg.sender),
                    body=f"Ação sugerida: {acao}"
                )
                await self.send(resposta)

    async def setup(self):
        print(f"Agente {self.name} iniciado.")
        msg_template = template.Template()
        self.add_behaviour(self.ControlBehaviour(), msg_template)


class Agent2(agent.Agent):
    class PromptBehaviour(behaviour.CyclicBehaviour):
        async def run(self):

            temp = await asyncio.to_thread(input, "Introduza a temperatura: ")
            if temp.strip():
                msg = message.Message(
                    to="agent1@localhost",
                    body=temp
                )
                await self.send(msg)

            resposta = await self.receive(timeout=5)
            if resposta:
                print(f"[{self.agent.name}] recebeu do controlo: {resposta.body}")

    async def setup(self):
        print(f"Agente {self.name} iniciado.")
        msg_template = template.Template()
        self.add_behaviour(self.PromptBehaviour(), msg_template)


async def main():
    agent1_ = Agent1("agent1@localhost", "12345", verify_security=False)
    agent2_ = Agent2("agent2@localhost", "12345", verify_security=False)
    agent1_.web.start(hostname="localhost",port="9055")
    agent2_.web.start(hostname="localhost",port="9056")

    await agent1_.start()
    await agent2_.start()

    print("Agentes em execução. Pode agora introduzir temperaturas no prompt.")
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("A desligar...")