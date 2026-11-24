import os
import time
import threading
import requests
from flask import Flask, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("COINGECKO_API_KEY", "")
CACHE = {"BTC": None, "ETH": None, "SOL": None}
PROXIMA_CONSULTA = 0
ULTIMA_ATUALIZACAO = None
STATUS = "Aguardando consulta"
LOCK = threading.Lock()

@app.route("/precos")
def precos():
    global CACHE, PROXIMA_CONSULTA
    global STATUS, ULTIMA_ATUALIZACAO

    with LOCK:
        if time.monotonic() >= PROXIMA_CONSULTA:
            PROXIMA_CONSULTA = time.monotonic() + 300

            if not API_KEY:
                STATUS = "Chave API nao configurada"
            else:
                try:
                    resposta = requests.get(
                        "https://api.coingecko.com/api/v3/simple/price",
                        headers={
                            "x-cg-demo-api-key": API_KEY
                        },
                        params={
                            "ids": "bitcoin,ethereum,solana",
                            "vs_currencies": "usd"
                        },
                        timeout=10
                    )

                    resposta.raise_for_status()
                    dados = resposta.json()

                    CACHE = {
                        "BTC": dados["bitcoin"]["usd"],
                        "ETH": dados["ethereum"]["usd"],
                        "SOL": dados["solana"]["usd"]
                    }

                    ULTIMA_ATUALIZACAO = time.time()
                    STATUS = "Mercado conectado"

                except requests.HTTPError as erro:
                    codigo = erro.response.status_code
                    STATUS = f"Erro API: {codigo}"
                    app.logger.warning(STATUS)

                    if codigo == 429:
                        PROXIMA_CONSULTA = time.monotonic() + 600

                except Exception:
                    STATUS = "Falha na consulta de precos"
                    app.logger.warning(STATUS)

        return jsonify({
            **CACHE,
            "status": STATUS,
            "atualizado": ULTIMA_ATUALIZACAO
        })

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>XVITOR TRADE AI</title>
    <style>
    body {
        background: #090909;
        color: white;
        font-family: Arial, sans-serif;
        padding: 18px;
    }
    h1 { color: #ff2525; }
    .card {
        background: #181818;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        border: 1px solid #333;
    }
    .saldo {
        font-size: 32px;
        color: #39dc80;
    }
    small { color: #aaa; }
    </style>
    </head>
    <body>

    <h1>XVITOR TRADE AI</h1>
    <p>V1.1 | Modo simulação</p>

    <div class="card">
        <p>Saldo virtual inicial</p>
        <div class="saldo">R$ 1.000,00</div>
        <p>Nenhum dinheiro real investido</p>
    </div>

    <div class="card">
        <h2>Mercado em USD</h2>
        <p id="BTC">Bitcoin: carregando...</p>
        <p id="ETH">Ethereum: carregando...</p>
        <p id="SOL">Solana: carregando...</p>
        <small>Fonte: CoinGecko</small>
        <p id="hora"></p>
    </div>

    <div class="card">
        <h2>Status do sistema</h2>
        <p id="status">Conectando...</p>
        <p>Operações automáticas: desativadas</p>
        <small>Consulta externa a cada 5 minutos,
        enquanto houver acesso ao painel.</small>
    </div>

    <script>
    async function atualizar() {
        try {
            const resposta = await fetch('/precos', {
                cache: 'no-store'
            });
            const dados = await resposta.json();

            for (const moeda of ['BTC','ETH','SOL']) {
                document.getElementById(moeda).textContent =
                    moeda + ': ' + (
                    dados[moeda] == null
                    ? 'Indisponível'
                    : Number(dados[moeda]).toLocaleString(
                        'en-US', {
                            style: 'currency',
                            currency: 'USD'
                        }
                    ));
            }

            document.getElementById('status').textContent =
                dados.status;

            document.getElementById('hora').textContent =
                dados.atualizado
                ? 'Última atualização: ' +
                  new Date(dados.atualizado * 1000)
                  .toLocaleString('pt-BR')
                : 'Sem preços disponíveis';

        } catch(e) {
            document.getElementById('status').textContent =
                'Falha de conexão';
        }
    }

    atualizar();
    setInterval(atualizar, 30000);
    </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
    
