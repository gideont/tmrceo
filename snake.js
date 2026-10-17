'use strict';
(() => {
const $ = id => document.getElementById(id);
$('year').textContent = new Date().getFullYear();
const canvas = $('board'), ctx = canvas.getContext('2d'), N = 20, cell = canvas.width / N;
const vectors = [[0,-1],[1,0],[0,1],[-1,0]];
let snake, food, direction, queue, score=0, best=0, state='ready', timer=null, sound=false, audio;
let randomState=null, currentRun=null, moves='', starting=false;
let snakeColour='#779462';
try { const saved=localStorage.getItem('tmrceo-snake-colour'); if(saved==='rainbow'||/^#[0-9a-f]{6}$/i.test(saved||''))snakeColour=saved; } catch {}
function tickDelay(){return Math.ceil(45+90/(1+0.18*(score/10)));}
function updateSpeed(){$('snake-speed').textContent=(135/tickDelay()).toFixed(1)+'×';}
function random(){if(randomState===null)return Math.random();randomState=(Math.imul(randomState,1664525)+1013904223)>>>0;return randomState/4294967296;}
try { best = Math.max(0, Number(localStorage.getItem('tmrceo-snake-best')) || 0); } catch {}
$('best').textContent = String(best).padStart(3,'0');
function apple() { const empty=[]; for(let y=0;y<N;y++) for(let x=0;x<N;x++) if(!snake.some(s=>s.x===x&&s.y===y)) empty.push({x,y}); food=empty.length ? empty[Math.floor(random()*empty.length)] : null; }
function reset(seed=null) { randomState=seed;moves='';snake=[{x:8,y:10},{x:7,y:10},{x:6,y:10}]; direction=1;queue=[];score=0;$('score').textContent='000';updateSpeed();apple();draw(); }
// Paint at 200 × 200 and scale with nearest-neighbour pixels: no rounded sprites.
function shade(hex, amount){return '#'+[1,3,5].map(at=>Math.round(Math.max(0,Math.min(255,parseInt(hex.slice(at,at+2),16)+amount))).toString(16).padStart(2,'0')).join('');}
function draw() {
 ctx.imageSmoothingEnabled=false;
 for(let y=0;y<N;y++)for(let x=0;x<N;x++){
  ctx.fillStyle=(x+y)%2?'#e2ead5':'#dce6cd';ctx.fillRect(x*cell,y*cell,cell,cell);
  if((x*7+y*11)%9===0){ctx.fillStyle='#d2dfc0';ctx.fillRect(x*cell+3,y*cell+6,2,1);}
 }
 if(food){const x=food.x*cell,y=food.y*cell;
  ctx.fillStyle='#bd466b';ctx.fillRect(x,y+3,2,4);ctx.fillRect(x+8,y+3,2,4);
  ctx.fillStyle='#e986a3';ctx.fillRect(x+2,y+1,6,8);
  ctx.fillStyle='#fff5d6';ctx.fillRect(x+4,y+1,2,7);
  ctx.fillStyle='#ac385d';ctx.fillRect(x+2,y+8,6,1);
 }
 snake.slice().reverse().forEach((part,i)=>{
  const x=part.x*cell,y=part.y*cell;
  const rainbow=['#dc6868','#dc9942','#c1ac32','#65a259','#428fc6','#9371c2'];
  const colour=snakeColour==='rainbow'?rainbow[(snake.length-1-i)%rainbow.length]:snakeColour;
  ctx.fillStyle=shade(colour,-52);ctx.fillRect(x,y,cell,cell);
  ctx.fillStyle=colour;ctx.fillRect(x+1,y+1,cell-2,cell-2);
  ctx.fillStyle=shade(colour,35);ctx.fillRect(x+1,y+1,cell-2,1);ctx.fillRect(x+1,y+2,1,3);
  ctx.fillStyle=shade(colour,-22);ctx.fillRect(x+3,y+6,2,1);ctx.fillRect(x+7,y+4,1,2);
 });
 const head=snake[0],v=vectors[direction],side=[-v[1],v[0]];
 for(const sign of [-1,1]){
  const x=head.x*cell+4+v[0]*2+side[0]*sign*2,y=head.y*cell+4+v[1]*2+side[1]*sign*2;
  ctx.fillStyle='#26372e';ctx.fillRect(x-1,y-1,4,4);
  ctx.fillStyle='#fffdf0';ctx.fillRect(x,y,2,2);
  ctx.fillStyle='#26372e';ctx.fillRect(x+(v[0]>0?1:0),y+(v[1]>0?1:0),1,1);
 }
}
function syncColours(){
 document.querySelectorAll('[data-snake-colour]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.snakeColour===snakeColour)));
 if(snakeColour!=='rainbow')$('snake-colour').value=snakeColour;
}
function chooseColour(colour){
 snakeColour=colour;syncColours();draw();
 try{localStorage.setItem('tmrceo-snake-colour',colour);}catch{}
}
document.querySelectorAll('[data-snake-colour]').forEach(button=>button.addEventListener('click',()=>{chooseColour(button.dataset.snakeColour);if(state==='playing')canvas.focus({preventScroll:true});}));
$('snake-colour').addEventListener('input',event=>chooseColour(event.target.value));
syncColours();
function beep(){if(!sound)return;try{audio ||= new (window.AudioContext||window.webkitAudioContext)();audio.resume();const osc=audio.createOscillator(),gain=audio.createGain();osc.type='sine';osc.frequency.setValueAtTime(660,audio.currentTime);gain.gain.setValueAtTime(.045,audio.currentTime);gain.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.12);osc.connect(gain);gain.connect(audio.destination);osc.start();osc.stop(audio.currentTime+.12);}catch{}}
// Synthesized applause uses no downloaded audio and follows the sound toggle.
let applauseNodes=[],applauseVersion=0;
function stopApplause(){applauseVersion++;for(const node of applauseNodes){try{node.stop();}catch{}}applauseNodes=[];}
async function applaud(rank){
 stopApplause();if(!sound)return;const version=applauseVersion;
 try{
  audio ||= new (window.AudioContext||window.webkitAudioContext)();
  await audio.resume();if(version!==applauseVersion||!sound||document.hidden)return;
  const start=audio.currentTime+.03,champion=rank===1;
  const noise=audio.createBuffer(1,Math.ceil(audio.sampleRate*.11),audio.sampleRate),data=noise.getChannelData(0);
  for(let i=0;i<data.length;i++)data[i]=Math.random()*2-1;
  for(let i=0;i<(champion?36:14);i++){
   const at=start+i*(champion ? 0.065 : 0.075)+Math.random()*.035;
   const clap=audio.createBufferSource(),filter=audio.createBiquadFilter(),gain=audio.createGain();
   clap.buffer=noise;filter.type='bandpass';filter.frequency.value=850+Math.random()*1300;filter.Q.value=.65;
   gain.gain.setValueAtTime(.001,at);gain.gain.linearRampToValueAtTime(.14,at+.004);gain.gain.exponentialRampToValueAtTime(.001,at+.10);
   clap.connect(filter);filter.connect(gain);gain.connect(audio.destination);clap.start(at);clap.stop(at+.11);applauseNodes.push(clap);
  }
  const notes=champion?[523.25,659.25,783.99,1046.5,783.99,1046.5]:[659.25,783.99,1046.5];
  notes.forEach((frequency,i)=>{
   const at=start+i*.14,tone=audio.createOscillator(),gain=audio.createGain();tone.type='triangle';tone.frequency.value=frequency;
   gain.gain.setValueAtTime(.001,at);gain.gain.linearRampToValueAtTime(.045,at+.015);gain.gain.exponentialRampToValueAtTime(.001,at+.28);
   tone.connect(gain);gain.connect(audio.destination);tone.start(at);tone.stop(at+.3);applauseNodes.push(tone);
  });
 }catch{/* Visual congratulations still work when audio is unavailable. */}
}
document.addEventListener('snake:celebrate',event=>applaud(event.detail.rank));
document.addEventListener('snake:celebration-stop',stopApplause);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopApplause();});
function stop(){clearTimeout(timer);timer=null;}
function scheduleTick(){timer=setTimeout(()=>{timer=null;tick();if(state==='playing')scheduleTick();},tickDelay());}
function run(){stop();scheduleTick();}
function show(title,copy,button,tip){$('overlay-title').textContent=title;$('overlay-copy').textContent=copy;$('start').textContent=button;$('overlay-tip').textContent=tip;$('overlay').hidden=false;}
function end(won=false){state='over';stop();$('pause').disabled=true;if(score>best){best=score;try{localStorage.setItem('tmrceo-snake-best',String(best));}catch{}$('best').textContent=String(best).padStart(3,'0');}show(won?'You grew all the way!':'That’s a wrap!',`You scored ${score}. Your best is ${best}.`, 'Play again →','A fresh start is always a good idea.');$('game-status').textContent=`Game over. Score ${score}. Best score ${best}.`;window.tmrceoArcade?.gameOver(currentRun,moves);}
function tick(){if(state!=='playing')return;if(queue.length)direction=queue.shift();moves+=String(direction);const v=vectors[direction],head={x:snake[0].x+v[0],y:snake[0].y+v[1]},eat=food&&head.x===food.x&&head.y===food.y;const body=eat?snake:snake.slice(0,-1);if(head.x<0||head.y<0||head.x>=N||head.y>=N||body.some(s=>s.x===head.x&&s.y===head.y)){end();return;}snake.unshift(head);if(eat){score+=10;$('score').textContent=String(score).padStart(3,'0');updateSpeed();$('game-status').textContent=`Candy! Score ${score}. Speed ${(135/tickDelay()).toFixed(1)} times.`;beep();apple();}else snake.pop();draw();if(!food)end(true);}
function turn(next){if(state!=='playing')return;const last=queue.length?queue[queue.length-1]:direction;if(next!==last&&next!==(last+2)%4&&queue.length<2)queue.push(next);}
function pause(){if(state==='playing'){state='paused';stop();show('A tiny pause.','Your candy isn’t going anywhere.','Keep playing →','Press Space or P to resume.');$('pause').textContent='Resume ▶';$('game-status').textContent='Game paused.';}else if(state==='paused'){state='playing';$('overlay').hidden=true;$('pause').textContent='Pause Ⅱ';run();}}
$('start').addEventListener('click',async()=>{
 if(starting)return;
 if(state==='paused'){pause();canvas.focus({preventScroll:true});return;}
 starting=true;$('start').disabled=true;
 try{currentRun=await window.tmrceoArcade?.startRun()||null;reset(currentRun?.seed??null);state='playing';$('overlay').hidden=true;$('pause').disabled=false;$('pause').textContent='Pause Ⅱ';$('game-status').textContent='Game started.';run();canvas.focus({preventScroll:true});}
 finally{starting=false;$('start').disabled=false;}
});
$('pause').addEventListener('click',pause);
$('sound').addEventListener('click',()=>{sound=!sound;if(!sound)stopApplause();$('sound').textContent=sound?'Sound on ♪':'Sound off ♪';$('sound').setAttribute('aria-pressed',String(sound));$('sound').setAttribute('aria-label',sound?'Turn game sound off':'Turn game sound on');if(sound)beep();});
const keys={ArrowUp:0,w:0,W:0,ArrowRight:1,d:1,D:1,ArrowDown:2,s:2,S:2,ArrowLeft:3,a:3,A:3};
document.addEventListener('keydown',event=>{if(event.target.closest('dialog[open],input,textarea,select,button,a'))return;if(state!=='playing'&&state!=='paused')return;if(event.key in keys){event.preventDefault();turn(keys[event.key]);}else if([' ','p','P'].includes(event.key)){event.preventDefault();pause();}});
// Return focus to the board so arrows work immediately after starting with a button.
canvas.tabIndex=0;canvas.setAttribute('aria-label','Snake game. Arrow keys or W A S D to move. Space or P to pause.');
document.addEventListener('snake:name-edit',()=>{if(state==='playing')pause();});
document.addEventListener('tmrceo:auth-change',event=>{if(state==='playing')pause();if(event.detail.action==='logout')currentRun=null;});
document.querySelectorAll('[data-dir]').forEach(button=>button.addEventListener('pointerdown',event=>{event.preventDefault();turn(Number(button.dataset.dir));}));
let touch=null;canvas.addEventListener('pointerdown',event=>{touch={x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);});canvas.addEventListener('pointerup',event=>{if(!touch)return;const dx=event.clientX-touch.x,dy=event.clientY-touch.y;touch=null;if(Math.max(Math.abs(dx),Math.abs(dy))<12)return;turn(Math.abs(dx)>Math.abs(dy)?(dx>0?1:3):(dy>0?2:0));});canvas.addEventListener('pointercancel',()=>touch=null);
document.addEventListener('visibilitychange',()=>{if(document.hidden&&state==='playing')pause();});
window.addEventListener('blur',()=>{if(state==='playing')pause();});
reset();
$('newsletter').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget,button=form.querySelector('button'),status=$('newsletter-status');button.disabled=true;status.textContent='Saving your spot…';try{const response=await fetch('/api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:form.email.value,consent:form.consent.checked,website:form.website.value})});const data=await response.json();if(!response.ok)throw Error(data.error||'Please try again in a moment.');if(data.unsubscribe){try{localStorage.setItem('tmrceo-unsubscribe',data.unsubscribe);}catch{}}status.textContent='You’re on the list. Thanks for cheering us on!';form.reset();}catch(error){status.textContent=error.message||'Couldn’t connect. Please try again.';}finally{button.disabled=false;}});
})();

// Discovery suggestions are kept private until the family newsroom reviews them.
const discoveryForm = document.getElementById('discovery-form');
if (discoveryForm) discoveryForm.addEventListener('submit', async event => {
 event.preventDefault();
 const form=event.currentTarget, button=form.querySelector('button'), status=document.getElementById('discovery-status');
 button.disabled=true; status.textContent='Sending your discovery…';
 try {
  const payload=Object.fromEntries(new FormData(form));payload.consent=form.consent.checked;
  const response=await fetch('/api/discoveries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Please try again.');
  status.textContent='Thank you! Your discovery is in our review pile. It hasn’t been published yet.';form.reset();
 } catch(error) {status.textContent=error.message||'Couldn’t connect. Please try again.';} finally {button.disabled=false;}
});

function openDiscoveryForm() {
 const panel=document.getElementById('share-discovery');
 if(panel && location.hash==='#share-discovery') panel.open=true;
}
window.addEventListener('hashchange',openDiscoveryForm);
openDiscoveryForm();
document.querySelectorAll('a[href="#share-discovery"]').forEach(link=>link.addEventListener('click',()=>{document.getElementById('share-discovery').open=true;}));
