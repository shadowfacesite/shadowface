# -*- coding: utf-8 -*-
"""Генерирует проходимый лабиринт и собирает vault.example.html с 3D-игрой."""
import random, json
from collections import deque

SEED = 3
random.seed(SEED)

Wc, Hc = 9, 7                      # ячеек по ширине/высоте
W, H = 2 * Wc + 1, 2 * Hc + 1
grid = [['#'] * W for _ in range(H)]

def carve(cx, cy):
    grid[2 * cy + 1][2 * cx + 1] = '.'
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    random.shuffle(dirs)
    for dx, dy in dirs:
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < Wc and 0 <= ny < Hc and grid[2 * ny + 1][2 * nx + 1] == '#':
            grid[2 * cy + 1 + dy][2 * cx + 1 + dx] = '.'
            carve(nx, ny)

carve(0, 0)

start = (1, 1)
exit_tile = (2 * (Wc - 1) + 1, 2 * (Hc - 1) + 1)

# BFS: путь от старта к выходу
def bfs(src, dst):
    q = deque([src]); prev = {src: None}
    while q:
        x, y = q.popleft()
        if (x, y) == dst: break
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < W and 0 <= ny < H and grid[ny][nx] == '.' and (nx,ny) not in prev:
                prev[(nx,ny)] = (x,y); q.append((nx,ny))
    path = []; cur = dst
    while cur is not None:
        path.append(cur); cur = prev[cur]
    return path[::-1]

path = bfs(start, exit_tile)
assert path[0] == start and path[-1] == exit_tile, "лабиринт непроходим!"

# Триггеры на пути (без старта и выхода), 4 штуки
types = ["camera", "mic", "geo", "notify"]
fracs = [0.20, 0.42, 0.64, 0.84]
triggers = []
for t, f in zip(types, fracs):
    idx = max(1, min(len(path) - 2, int(len(path) * f)))
    x, y = path[idx]
    triggers.append({"x": x + 0.5, "y": y + 0.5, "type": t})

# Начальный угол — в сторону открытого соседа
sx, sy = start
if grid[sy][sx + 1] == '.': ang = 0.0
elif grid[sy + 1][sx] == '.': ang = 1.5708
elif grid[sy][sx - 1] == '.': ang = 3.14159
else: ang = -1.5708

start_dist = ((exit_tile[0] - sx) ** 2 + (exit_tile[1] - sy) ** 2) ** 0.5

# --- визуальная проверка в консоль ---
vis = [row[:] for row in grid]
vis[sy][sx] = 'S'
vis[exit_tile[1]][exit_tile[0]] = 'E'
for i, t in enumerate(triggers):
    vis[int(t["y"])][int(t["x"])] = str(i + 1)
print("Лабиринт %dx%d, путь %d клеток, триггеров %d:" % (W, H, len(path), len(triggers)))
print("\n".join("".join(r) for r in vis))

MAP = ["".join(r) for r in grid]

# ---------------------------------------------------------------- шаблон игры
TPL = r'''<!DOCTYPE html>
<!--
  ЗАКРЫТАЯ СТРАНИЦА — 3D-лабиринт (стиль Doom), открывается после входа.

  ССЫЛКА НА ВЫХОДЕ: задай секрет VAULT_VIDEO, либо впиши прямо сюда,
  в кавычки EXIT_URL ниже.

  Разрешения (камера/микрофон/гео/уведомления) встроены в сюжет и служат
  ТОЛЬКО ДЛЯ ИСПУГА. Ничего не записывается и не отправляется — политика
  сайта (connect-src 'self') это запрещает. Всё живёт в браузере зрителя.
-->
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>—</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  html,body{height:100%;background:#000;overflow:hidden;
    font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;color:#c9c9c9;}
  #view{display:block;width:100vw;height:100svh;background:#000;image-rendering:pixelated;cursor:crosshair;}

  .layer{position:fixed;inset:0;pointer-events:none;}
  #whisper{position:fixed;left:0;right:0;bottom:16%;text-align:center;
    font-size:clamp(14px,3.4vw,20px);letter-spacing:.12em;color:#e8e8e8;
    text-shadow:0 0 12px #000,0 0 26px rgba(176,20,20,.7);padding:0 20px;}
  #whisper.red{color:#e66;}

  #cam{position:fixed;right:12px;bottom:12px;width:120px;height:90px;
    object-fit:cover;filter:grayscale(1) contrast(1.3) brightness(.7);
    border:1px solid rgba(176,20,20,.5);display:none;opacity:.75;
    animation:flick 3s steps(2) infinite;z-index:4;}
  @keyframes flick{0%,100%{opacity:.7;}50%{opacity:.85;}}

  /* интро / финал */
  .screen{position:fixed;inset:0;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:22px;text-align:center;
    background:#000;padding:24px;z-index:6;}
  .screen h1{font-size:clamp(20px,5vw,30px);letter-spacing:.24em;text-transform:uppercase;font-weight:600;}
  .screen p{font-size:13px;letter-spacing:.1em;color:#8a8a8a;line-height:1.8;max-width:520px;}
  .screen .kbd{color:#c9c9c9;}
  .btn{display:inline-block;padding:16px 34px;cursor:pointer;color:#c9c9c9;text-decoration:none;
    background:#0a0a0a;border:1px solid rgba(176,20,20,.5);border-radius:3px;
    font-family:inherit;font-size:13px;letter-spacing:.22em;text-transform:uppercase;
    animation:glow 2s ease-in-out infinite;}
  @keyframes glow{0%,100%{box-shadow:0 0 0 rgba(176,20,20,0);}50%{box-shadow:0 0 24px rgba(176,20,20,.5);}}
  .btn:hover{color:#fff;}
  #end{display:none;}

  /* сенсорные кнопки */
  #pad{position:fixed;left:0;right:0;bottom:0;display:none;justify-content:center;gap:12px;
    padding:14px;z-index:5;}
  #pad button{width:74px;height:60px;background:rgba(10,10,10,.6);color:#c9c9c9;
    border:1px solid rgba(255,255,255,.12);border-radius:6px;font-size:22px;
    -webkit-user-select:none;user-select:none;touch-action:none;}
  @media (pointer:coarse){ #pad{display:flex;} }
</style>
</head>
<body>
  <canvas id="view"></canvas>
  <img id="cam" alt="">
  <div id="whisper" class="layer"></div>

  <div id="pad">
    <button data-k="left">◄</button>
    <button data-k="fwd">▲</button>
    <button data-k="back">▼</button>
    <button data-k="right">►</button>
  </div>

  <div class="screen" id="intro">
    <h1>Ты внутри</h1>
    <p>__TEXT__</p>
    <p>найди выход.<br><span class="kbd">W A S D</span> или стрелки — идти и поворачивать.<br>на телефоне — кнопки снизу.</p>
    <button class="btn" id="startBtn">войти в лабиринт</button>
  </div>

  <div class="screen" id="end">
    <h1>Выход</h1>
    <p>ты дошёл. но выход — это только начало.</p>
    <a class="btn" id="exitBtn" target="_blank" rel="noopener noreferrer">открыть</a>
  </div>

<script>
/* ============ данные лабиринта (сгенерированы заранее) ============ */
const MAP = __MAP__;
const W = MAP[0].length, H = MAP.length;
let px = __SX__, py = __SY__;
let ang = __ANG__;
let dirX = Math.cos(ang), dirY = Math.sin(ang);
const FOV = 0.66;
let planeX = -dirY * FOV, planeY = dirX * FOV;
const EXIT = {x: __EX__, y: __EY__};
const START_DIST = __SDIST__;
const TRIGGERS = __TRIGGERS__.map(t => Object.assign({fired:false}, t));

/* ссылка выхода: секрет VAULT_VIDEO или впиши вручную */
let EXIT_URL = "";
const FROM_SECRET = "__VIDEO_URL__";
if (FROM_SECRET && FROM_SECRET.indexOf("{{") !== 0) EXIT_URL = FROM_SECRET;

/* ============ канвас ============ */
const cv = document.getElementById('view');
const ctx = cv.getContext('2d', {alpha:false});
let CW, CH;
function resize(){
  CW = cv.width  = Math.min(900, Math.floor(cv.clientWidth));
  CH = cv.height = Math.floor(cv.clientHeight * (CW / cv.clientWidth));
}
addEventListener('resize', resize);

/* ============ карта ============ */
function cell(x,y){ if(x<0||y<0||x>=W||y>=H) return '#'; return MAP[y|0][x|0]; }
function wall(x,y){ return cell(x,y) === '#'; }
function canGo(x,y){ const r=0.22;
  return !wall(x-r,y-r)&&!wall(x+r,y-r)&&!wall(x-r,y+r)&&!wall(x+r,y+r); }
function move(dx,dy){ if(canGo(px+dx,py)) px+=dx; if(canGo(px,py+dy)) py+=dy; }
function rot(a){ const c=Math.cos(a),s=Math.sin(a);
  let x=dirX*c-dirY*s, y=dirX*s+dirY*c; dirX=x; dirY=y;
  let px2=planeX*c-planeY*s, py2=planeX*s+planeY*c; planeX=px2; planeY=py2; }

/* ============ ввод ============ */
const K = {fwd:false,back:false,left:false,right:false};
const map = {KeyW:'fwd',ArrowUp:'fwd',KeyS:'back',ArrowDown:'back',
             KeyA:'left',ArrowLeft:'left',KeyD:'right',ArrowRight:'right'};
addEventListener('keydown', e=>{ if(map[e.code]){K[map[e.code]]=true; e.preventDefault();} });
addEventListener('keyup',   e=>{ if(map[e.code]){K[map[e.code]]=false;} });
document.querySelectorAll('#pad button').forEach(b=>{
  const k=b.dataset.k;
  const on =e=>{e.preventDefault();K[k]=true;};
  const off=e=>{e.preventDefault();K[k]=false;};
  b.addEventListener('pointerdown',on); b.addEventListener('pointerup',off);
  b.addEventListener('pointerleave',off); b.addEventListener('pointercancel',off);
});
/* мышь (если браузер даст захват) */
cv.addEventListener('click', ()=>{ if(cv.requestPointerLock) cv.requestPointerLock(); });
addEventListener('mousemove', e=>{ if(document.pointerLockElement===cv) rot(e.movementX*0.0025); });

/* ============ рендер ============ */
const STEP = 2;
function render(){
  ctx.fillStyle='#000'; ctx.fillRect(0,0,CW,CH/2);
  ctx.fillStyle='#080808'; ctx.fillRect(0,CH/2,CW,CH/2);
  for(let x=0; x<CW; x+=STEP){
    const camX = 2*x/CW - 1;
    const rdx = dirX + planeX*camX, rdy = dirY + planeY*camX;
    let mx = px|0, my = py|0;
    const ddx = Math.abs(1/rdx), ddy = Math.abs(1/rdy);
    let sx, sy, stepX, stepY;
    if(rdx<0){stepX=-1; sx=(px-mx)*ddx;} else {stepX=1; sx=(mx+1-px)*ddx;}
    if(rdy<0){stepY=-1; sy=(py-my)*ddy;} else {stepY=1; sy=(my+1-py)*ddy;}
    let side=0, guard=0;
    while(guard++<64){
      if(sx<sy){ sx+=ddx; mx+=stepX; side=0; } else { sy+=ddy; my+=stepY; side=1; }
      if(cell(mx,my)==='#') break;
    }
    let dist = side===0 ? (sx-ddx) : (sy-ddy);
    if(dist<0.0001) dist=0.0001;
    const lh = CH/dist;
    const y0 = (CH-lh)/2;
    let sh = Math.max(0, 1 - dist/11);
    let c = Math.floor(sh*255);
    if(side===1) c = Math.floor(c*0.6);
    ctx.fillStyle = 'rgb('+c+','+c+','+c+')';
    ctx.fillRect(x, y0, STEP, lh);
  }
  vignette();
}

/* ============ нагнетание ============ */
let dread = 0;
function updateDread(){
  const d = Math.hypot(EXIT.x-px, EXIT.y-py);
  const t = 1 - Math.min(1, d/START_DIST);
  dread += (t - dread) * 0.04;
}
let shake = 0;
function vignette(){
  let ox=0, oy=0;
  if(shake>0){ ox=(Math.random()-0.5)*shake*14; oy=(Math.random()-0.5)*shake*14; shake*=0.9; }
  const r0 = CH*(0.62 - 0.46*dread);
  const r1 = CH*0.8;
  const g = ctx.createRadialGradient(CW/2+ox, CH/2+oy, Math.max(1,r0), CW/2+ox, CH/2+oy, r1);
  g.addColorStop(0,'rgba(0,0,0,0)');
  g.addColorStop(1,'rgba(0,0,0,'+(0.55+0.45*dread).toFixed(3)+')');
  ctx.fillStyle=g; ctx.fillRect(0,0,CW,CH);
}

/* ============ звук: сердце + гул ============ */
let actx=null;
function initAudio(){
  try{
    actx = new (window.AudioContext||window.webkitAudioContext)();
    const g = actx.createGain(); g.gain.value=0; g.connect(actx.destination);
    [55,55.4,82.5].forEach(f=>{const o=actx.createOscillator();o.type='sine';o.frequency.value=f;o.connect(g);o.start();});
    g.gain.linearRampToValueAtTime(0.025, actx.currentTime+4);
  }catch(e){}
}
function thump(){
  if(!actx) return;
  const o=actx.createOscillator(), g=actx.createGain();
  o.type='sine'; o.frequency.setValueAtTime(90, actx.currentTime);
  o.frequency.exponentialRampToValueAtTime(38, actx.currentTime+0.14);
  g.gain.setValueAtTime(0.0001, actx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.5, actx.currentTime+0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime+0.3);
  o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime+0.32);
}
function heartbeat(){
  if(!running){ return; }
  thump(); setTimeout(thump, 190);
  const interval = 1150 - dread*760;
  setTimeout(heartbeat, Math.max(360, interval));
}

/* ============ сообщения ============ */
const wEl = document.getElementById('whisper');
let queue=[], busy=false;
function say(text, red){ return new Promise(res=>{ queue.push({text,red,res}); pump(); }); }
async function pump(){
  if(busy) return; busy=true;
  while(queue.length){
    const m=queue.shift();
    wEl.className = m.red ? 'layer red' : 'layer';
    wEl.textContent='';
    for(let i=0;i<m.text.length;i++){ wEl.textContent=m.text.slice(0,i+1); await sleep(30); }
    await sleep(1600); m.res&&m.res();
  }
  wEl.textContent=''; busy=false;
}
const sleep = ms => new Promise(r=>setTimeout(r,ms));

/* ============ триггеры-разрешения (только испуг) ============ */
async function fireTrigger(type){
  if(type==='camera'){
    await say('дай посмотреть на тебя.');
    try{
      const st = await navigator.mediaDevices.getUserMedia({video:true});
      const el=document.getElementById('cam'); el.srcObject=st; el.style.display='block';
      await say('вот, значит, ты какой.', true);
    }catch(e){ await say('спрятал лицо. я уже запомнил.', true); }
  }
  else if(type==='mic'){
    await say('тише. я слушаю.');
    try{
      const st = await navigator.mediaDevices.getUserMedia({audio:true});
      const ac = actx || new (window.AudioContext||window.webkitAudioContext)();
      const src = ac.createMediaStreamSource(st);
      const an = ac.createAnalyser(); an.fftSize=256; src.connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      (function loop(){ an.getByteFrequencyData(buf);
        let s=0; for(const v of buf) s+=v; const avg=s/buf.length;
        if(avg>55) shake=Math.min(1, avg/120);
        if(running) requestAnimationFrame(loop);
      })();
      await say('слышу, как ты дышишь.', true);
    }catch(e){ await say('молчишь. тишина не спрячет.', true); }
  }
  else if(type==='geo'){
    await say('а где ты на самом деле?');
    if(!navigator.geolocation){ await say('...и так найду.', true); return; }
    navigator.geolocation.getCurrentPosition(
      async p=>{ await say('ты здесь: '+p.coords.latitude.toFixed(3)+', '+p.coords.longitude.toFixed(3)+'. теперь навсегда.', true); },
      async ()=>{ await say('не хочешь говорить. найду сам.', true); },
      {timeout:8000});
  }
  else if(type==='notify'){
    await say('я позову, когда придёт время.');
    if(!('Notification' in window)){ return; }
    try{
      const p = await Notification.requestPermission();
      if(p==='granted'){ setTimeout(()=>{ try{ new Notification('не оборачивайся.'); }catch(e){} }, 9000);
        await say('хорошо.', true); }
      else { await say('всё равно услышишь.', true); }
    }catch(e){}
  }
}
function checkTriggers(){
  for(const t of TRIGGERS){
    if(!t.fired && Math.hypot(t.x-px, t.y-py) < 0.5){ t.fired=true; fireTrigger(t.type); }
  }
}

/* ============ цикл ============ */
let running=false, last=0;
function loop(ts){
  if(!running) return;
  const dt = Math.min(0.05, (ts-last)/1000 || 0.016); last=ts;
  const spd = 2.7*dt, r = 2.3*dt;
  if(K.fwd)  move(dirX*spd, dirY*spd);
  if(K.back) move(-dirX*spd, -dirY*spd);
  if(K.left) rot(-r);
  if(K.right) rot(r);
  updateDread(); checkTriggers(); render();
  if(Math.hypot(EXIT.x-px, EXIT.y-py) < 0.6){ finish(); return; }
  requestAnimationFrame(loop);
}

function finish(){
  running=false;
  const a=document.getElementById('exitBtn');
  if(EXIT_URL){ a.href=EXIT_URL; }
  else { a.removeAttribute('href'); a.textContent='ссылка не задана'; a.style.cursor='default'; }
  document.getElementById('end').style.display='flex';
}

document.getElementById('startBtn').addEventListener('click', function(){
  document.getElementById('intro').style.display='none';
  resize(); initAudio(); heartbeat();
  running=true; last=performance.now(); requestAnimationFrame(loop);
});

/* заголовок вкладки, если отвлёкся */
const rt=document.title;
document.addEventListener('visibilitychange', ()=>{
  document.title = document.hidden ? 'не оборачивайся.' : rt;
});
resize();
</script>
</body>
</html>
'''

out = (TPL
       .replace("__MAP__", json.dumps(MAP, ensure_ascii=False))
       .replace("__SX__", str(sx + 0.5))
       .replace("__SY__", str(sy + 0.5))
       .replace("__ANG__", "%.5f" % ang)
       .replace("__EX__", str(exit_tile[0] + 0.5))
       .replace("__EY__", str(exit_tile[1] + 0.5))
       .replace("__SDIST__", "%.4f" % start_dist)
       .replace("__TRIGGERS__", json.dumps(triggers, ensure_ascii=False))
       .replace("__TEXT__", "{{TEXT}}")
       .replace("__VIDEO_URL__", "{{VIDEO_URL}}"))

with open("/home/claude/site/vault.example.html", "w", encoding="utf-8") as f:
    f.write(out)
print("\nvault.example.html собран:", len(out), "байт")
