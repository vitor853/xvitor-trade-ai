import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

MOEDAS = ["BTC", "ETH", "SOL"]

@app.route("/precos")
def precos():
    resultado = {}
    for moeda in MOEDAS:
        try:
            resposta = requests.get(
                "https://data-api.binance.vision/api/v3/ticker/price",,
                params={"symbol": moeda + "USDT"},
                timeout=10
            )
            resposta.raise_for_status()
            resultado[moeda] = float(resposta.json()["price"])
        except (requests.RequestException, KeyError, ValueError):
            resultado[moeda] = None
    return jsonify(resultado)

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
        padding: 20px;
    }
    h1 { color: #ff2525; }
    .card {
        background: #181818;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        border: 1px solid #333;
    }
    .saldo { font-size: 32px; color: #39dc80; }
    </style>
    </head>
    <body>
    <h1>XVITOR TRADE AI</h1>
    <p>V1.0 | Modo simulacao</p>
    <div class="card">
        <p>Saldo virtual inicial</p>
        <div class="saldo">R$ 1.000,00</div>
        <p>Nenhum dinheiro real investido</p>
    </div>
    <div class="card">
        <h2>Mercado em USDT</h2>
        <p id="BTC">Bitcoin: carregando...</p>
        <p id="ETH">Ethereum: carregando...</p>
        <p id="SOL">Solana: carregando...</p>
    </div>
    <div class="card">
        <h2>Status do sistema</h2>
        <p id="status">Conectando ao mercado...</p>
        <p>Operacoes automaticas: desativadas</p>
    </div>
    <script>
    async function atualizar() {
        try {
            const resposta = await fetch('/precos');
            const dados = await resposta.json();
            for (const moeda of ['BTC','ETH','SOL']) {
                document.getElementById(moeda).textContent =
                    moeda + ': ' + (dados[moeda] == null
                    ? 'Indisponivel'
                    : dados[moeda].toFixed(2) + ' USDT');
            }
            document.getElementById('status').textContent =
                Object.values(dados).every(v => v == null)
                ? 'Mercado indisponivel'
                : 'Monitoramento ativo';
        } catch(e) {
            document.getElementById('status').textContent =
                'Falha de conexao';
        }
    }
    atualizar();
    setInterval(atualizar, 15000);
    </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
  
