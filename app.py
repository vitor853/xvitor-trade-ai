import os, time, threading, secrets, copy
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
URL = os.getenv('SUPABASE_URL','').rstrip('/') + '/rest/v1/robo_estado'
KEY = os.getenv('SUPABASE_SECRET_KEY','')
CG = os.getenv('COINGECKO_API_KEY','')
PASSWORD = os.getenv('ROBO_PASSWORD','')
LOCK = threading.RLock()
MOEDAS = ('BTC','ETH','SOL')
TAXA = .001
STATUS = 'Aguardando cotação'
def status_mercado(s):
    if STATUS.startswith('Falha'):
        return STATUS

    ultimo = s.get('ultimo', 0)

    if ultimo and 0 <= time.time() - ultimo <= 360:
        return 'Mercado conectado'

    if ultimo:
        return 'Cotação desatualizada'

    return 'Aguardando cotação'


def novo():
    return dict(caixa=1000, pos={}, historico=[], curva=[1000], amostras={m:[] for m in MOEDAS}, precos={}, ultimo=0, total=0, dia='', baseDia=1000, bloqueado=False, ativo=False)


def db(method, **kwargs):
    if not KEY or not os.getenv('SUPABASE_URL'):
        raise RuntimeError('Configuração Supabase ausente')
    headers = {'apikey':KEY, 'Content-Type':'application/json', 'Prefer':'return=representation'}
    if not KEY.startswith('sb_secret_'):
        headers['Authorization'] = 'Bearer '+KEY
    r = requests.request(method, URL, headers=headers, params={'id':'eq.1'}, timeout=15, **kwargs)
    r.raise_for_status()
    return r.json()


def carregar():
    rows = db('GET')
    if len(rows)!=1: raise RuntimeError('Estado não encontrado')
    return rows[0]['estado'] or novo()


def salvar(s):
    if len(db('PATCH',json={'estado':s}))!=1: raise RuntimeError('Estado não salvo')


def patrimonio(s):
    return s['caixa']+sum(p['qtd']*s['precos'].get(m,p['entrada'])*(1-TAXA) for m,p in s['pos'].items())


def agora():
    return datetime.now(timezone(timedelta(hours=-4)))


def registrar(s, texto):
    s['historico'].insert(0, agora().strftime('%d/%m/%Y %H:%M:%S')+' | '+texto)
    s['historico']=s['historico'][:200]
    s['total']+=1


def vender(s,m,motivo):
    p=s['pos'].pop(m)
    recebido=p['qtd']*s['precos'][m]*(1-TAXA)
    s['caixa']+=recebido
    registrar(s,f'VENDA {m} | {motivo} | Resultado: R$ {recebido-p["custo"]:.2f}')


def analisar(s):
    hoje=agora().date().isoformat()
    if s['dia']!=hoje:
        s.update(dia=hoje,baseDia=patrimonio(s),bloqueado=False)
    if not s['ativo'] or s['bloqueado']: return
    if patrimonio(s)<=s['baseDia']*.98:
        for m in list(s['pos']): vender(s,m,'Limite diário')
        s.update(bloqueado=True,ativo=False)
        return
    for m in MOEDAS:
        preco=s['precos'][m]
        p=s['pos'].get(m)
        if p:
            v=preco/p['entrada']-1
            if v<=-.02: vender(s,m,'Stop Loss')
            elif v>=.03: vender(s,m,'Take Profit')
        else:
            a=s['amostras'][m]
            if len(a)>=3 and a[-1]>a[-2]>a[-3] and a[-1]/a[-3]-1>=.003 and s['caixa']>=100:
                s['caixa']-=100
                s['pos'][m]=dict(qtd=100*(1-TAXA)/preco,entrada=preco,custo=100)
                registrar(s,f'COMPRA {m} | R$ 100,00')


def ciclo():
    global STATUS
    while True:
        espera=300
        try:
            r=requests.get('https://api.coingecko.com/api/v3/simple/price',headers={'x-cg-demo-api-key':CG},params={'ids':'bitcoin,ethereum,solana','vs_currencies':'brl'},timeout=15)
            if r.status_code==429: espera=600
            r.raise_for_status()
            d=r.json()
            p={m:float(d[n]['brl']) for m,n in zip(MOEDAS,('bitcoin','ethereum','solana'))}
            if not all(0<v<float('inf') for v in p.values()): raise ValueError('Cotação inválida')
            with LOCK:
                s=carregar()
                if time.time()-s['ultimo']>=290:
                    s.update(precos=p,ultimo=time.time())
                    for m in MOEDAS: s['amostras'][m]=(s['amostras'][m]+[p[m]])[-20:]
                    analisar(s)
                    s['curva']=(s['curva']+[patrimonio(s)])[-288:]
                    salvar(s)
                STATUS='Mercado conectado'
        except Exception as e:
            STATUS='Falha de atualização; sem novas ordens'
            app.logger.warning('Falha no ciclo: %s',type(e).__name__)
        time.sleep(espera)


@app.before_request
def proteger():
    if request.path=='/health': return
    a=request.authorization
    if not PASSWORD: return 'Configure ROBO_PASSWORD no Render',503
    if not a or not secrets.compare_digest(a.username or '', 'xvitor') or not secrets.compare_digest((a.password or '').encode(),PASSWORD.encode()):
        return Response('Login necessário',401,{'WWW-Authenticate':'Basic realm="XVITOR"'})

@app.get('/health')
def health(): return 'ok'

@@app.get('/estado')
def estado():
    try:
        with LOCK:
            s = carregar()
            return jsonify(
                **s,
                patrimonio=patrimonio(s),
                status=status_mercado(s)
            )
    except Exception:
        return jsonify(erro='Banco indisponível'),503

@app.post('/controle/<acao>')
def controle(acao):
    if request.headers.get('X-Xvitor')!='1': return '',403
    try:
        with LOCK:
            s=carregar()
            if acao=='iniciar':
                if s['dia']!=agora().date().isoformat(): s.update(dia=agora().date().isoformat(),baseDia=patrimonio(s),bloqueado=False)
                if s['bloqueado']: return jsonify(erro='Limite diário atingido'),409
                s['ativo']=True
            elif acao=='parar': s['ativo']=False
            elif acao=='resetar': s=novo()
            else: return '',404
            salvar(s)
        return jsonify(ok=True)
    except Exception: return jsonify(erro='Banco indisponível'),503

@app.get('/precos')
def precos():
    try:
        with LOCK:
            s = carregar()
            return jsonify(
                precos=s['precos'],
                atualizado=s['ultimo'],
                status=status_mercado(s)
            )
    except Exception:
        return jsonify(erro='Banco indisponível'),503

@app.get('/')
def home():
    return r'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>XVITOR TRADE AI</title><style>*{box-sizing:border-box}body{background:#090909;color:white;font:16px Arial;max-width:650px;margin:auto;padding:14px}h1{color:#ff2525;font-size:27px}h2{font-size:19px}.card{background:#181818;border:1px solid #333;padding:18px;border-radius:16px;margin:14px 0}.saldo{font-size:32px;color:#39dc80}small{color:#aaa}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}button{width:100%;padding:16px;border:0;border-radius:10px;color:white;font-weight:bold;margin-top:8px;background:#333}canvas{width:100%;height:160px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:350px;overflow:auto}</style><h1>XVITOR TRADE AI</h1><p>V1.3 | TRADING SIMULATOR</p><small>SIMULAÇÃO • SEM DINHEIRO REAL</small><div class="card">Patrimônio virtual<p class="saldo" id="saldo">Aguardando</p><div class="grid"><div>Lucro / prejuízo<p id="lucro"></p></div><div>Rentabilidade<p id="pct"></p></div><div>Disponível<p id="caixa"></p></div><div>Operações<p id="total"></p></div></div></div><div class="card"><h2>Desempenho virtual</h2><canvas id="grafico" width="600" height="200"></canvas></div><div class="card"><h2>Mercado em BRL</h2><p id="BTC"></p><p id="ETH"></p><p id="SOL"></p><p id="hora"></p><small>Dados fornecidos pela CoinGecko</small></div><div class="card"><h2>Controle do robô</h2><p id="status"></p><p id="conexao"></p><button style="background:#15803d" onclick="cmd('iniciar')">INICIAR ROBÔ</button><button style="background:#b91c1c" onclick="cmd('parar')">PARAR ROBÔ</button><button onclick="cmd('resetar')">REINICIAR SIMULAÇÃO</button><p><small>Compra virtual: R$ 100<br>Stop Loss: 2%<br>Take Profit: 3%<br>Taxa: 0,1% por ordem<br>Limite diário: 2%<br>Estratégia experimental de tendência.</small></p></div><div class="card"><h2>Posições abertas</h2><p id="posicoes"></p></div><div class="card"><h2>Histórico de operações</h2><pre id="historico"></pre></div><div class="card"><small>Dados salvos no Supabase. O robô só opera enquanto o servidor estiver ativo. Parar suspende também as saídas automáticas. Stop Loss não garante preço de saída.</small></div><script>
const el=id=>document.getElementById(id), txt=(id,v)=>el(id).textContent=v, br=v=>Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});let busy=false;
async function atualizar(){if(busy)return;busy=true;try{const r=await fetch('/estado',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();txt('saldo',br(s.patrimonio));txt('lucro',br(s.patrimonio-1000));txt('pct',((s.patrimonio/1000-1)*100).toFixed(2)+'%');txt('caixa',br(s.caixa));txt('total',s.total);txt('status',s.bloqueado?'Limite diário atingido':s.ativo?'Robô ativo':'Robô parado');txt('conexao',s.status);for(const m of ['BTC','ETH','SOL'])txt(m,m+': '+(s.precos[m]?br(s.precos[m]):'Indisponível'));txt('hora',s.ultimo?'Atualizado: '+new Date(s.ultimo*1000).toLocaleString('pt-BR'):'Sem cotação');txt('posicoes',Object.entries(s.pos).map(([m,p])=>m+' | '+br(p.qtd*(s.precos[m]||p.entrada))).join(' • ')||'Nenhuma posição');txt('historico',s.historico.join('\n\n')||'Nenhuma operação');const c=el('grafico'),x=c.getContext('2d'),a=s.curva,lo=Math.min(...a)-1,hi=Math.max(...a)+1;x.clearRect(0,0,600,200);x.strokeStyle='#333';for(let i=0;i<5;i++){x.beginPath();x.moveTo(0,i*49);x.lineTo(600,i*49);x.stroke()}x.strokeStyle=s.patrimonio>=1000?'#39dc80':'#ff3535';x.lineWidth=3;x.beginPath();a.forEach((v,i)=>{let xx=i/Math.max(1,a.length-1)*600,y=190-(v-lo)/(hi-lo)*180;i?x.lineTo(xx,y):x.moveTo(xx,y)});if(a.length===1)x.lineTo(600,100);x.stroke();}catch(e){txt('conexao','Falha de conexão com servidor ou banco')}finally{busy=false}}
async function cmd(a){if(a==='resetar'&&!confirm('Apagar a simulação virtual?'))return;try{let r=await fetch('/controle/'+a,{method:'POST',headers:{'X-Xvitor':'1'}});if(!r.ok){let d=await r.json();throw Error(d.erro||'Falha')}await atualizar()}catch(e){alert(e.message)}}atualizar();setInterval(atualizar,15000);
</script></html>'''

# Execute com um único processo Gunicorn, sem --preload.
threading.Thread(target=ciclo,daemon=True).start()
if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','8000')),use_reloader=False)
    
