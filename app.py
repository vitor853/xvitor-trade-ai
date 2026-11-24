import os
import time
import threading
import requests
from flask import Flask, jsonify

app = Flask(__name__)

KEY = os.environ.get("COINGECKO_API_KEY", "")
LOCK = threading.Lock()
CACHE = {}
NEXT = 0
UPDATED = 0
STATUS = "Aguardando"

@app.route("/precos")
def precos():
    global CACHE, NEXT, UPDATED, STATUS

    with LOCK:
        if time.monotonic() >= NEXT:
            NEXT = time.monotonic() + 300

            try:
                if not KEY:
                    raise ValueError("Chave ausente")

                r = requests.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    headers={"x-cg-demo-api-key": KEY},
                    params={
                        "ids": "bitcoin,ethereum,solana",
                        "vs_currencies": "brl"
                    },
                    timeout=10
                )
                r.raise_for_status()
                d = r.json()

                novos = {
                    "BTC": float(d["bitcoin"]["brl"]),
                    "ETH": float(d["ethereum"]["brl"]),
                    "SOL": float(d["solana"]["brl"])
                }

                if not all(0 < p < float("inf") for p in novos.values()):
                    raise ValueError("Preco invalido")

                CACHE = novos
                UPDATED = time.time()
                STATUS = "Mercado conectado"

            except requests.HTTPError as e:
                STATUS = "Erro API: " + str(e.response.status_code)
                if e.response.status_code == 429:
                    NEXT = time.monotonic() + 600

            except Exception:
                STATUS = "Falha na conexao ou configuracao"

        return jsonify({
            "precos": CACHE,
            "atualizado": UPDATED,
            "status": STATUS
        })

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XVITOR TRADE AI</title>

<style>
*{box-sizing:border-box}
body{
 background:#090909;
 color:white;
 font-family:Arial,sans-serif;
 padding:14px;
 max-width:650px;
 margin:auto
}
h1{color:#ff2525;font-size:27px}
h2{font-size:19px}
.card{
 background:#181818;
 border:1px solid #333;
 padding:18px;
 border-radius:16px;
 margin-bottom:14px
}
.saldo{font-size:32px;color:#39dc80}
small{color:#aaa}
.grid{
 display:grid;
 grid-template-columns:1fr 1fr;
 gap:14px
}
button{
 width:100%;
 padding:16px;
 border:0;
 border-radius:10px;
 color:white;
 font-size:16px;
 font-weight:bold;
 margin-top:8px
}
.start{background:#15803d}
.stop{background:#b91c1c}
.reset{background:#333}
.coin{
 padding:14px 0;
 border-bottom:1px solid #333
}
canvas{width:100%;height:160px}
#historico{
 font-size:13px;
 white-space:pre-wrap;
 overflow-wrap:anywhere;
 max-height:350px;
 overflow:auto
}
</style>
</head>

<body>

<h1>XVITOR TRADE AI</h1>
<p>V1.2 | TRADING SIMULATOR</p>
<small>SIMULAÇÃO • SEM DINHEIRO REAL</small>

<div class="card">
 <p>Patrimônio virtual</p>
 <div class="saldo" id="saldo">R$ 1.000,00</div>

 <div class="grid">
  <div>
   <p>Lucro / prejuízo</p>
   <b id="lucro">R$ 0,00</b>
  </div>
  <div>
   <p>Rentabilidade</p>
   <b id="percentual">0%</b>
  </div>
  <div>
   <p>Disponível</p>
   <b id="caixa"></b>
  </div>
  <div>
   <p>Operações</p>
   <b id="total">0</b>
  </div>
 </div>
</div>

<div class="card">
 <h2>Desempenho virtual</h2>
 <canvas id="grafico" width="600" height="200"></canvas>
</div>

<div class="card">
 <h2>Mercado em BRL</h2>
 <div class="coin" id="BTC">Bitcoin: aguardando</div>
 <div class="coin" id="ETH">Ethereum: aguardando</div>
 <div class="coin" id="SOL">Solana: aguardando</div>
 <p id="hora"></p>
 <small>Dados fornecidos pela CoinGecko</small>
</div>

<div class="card">
 <h2>Controle do robô</h2>
 <p id="status">Robô parado</p>
 <p id="conexao">Conectando...</p>

 <button class="start" onclick="iniciar()">
 INICIAR ROBÔ
 </button>

 <button class="stop" onclick="parar()">
 PARAR ROBÔ
 </button>

 <button class="reset" onclick="resetar()">
 REINICIAR SIMULAÇÃO
 </button>

 <p><small>
 Compra virtual: R$ 100<br>
 Stop Loss: 2%<br>
 Take Profit: 3%<br>
 Taxa: 0,1% por ordem<br>
 Limite diário: 2%<br>
 Estratégia experimental de tendência.
 </small></p>
</div>

<div class="card">
 <h2>Posições abertas</h2>
 <div id="posicoes">Nenhuma posição</div>
</div>

<div class="card">
 <h2>Histórico de operações</h2>
 <div id="historico">Nenhuma operação</div>
</div>

<div class="card">
 <small>
 Simulação executada neste navegador.
 Mantenha a página aberta.
 Dados salvos localmente neste dispositivo.
 Stop Loss não garante o preço de saída.
 </small>
</div>

<script>

const MOEDAS = ["BTC","ETH","SOL"];
const TAXA = 0.001;
const VALOR = 100;

function novo(){
 return {
  caixa:1000,
  pos:{},
  historico:[],
  curva:[1000],
  amostras:{BTC:[],ETH:[],SOL:[]},
  precos:{},
  ultimo:0,
  total:0,
  dia:"",
  baseDia:1000,
  bloqueado:false
 };
}

let s = novo();
let ativo = false;
let ocupado = false;

try{
 const salvo = localStorage.getItem("xvitor_v12");
 if(salvo) s = JSON.parse(salvo);
}catch(e){}

function salvar(){
 try{
  localStorage.setItem("xvitor_v12",JSON.stringify(s));
 }catch(e){
  document.getElementById("status").textContent =
   "Aviso: armazenamento indisponível";
 }
}

function dinheiro(n){
 return Number(n).toLocaleString("pt-BR",{
  style:"currency",currency:"BRL"
 });
}

function patrimonio(){
 let valor = s.caixa;
 for(const m of Object.keys(s.pos)){
  const p = s.pos[m];
  valor += p.qtd * (s.precos[m] || p.entrada) * (1-TAXA);
 }
 return valor;
}

function registrar(texto){
 s.historico.unshift(
  new Date().toLocaleString("pt-BR")+" | "+texto
 );
 s.historico = s.historico.slice(0,200);
 s.total++;
}

function comprar(m,preco){
 if(s.caixa < VALOR || s.pos[m]) return;

 s.caixa -= VALOR;

 s.pos[m] = {
  qtd:VALOR*(1-TAXA)/preco,
  entrada:preco,
  custo:VALOR
 };

 registrar("COMPRA "+m+" | "+dinheiro(VALOR));
}

function vender(m,preco,motivo){
 const p = s.pos[m];
 if(!p) return;

 const recebido = p.qtd*preco*(1-TAXA);
 const resultado = recebido-p.custo;

 s.caixa += recebido;
 delete s.pos[m];

 registrar(
  "VENDA "+m+" | "+motivo+
  " | Resultado: "+dinheiro(resultado)
 );
}

function analisar(){
 const hoje = new Date().toLocaleDateString("pt-BR");

 if(s.dia !== hoje){
  s.dia = hoje;
  s.baseDia = patrimonio();
  s.bloqueado = false;
 }

 if(patrimonio() <= s.baseDia*0.98){
  for(const m of Object.keys(s.pos)){
   vender(m,s.precos[m],"Limite diário");
  }
  s.bloqueado = true;
  ativo = false;
  return;
 }

 if(!ativo || s.bloqueado) return;

 for(const m of MOEDAS){
  const preco = s.precos[m];
  if(!preco) continue;

  const p = s.pos[m];

  if(p){
   const variacao = preco/p.entrada-1;

   if(variacao <= -0.02){
    vender(m,preco,"Stop Loss");
   }else if(variacao >= 0.03){
    vender(m,preco,"Take Profit");
   }

  }else{
   const a = s.amostras[m];

   if(a.length >= 3){
    const anterior = a[a.length-2];
    const inicial = a[a.length-3];

    if(preco > anterior && anterior > inicial &&
       preco/inicial-1 >= 0.003){
     comprar(m,preco);
    }
   }
  }
 }
}

function desenhar(){
 const c = document.getElementById("grafico");
 const ctx = c.getContext("2d");

 ctx.clearRect(0,0,c.width,c.height);

 const a = s.curva;
 const min = Math.min(...a)-1;
 const max = Math.max(...a)+1;

 ctx.strokeStyle="#333";
 ctx.lineWidth=1;

 for(let i=0;i<5;i++){
  ctx.beginPath();
  ctx.moveTo(0,i*49);
  ctx.lineTo(c.width,i*49);
  ctx.stroke();
 }

 ctx.strokeStyle =
  patrimonio()>=1000?"#39dc80":"#ff3535";

 ctx.lineWidth=3;
 ctx.beginPath();

 a.forEach((v,i)=>{
  const x=i/Math.max(1,a.length-1)*c.width;
  const y=c.height-10-
   (v-min)/(max-min)*(c.height-20);

  if(i===0)ctx.moveTo(x,y);
  else ctx.lineTo(x,y);
 });

 if(a.length===1){
  ctx.lineTo(c.width,c.height/2);
 }

 ctx.stroke();
}

function painel(){
 const p = patrimonio();
 const lucro = p-1000;

 document.getElementById("saldo").textContent =
  dinheiro(p);

 document.getElementById("lucro").textContent =
  dinheiro(lucro);

 document.getElementById("lucro").style.color =
  lucro>=0?"#39dc80":"#ff3535";

 document.getElementById("percentual").textContent =
  (lucro/1000*100).toFixed(2)+"%";

 document.getElementById("caixa").textContent =
  dinheiro(s.caixa);

 document.getElementById("total").textContent =
  s.total;

 document.getElementById("status").textContent =
  s.bloqueado?"Limite diário atingido":
  ativo?"Robô ativo":"Robô parado";

 document.getElementById("historico").textContent =
  s.historico.join("\\n\\n") || "Nenhuma operação";

 document.getElementById("posicoes").textContent =
  Object.keys(s.pos).map(m=>
   m+" | "+dinheiro(
    s.pos[m].qtd*(s.precos[m]||s.pos[m].entrada)
   )
  ).join(" • ") || "Nenhuma posição";

 desenhar();
}

async function atualizar(){
 if(ocupado) return;
 ocupado=true;

 try{
  const r=await fetch("/precos",{cache:"no-store"});
  if(!r.ok) throw Error("HTTP");
  const d=await r.json();

  document.getElementById("conexao").textContent =
   d.status;

  for(const m of MOEDAS){
   const preco=d.precos[m];

   document.getElementById(m).textContent =
    m+": "+(preco?dinheiro(preco):"Indisponível");
  }

  document.getElementById("hora").textContent =
   d.atualizado?
   "Atualizado: "+new Date(d.atualizado*1000)
   .toLocaleString("pt-BR"):
   "Sem cotação";

  const recente =
   Date.now()/1000-d.atualizado < 360;

  const valido = MOEDAS.every(m=>
   Number.isFinite(d.precos[m]) && d.precos[m]>0
  );

  if(d.status==="Mercado conectado" &&
     recente && valido &&
     d.atualizado>s.ultimo){

   s.precos=d.precos;
   s.ultimo=d.atualizado;

   for(const m of MOEDAS){
    s.amostras[m].push(s.precos[m]);
    s.amostras[m]=s.amostras[m].slice(-20);
   }

   if(ativo) analisar();

   s.curva.push(patrimonio());
   s.curva=s.curva.slice(-288);

   salvar();
  }

  painel();

 }catch(e){
  document.getElementById("conexao").textContent =
   "Falha de conexão. Sem novas ordens.";
 }finally{
  ocupado=false;
 }
}

function iniciar(){
 const hoje=new Date().toLocaleDateString("pt-BR");

 if(s.dia!==hoje){
  s.dia=hoje;
  s.baseDia=patrimonio();
  s.bloqueado=false;
 }

 if(s.bloqueado){
  alert("Limite diário atingido.");
  return;
 }

 ativo=true;
 salvar();
 painel();
 atualizar();
}

function parar(){
 ativo=false;
 salvar();
 painel();
}

function resetar(){
 if(!confirm("Apagar todas as operações virtuais?"))
  return;

 ativo=false;
 s=novo();
 salvar();
 painel();
 atualizar();
}

painel();
atualizar();
setInterval(atualizar,30000);

</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT",8000))
    )
    
