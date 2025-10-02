import asyncio
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from aiohttp import web
import json
from datetime import datetime
from collections import defaultdict

# ===============================
# CONFIGURAÇÃO GLOBAL
# ===============================
grid_size = 5
carros = []
dashboard_logs = []
direcoes = ["NORTE", "ESTE", "OESTE", "SUL"]

# Mapeamento para que o Carro saiba qual Semáforo monitorizar
# Direção do Carro -> {Nome do Semáforo a monitorizar, JID do Semáforo}
# Este mapeamento garante que o carro vê o semáforo que regula a sua entrada no cruzamento.
car_light_map = {
    "NORTE": {"name": "S4", "jid": "semaforo4@localhost"},
    # Carro de CIMA (Norte) é parado pelo S4 (Sul, na extremidade)
    "SUL": {"name": "S1", "jid": "semaforo1@localhost"},
    # Carro de BAIXO (Sul) é parado pelo S1 (Norte, na extremidade)
    "OESTE": {"name": "S2", "jid": "semaforo2@localhost"},
    # Carro da DIREITA (Oeste) é parado pelo S2 (Este, na extremidade)
    "ESTE": {"name": "S3", "jid": "semaforo3@localhost"}
    # Carro da ESQUERDA (Este) é parado pelo S3 (Oeste, na extremidade)
}

# Posições dos semáforos (AO LADO DAS ESTRADAS)
semaforo_positions = {
    "S1": (0, 3),  # N/S (Para carros vindos do Sul)
    "S2": (3, 4),  # E/O (Para carros vindos do Oeste)
    "S3": (1, 0),  # E/O (Para carros vindos do Este)
    "S4": (4, 1)  # N/S (Para carros vindos do Norte)
}

# Estado global para a dashboard web (o TrafficLightAgent atualiza isto)
semaforo_states = {
    "S1": "VERDE",
    "S2": "VERMELHO",
    "S3": "VERMELHO",
    "S4": "VERDE"
}

# Definir estradas (posições onde carros podem estar)
estradas = {
    (0, 2), (1, 2), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (3, 2), (4, 2)
}


# ===============================
# FUNÇÕES DE UTILIDADE
# ===============================
def add_log(msg):
    """Adiciona uma mensagem ao registro de logs do dashboard."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    dashboard_logs.append({"time": timestamp, "msg": msg})
    if len(dashboard_logs) > 50:
        dashboard_logs.pop(0)


def print_grid():
    """Imprime o estado atual da grid na consola (apenas para debug)."""
    grid = [["-" for _ in range(grid_size)] for _ in range(grid_size)]

    # Desenhar estradas
    for row, col in estradas:
        grid[row][col] = "+"

    # Colocar semáforos
    for name, (row, col) in semaforo_positions.items():
        grid[row][col] = name

        # Colocar carros
    for c in carros:
        row, col = c['pos']
        if 0 <= row < grid_size and 0 <= col < grid_size:
            grid[row][col] = "C"

    print("\n")
    for row in grid:
        print(" ".join(row))
    print("\n")


def calcular_posicao(direcao, step):
    """Calcula a posição (row, col) baseada na direção e step.
       step 0 = Entrada, step 1 = Posição de Paragem/Semáforo, step 2 = Centro
    """
    if direcao == "NORTE":  # De (4, 2) para (0, 2)
        return (4 - step, 2)
    elif direcao == "SUL":  # De (0, 2) para (4, 2)
        return (0 + step, 2)
    elif direcao == "OESTE":  # De (2, 4) para (2, 0)
        return (2, 4 - step)
    elif direcao == "ESTE":  # De (2, 0) para (2, 4)
        return (2, 0 + step)
    return (2, 2)


# ===============================
# AGENTE SEMÁFORO
# ===============================
class TrafficLightAgent(Agent):
    def __init__(self, jid, password, light_name):
        super().__init__(jid, password)
        self.light_name = light_name
        self.state = semaforo_states[light_name]

    class LightBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                new_state = msg.body
                if new_state in ["VERDE", "AMARELO", "VERMELHO"]:
                    self.agent.state = new_state
                    global semaforo_states
                    semaforo_states[self.agent.light_name] = self.agent.state

                    log_msg = f"[{self.agent.light_name}] mudou para {self.agent.state}"
                    print(log_msg)
                    add_log(log_msg)

    async def setup(self):
        log_msg = f"Semáforo {self.light_name} iniciado ({self.state})"
        print(log_msg)
        add_log(log_msg)
        self.add_behaviour(self.LightBehaviour())


# ===============================
# AGENTE CENTRAL
# ===============================
class CentralAgent(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.cycle = 0

    class CentralBehaviour(CyclicBehaviour):
        """Controla o ciclo de tempo dos semáforos."""

        async def run(self):
            # O ciclo é de 7 segundos (5s Verde + 2s Amarelo)
            await asyncio.sleep(7)

            # 1. Ciclo N/S (Verde) / E/O (Vermelho)
            if self.agent.cycle == 0:
                log_msg = "[Central] N/S VERDE -> AMARELO"
                add_log(log_msg)

                # N/S para AMARELO
                for s_jid in ["semaforo1@localhost", "semaforo4@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "AMARELO"
                    await self.send(msg)
                await asyncio.sleep(2)  # Pausa para o Amarelo

                # N/S para VERMELHO, E/O para VERDE
                log_msg = "[Central] E/O VERDE | N/S VERMELHO"
                add_log(log_msg)

                for s_jid in ["semaforo2@localhost", "semaforo3@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "VERDE"
                    await self.send(msg)

                for s_jid in ["semaforo1@localhost", "semaforo4@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "VERMELHO"
                    await self.send(msg)

            # 2. Ciclo E/O (Verde) / N/S (Vermelho)
            else:
                log_msg = "[Central] E/O VERDE -> AMARELO"
                add_log(log_msg)

                # E/O para AMARELO
                for s_jid in ["semaforo2@localhost", "semaforo3@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "AMARELO"
                    await self.send(msg)
                await asyncio.sleep(2)  # Pausa para o Amarelo

                # E/O para VERMELHO, N/S para VERDE
                log_msg = "[Central] N/S VERDE | E/O VERMELHO"
                add_log(log_msg)

                for s_jid in ["semaforo1@localhost", "semaforo4@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "VERDE"
                    await self.send(msg)

                for s_jid in ["semaforo2@localhost", "semaforo3@localhost"]:
                    msg = Message(to=s_jid)
                    msg.body = "VERMELHO"
                    await self.send(msg)

            self.agent.cycle = (self.agent.cycle + 1) % 2  # Próximo ciclo

    class RequestHandler(CyclicBehaviour):
        """Lida com pedidos de luz verde dos carros."""

        async def run(self):
            # Espera por uma mensagem com performative "request"
            msg = await self.receive(timeout=1)
            if msg and msg.get_metadata("performative") == "request":
                try:
                    content = json.loads(msg.body)
                    light_name = content['light']
                    direction = content['direction']

                    log_msg = f"[Central - REQUEST] Recebido pedido de VERDE do {msg.sender.split('@')[0]} (Dir: {direction}) para o semáforo {light_name}."
                    print(log_msg)
                    add_log(log_msg)

                    # NOTA: Num sistema real, aqui o Central avaliaria se deve ou não
                    # forçar uma mudança de ciclo para atender a esta requisição.
                    # Por agora, apenas registamos o pedido.

                except Exception as e:
                    print(f"[Central - ERROR] Erro ao processar mensagem de requisição: {e}")

    async def setup(self):
        log_msg = "Central de Controlo iniciada"
        print(log_msg)
        add_log(log_msg)
        self.add_behaviour(self.CentralBehaviour())
        self.add_behaviour(self.RequestHandler())  # Adiciona o novo comportamento


# ===============================
# AGENTE CARRO
# ===============================
class CarAgent(Agent):
    def __init__(self, jid, password, direcao, car_id):
        super().__init__(jid, password)
        self.direcao = direcao
        self.car_id = car_id
        self.step = 0
        self.light_info = car_light_map[direcao]

    class CarBehaviour(CyclicBehaviour):
        async def run(self):
            global semaforo_states

            # Lógica de Paragem no Semáforo (step 1)
            if self.agent.step == 1:
                light_name = self.agent.light_info['name']
                current_state = semaforo_states.get(light_name, "VERMELHO")

                if current_state == "VERMELHO" or current_state == "AMARELO":
                    log_msg = f"[Carro {self.agent.car_id}] PAROU em {light_name} ({current_state}). Aguarda..."
                    print(log_msg)
                    add_log(log_msg)

                    light_turned_green = False

                    # Esperar 5 segundos
                    for _ in range(5):
                        await asyncio.sleep(1)
                        current_state = semaforo_states.get(light_name, "VERMELHO")
                        if current_state == "VERDE":
                            light_turned_green = True
                            log_msg = f"[Carro {self.agent.car_id}] Arranca. {light_name} VERDE."
                            print(log_msg)
                            add_log(log_msg)
                            break

                    # Se não ficou VERDE após 5 segundos, envia pedido à Central
                    if not light_turned_green:
                        log_msg = f"[Carro {self.agent.car_id}] Pedindo VERDE para {light_name} à Central (após 5s)."
                        print(log_msg)
                        add_log(log_msg)

                        msg = Message(to="central@localhost")
                        msg.set_metadata("performative", "request")
                        msg.body = json.dumps({"light": light_name, "direction": self.agent.direcao})
                        await self.send(msg)

                        # Esperar indefinidamente até o semáforo ficar VERDE
                        while semaforo_states.get(light_name, "VERMELHO") != "VERDE":
                            await asyncio.sleep(0.5)

                        log_msg = f"[Carro {self.agent.car_id}] Arranca após pedido e espera. {light_name} VERDE."
                        print(log_msg)
                        add_log(log_msg)

                    # Se o carro estava parado e o semáforo ficou VERDE, o código continua abaixo

            # Lógica de Movimento (para todos os passos)
            if self.agent.step <= 4:
                pos = calcular_posicao(self.agent.direcao, self.agent.step)

                # Atualizar posição do carro
                global carros
                carros = [c for c in carros if c['id'] != self.agent.car_id]
                carros.append({
                    'id': self.agent.car_id,
                    'direcao': self.agent.direcao,
                    'pos': pos
                })

                print_grid()
                self.agent.step += 1
                await asyncio.sleep(1)
            else:
                # O carro chegou ao fim do seu percurso
                log_msg = f"[Carro {self.agent.car_id}] saiu do cruzamento (direção: {self.agent.direcao})"
                print(log_msg)
                add_log(log_msg)
                carros[:] = [c for c in carros if c['id'] != self.agent.car_id]
                print_grid()
                await self.agent.stop()

    async def setup(self):
        log_msg = f"Carro {self.car_id} entrou (direção: {self.direcao})"
        print(log_msg)
        add_log(log_msg)
        self.add_behaviour(self.CarBehaviour())


# ===============================
# DASHBOARD WEB - AIOHTTP
# ===============================
async def handle_dashboard(request):
    """Serve a página HTML do dashboard."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Sistema de Trânsito</title>
        <style>
            body {
                font-family: 'Inter', sans-serif;
                background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%);
                margin: 0;
                padding: 20px;
                color: #e0e7ff;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: #fff;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                padding: 30px;
                color: #333;
            }
            h1 {
                color: #1e3a8a;
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.5em;
            }
            .grid-container {
                display: flex;
                justify-content: center;
                margin-bottom: 30px;
            }
            .grid {
                display: inline-grid;
                grid-template-columns: repeat(5, 70px);
                gap: 5px;
                background: #e0e7ff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: inset 0 0 10px rgba(0,0,0,0.1);
            }
            .cell {
                width: 70px;
                height: 70px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                font-weight: bold;
                border-radius: 8px;
                transition: background 0.3s, transform 0.1s;
                user-select: none;
            }
            .road { 
                background: #4b5563; 
                color: white; 
                box-shadow: inset 0 0 5px rgba(0,0,0,0.5);
            }
            .empty { background: #d1d5db; }

            /* Estilos para os semáforos AGORA COLORIDOS */
            .semaforo-side {
                color: #fff;
                text-shadow: 1px 1px 2px #000;
                font-size: 1.2em;
                border: 3px solid #374151;
            }
            .light-red { 
                background: linear-gradient(145deg, #ef4444, #b91c1c); 
                box-shadow: 0 4px 10px rgba(185, 28, 28, 0.6);
            }
            .light-green { 
                background: linear-gradient(145deg, #4ade80, #16a34a); 
                box-shadow: 0 4px 10px rgba(22, 163, 74, 0.6);
            }
            .light-yellow { 
                background: linear-gradient(145deg, #fcd34d, #d97706); 
                box-shadow: 0 4px 10px rgba(217, 119, 6, 0.6);
            }

            .car { 
                background: #3b82f6; 
                color: white; 
                font-size: 30px;
                box-shadow: 0 0 15px rgba(59, 130, 246, 0.7);
                animation: pulse 1s infinite alternate;
            }
            @keyframes pulse {
                0% { transform: scale(1.0); }
                100% { transform: scale(1.05); }
            }
            .logs {
                background: #f9fafb;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                padding: 20px;
                max-height: 400px;
                overflow-y: auto;
                box-shadow: inset 0 0 8px rgba(0,0,0,0.05);
            }
            .log-entry {
                padding: 10px;
                margin: 5px 0;
                background: white;
                border-left: 4px solid #3b82f6;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
            .log-time {
                color: #6b7280;
                font-weight: bold;
                margin-right: 10px;
            }
            h2 {
                color: #1e3a8a;
                margin-top: 0;
                border-bottom: 2px solid #eff6ff;
                padding-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sistema de Controlo de Trânsito Inteligente</h1>
            <div class="grid-container">
                <div class="grid" id="grid"></div>
            </div>
            <div class="logs">
                <h2>Registo de Eventos (Logs)</h2>
                <div id="logs"></div>
            </div>
        </div>
        <script>
            async function updateDashboard() {
                try {
                    const response = await fetch('/data');
                    const data = await response.json();

                    const gridElement = document.getElementById('grid');
                    gridElement.innerHTML = '';

                    // Mapeamento das posições para o estado do semáforo
                    const semaforoStates = data.semaforo_states;

                    data.grid.forEach((row, rowIndex) => {
                        row.forEach((cell, colIndex) => {
                            const cellDiv = document.createElement('div');
                            cellDiv.className = 'cell';

                            if (semaforoStates[cell]) {
                                // A célula contém um semáforo (S1, S2, S3, S4)
                                const state = semaforoStates[cell];
                                cellDiv.className += ' semaforo-side';
                                cellDiv.textContent = cell;

                                if (state === 'VERMELHO') {
                                    cellDiv.className += ' light-red';
                                } else if (state === 'VERDE') {
                                    cellDiv.className += ' light-green';
                                } else if (state === 'AMARELO') {
                                    cellDiv.className += ' light-yellow';
                                }
                            } else if (cell === '+') {
                                // A célula é uma estrada
                                cellDiv.className += ' road';
                                cellDiv.textContent = '';
                            } else if (cell === 'C') {
                                // A célula contém um carro
                                cellDiv.className += ' car';
                                cellDiv.textContent = '🚗';
                            } else {
                                // A célula está vazia
                                cellDiv.className += ' empty';
                                cellDiv.textContent = '🌳';
                            }

                            gridElement.appendChild(cellDiv);
                        });
                    });

                    // Atualizar logs
                    const logsElement = document.getElementById('logs');
                    logsElement.innerHTML = '';
                    data.logs.slice().reverse().forEach(log => {
                        const logDiv = document.createElement('div');
                        logDiv.className = 'log-entry';
                        logDiv.innerHTML = `<span class="log-time">[${log.time}]</span>${log.msg}`;
                        logsElement.appendChild(logDiv);
                    });

                } catch (error) {
                    console.error("Erro ao atualizar o dashboard:", error);
                }
            }

            updateDashboard();
            setInterval(updateDashboard, 500); // Atualiza a cada 0.5 segundos
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')


async def handle_data(request):
    """Retorna os dados da simulação (grid, logs, e estados dos semáforos) em JSON."""
    # 1. Montar a grid com as posições atualizadas
    grid = [["-" for _ in range(grid_size)] for _ in range(grid_size)]

    # Adicionar estradas
    for row, col in estradas:
        grid[row][col] = "+"

    # Adicionar semáforos (usando o nome para que o JS saiba qual é)
    for name, (row, col) in semaforo_positions.items():
        if 0 <= row < grid_size and 0 <= col < grid_size:
            grid[row][col] = name

            # Adicionar carros
    for c in carros:
        row, col = c['pos']
        if 0 <= row < grid_size and 0 <= col < grid_size:
            grid[row][col] = "C"

    # 2. Preparar os dados para o dashboard
    data = {
        'grid': grid,
        'logs': dashboard_logs,
        'semaforo_states': semaforo_states,
        'semaforo_positions': semaforo_positions
    }
    return web.Response(text=json.dumps(data), content_type='application/json')


async def start_web_server():
    """Inicia o servidor AioHTTP."""
    app = web.Application()
    app.router.add_get('/', handle_dashboard)
    app.router.add_get('/data', handle_data)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    print("Dashboard disponível em: http://localhost:8080")
    add_log("Dashboard web iniciado em http://localhost:8080")


# ===============================
# MAIN
# ===============================
async def main():
    # Iniciar servidor web
    await start_web_server()

    # Criar semáforos
    semaforos = [
        TrafficLightAgent("semaforo1@localhost", "123456", "S1"),
        TrafficLightAgent("semaforo2@localhost", "123456", "S2"),
        TrafficLightAgent("semaforo3@localhost", "123456", "S3"),
        TrafficLightAgent("semaforo4@localhost", "123456", "S4")
    ]
    for s in semaforos:
        await s.start(auto_register=True)

    # Criar central
    central = CentralAgent("central@localhost", "123456")
    await central.start(auto_register=True)

    print("Sistema iniciado! Criando carros continuamente...")
    add_log("Sistema de trânsito totalmente operacional")

    # Loop infinito criando carros (um de cada vez, alternando as direções)
    car_counter = 1
    direction_index = 0
    while True:
        # Pega a próxima direção no ciclo
        d = direcoes[direction_index % len(direcoes)]

        carro = CarAgent(f"carro{car_counter}@localhost", "123456", d, car_counter)
        await carro.start(auto_register=True)

        direction_index += 1
        car_counter += 1

        # MUDANÇA: Reseta o contador de carros e o índice de direção após o 4º carro
        if car_counter > 4:
            car_counter = 1
            direction_index = 0

        # Cria um novo carro a cada 4 segundos, permitindo que os anteriores parem
        await asyncio.sleep(4)


if __name__ == "__main__":
    asyncio.run(main())
