const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
let currentView='adventure', chosenLocation=1, locations=[], busy=false, timer, hero=null;
const titles={adventure:'Приключения',inventory:'Инвентарь',quests:'Задания',boss:'Мировой босс',community:'Гильдия и чат'};
async function api(path,body) {
  let response;
  try { response=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  catch { throw new Error('Нет связи с сервером. Обновите страницу: завершённый бой и награды сохраняются.'); }
  if(response.status===401){location.replace('/');throw new Error('Войдите в игру');}
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Проверьте введённые данные');
  return data;
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('toast').hidden=true,4000);}
function error(message){$('global-error').textContent=message;}
function disabled(){return busy||!hero||hero.in_battle;}
async function refreshHero(){
  hero=await api('/character');const h=hero;
  $('hero-summary').innerHTML=`<div class="hero-identity"><div class="avatar">✦</div><div><span class="eyebrow">ИСКАТЕЛЬ ПРИКЛЮЧЕНИЙ</span><h2>${esc(h.name)}</h2><span class="muted">Уровень ${h.level} · регенерация +${Math.round((h.level-1)*10)}%</span></div></div><div class="hero-xp"><div class="split"><span>До следующего уровня</span><b>${h.xp_in_level} / ${h.xp_next}</b></div><div class="progress"><i style="width:${100*h.xp_in_level/h.xp_next}%"></i></div><small>${h.xp} опыта · уровень ускоряет только восстановление</small></div><div class="hero-stats"><div><span>♡ Здоровье</span><b>${h.hp}<small> / ${h.max_hp}</small></b></div><div><span>⚔ Атака</span><b>${h.attack}</b></div><div><span>⬡ Защита</span><b>${h.defense}</b></div></div>`;
  $('recovery').innerHTML=`<div class="recovery-health"><div class="split"><b>${h.hp===0?'Вы повержены — отдыхайте или используйте зелье':'Состояние героя'}</b><span>${h.hp} / ${h.max_hp} HP</span></div><div class="progress"><i style="width:${100*h.hp/h.max_hp}%"></i></div><small>${h.in_battle?'В бою восстановление отключено':`Восстановление: ${h.regen_per_10s} HP / 10 сек (${h.regen_percent}%). Работает и вне игры.`} · Эликсиры: ${h.elixirs}</small></div><button class="secondary" data-heal ${disabled()||h.potions===0||h.hp>=h.max_hp?'disabled':''}>🧪 Лечение +30% · ${h.potions} шт.</button>`;
}
async function loadAdventure(){
  locations=await api('/locations');
  if(!locations.find(l=>l.id===chosenLocation)?.unlocked)chosenLocation=1;
  $('locations').innerHTML=locations.map((l,i)=>`<button class="location-card terrain-${i} ${chosenLocation===l.id?'selected':''}" data-location="${l.id}" ${!l.unlocked?'disabled':''}><div class="location-art"><span>${l.icon}</span></div><div class="location-info"><span class="tag">${l.cleared?'МИНИ-БОСС ПОБЕЖДЁН':l.unlocked?'ОТКРЫТО':'🔒 ПОБЕДИТЕ ПРЕДЫДУЩЕГО БОССА'}</span><h3>${esc(l.name)}</h3><p>${esc(l.description)}</p><small class="reward">Эликсиры ${l.elixirs}/5 · победы ${l.kills}</small></div></button>`).join('');
  renderMonsters();
}
function renderMonsters(){
  const l=locations.find(l=>l.id===chosenLocation);
  $('location-title').textContent=l.name+' · противники';
  $('monsters').innerHTML=l.monsters.map(m=>`<article class="monster-card ${m.is_miniboss?'mini-card':''}"><div class="monster-icon">${m.icon}</div>${m.is_miniboss?'<span class="eyebrow">МИНИ-БОСС ЛОКАЦИИ</span>':''}<h3>${esc(m.name)}</h3><div class="monster-stats"><span>♡ ${m.hp}</span><span>⚔ ${m.attack}</span><span>⬡ ${m.defense}</span></div>${m.is_miniboss?'':`<p class="loot-hint">Добыча 100%: ${esc(m.drop_name)} ★</p>`}<div class="split"><span class="reward">+${m.xp_reward} XP</span><button class="primary small" data-fight="${m.id}" ${disabled()||hero.hp<1||(m.is_miniboss&&l.cleared)?'disabled':''}>${m.is_miniboss&&l.cleared?'Побеждён ✓':'В бой →'}</button></div></article>`).join('');
}
async function loadInventory(){
  const items=await api('/inventory');
  $('consumables').innerHTML=`<div><h3>🧪 Зелья лечения · ${hero.potions} шт.</h3><p class="muted">Восстанавливают 30% максимального HP. Выпадают с шансом 15%. Используются только вне боя.</p><p class="reward">Эликсиры жизненной силы применяются при получении: +10 максимального HP. Всего применено ${hero.elixirs}.</p></div><button class="secondary" data-heal ${disabled()||hero.potions===0||hero.hp>=hero.max_hp?'disabled':''}>Использовать зелье</button>`;
  $('inventory').innerHTML=items.map(i=>`<article class="panel item ${i.equipped?'equipped':''}"><div class="split"><span class="item-icon">${i.icon}</span><span class="tag">${i.equipped?'НАДЕТО':i.slot==='weapon'?'ОРУЖИЕ':'ДОСПЕХ'}</span></div><h3>${esc(i.name)}</h3><div class="stars">${'★'.repeat(i.stars)}<span>${'☆'.repeat(5-i.stars)}</span></div><p class="muted">${i.attack?'+'+i.attack+' к атаке':'+'+i.defense+' к защите'} · Копий: <b>${i.quantity}</b></p><button class="${i.equipped?'secondary':'primary'} full" data-equip="${i.id}" data-enabled="${!i.equipped}" ${disabled()?'disabled':''}>${i.equipped?'Снять':'Надеть'}</button><button class="secondary full merge-button" data-merge="${i.id}" ${!i.can_merge||disabled()?'disabled':''}>${i.stars===5?'Максимум ★★★★★':`Объединить 3 → ${i.stars+1}★ (${i.quantity}/3)`}</button></article>`).join('');
}
async function loadQuests(){
  const qs=await api('/quests');
  $('quests').innerHTML=qs.map(q=>`<article class="panel quest"><div class="split"><span class="quest-symbol">▤</span><span class="tag">${q.claimed?'ВЫПОЛНЕНО':q.progress>=q.target?'НАГРАДА ЖДЁТ':'В ПРОЦЕССЕ'}</span></div><h2>${esc(q.title)}</h2><p class="muted">${esc(q.description)}</p><div class="split"><span>Прогресс</span><b>${q.progress} / ${q.target}</b></div><div class="progress"><i style="width:${100*q.progress/q.target}%"></i></div><p class="reward">+${q.xp_reward} XP</p><button class="primary full" data-claim="${q.id}" ${q.claimed||q.progress<q.target||disabled()?'disabled':''}>${q.claimed?'Награда получена ✓':'Забрать награду'}</button></article>`).join('');
}
async function loadBoss(){
  const b=await api('/boss');
  $('boss').innerHTML=`<section class="boss-banner"><div class="boss-portrait">${b.icon}</div><div class="boss-info"><span class="eyebrow">МИРОВОЙ БОСС</span><h2>${esc(b.name)}</h2><p>⚔ Атака ${b.attack}. Вы бьёте — выживший босс отвечает. Затем можно лечиться.</p><div class="split"><span>♡ Общее здоровье</span><b>${b.hp} / ${b.max_hp}</b></div><div class="progress boss-health"><i style="width:${100*b.hp/b.max_hp}%"></i></div><button class="primary" data-boss-attack ${b.hp===0||disabled()||hero.hp<1?'disabled':''}>${b.hp===0?'Повержен · смена босса через минуту':'⚔ Атаковать босса'}</button><small>Один обмен ударами за заход · здоровье сохраняется</small></div></section><section class="panel contributors"><h2>Вклад искателей</h2>${b.contributors.length?b.contributors.map((c,i)=>`<div class="ranking-row"><span class="rank">${i+1}</span><b>${esc(c.name)}</b><span>${c.damage} урона</span></div>`).join(''):'<p class="muted">Станьте первым, кто бросит вызов.</p>'}</section>`;
}
async function loadCommunity(){
  const [leaders,messages]=await Promise.all([api('/leaderboard'),api('/chat')]);
  $('leaderboard').innerHTML=leaders.map((h,i)=>`<div class="ranking-row ${h.is_me?'is-me':''}"><span class="rank">${String(i+1).padStart(2,'0')}</span><div><b>${esc(h.name)}${h.is_me?' · вы':''}</b><small>Уровень ${h.level}</small></div><span class="reward">${h.xp} XP</span></div>`).join('');
  const atBottom=$('messages').scrollHeight-$('messages').scrollTop-$('messages').clientHeight<60;
  $('messages').innerHTML=messages.length?messages.map(m=>`<article class="message"><div class="split"><b>${esc(m.name)}</b><time>${new Date(m.created_at).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}</time></div><p>${esc(m.text)}</p></article>`).join(''):'<div class="empty-chat">✦<p>Поздоровайтесь с гильдией!</p></div>';
  if(atBottom)$('messages').scrollTop=$('messages').scrollHeight;
}
const loaders={adventure:loadAdventure,inventory:loadInventory,quests:loadQuests,boss:loadBoss,community:loadCommunity};
async function switchView(view){
  if(busy)return;currentView=view;error('');window.scrollTo({top:0,behavior:'smooth'});
  document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!=='view-'+view);
  document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  $('breadcrumb').textContent=titles[view];
  try{await loaders[view]();}catch(e){error(e.message);}
}
function summary(r){
  return `<span class="eyebrow">${esc(r.enemy)}</span><h2 class="${r.final_hp===0?'error':'success'}">${esc(r.message)}</h2><p class="reward">+${r.xp} XP${r.level_up?' · Новый уровень '+r.level:''}</p>${r.drops.map(d=>`<p>${esc(d)}</p>`).join('')}<p class="muted">Здоровье после боя: ${r.final_hp} / ${r.final_max_hp}</p>`;
}
function battleBars(hp,enemy,r){
  $('combat-hero-hp').textContent=`${hp} / ${r.initial_max_hp} HP`;
  $('combat-enemy-hp').textContent=`${enemy} / ${r.enemy_max_hp} HP`;
  $('combat-hero-bar').style.width=(100*hp/r.initial_max_hp)+'%';
  $('combat-enemy-bar').style.width=(100*enemy/r.enemy_max_hp)+'%';
}
async function animateBattle(r){
  $('combat-overlay').hidden=false;document.body.classList.add('in-combat');
  $('combat-close').hidden=true;$('combat-outcome').hidden=true;
  $('combat-title').textContent=r.kind==='boss'?'Вызов мировому боссу':r.kind==='miniboss'?'Испытание локации':'Сражение';
  $('combat-label').textContent='АВТОМАТИЧЕСКИЙ БОЙ';
  $('combat-hero-name').textContent=r.hero_name;$('combat-enemy-name').textContent=r.enemy;
  $('combat-enemy-icon').textContent=r.enemy_icon;
  $('combat-caption').textContent='Противники готовятся…';
  ['hero','enemy'].forEach(side=>{
    $('fighter-'+side).classList.remove('striking','hit');
    $('damage-'+side).classList.remove('float');
    $('damage-'+side).textContent='';
  });
  battleBars(r.initial_hp,r.enemy_hp,r);
  const start=Date.parse(r.started_at);
  for(let i=0;i<r.frames.length;i++){
    const f=r.frames[i];
    const remaining=start+(i+1)*r.frame_seconds*1000-Date.now();
    if(remaining>0)await new Promise(resolve=>setTimeout(resolve,remaining));
    battleBars(f.hero_hp,f.enemy_hp,r);
    const target=f.actor==='hero'?'enemy':'hero';
    $('combat-caption').textContent=`${f.actor==='hero'?'Вы':r.enemy} наносит ${f.damage} урона`;
    if(remaining>0){
      const attacker=$('fighter-'+f.actor),defender=$('fighter-'+target),number=$('damage-'+target);
      attacker.classList.remove('striking');defender.classList.remove('hit');number.classList.remove('float');
      void attacker.offsetWidth;
      attacker.classList.add('striking');defender.classList.add('hit');number.textContent='−'+f.damage;number.classList.add('float');
    }
  }
  $('combat-caption').textContent='Бой завершён';
  battleBars(r.final_hp,r.frames[r.frames.length-1].enemy_hp,{...r,initial_max_hp:r.final_max_hp});
  $('combat-outcome').innerHTML=summary(r);$('combat-outcome').hidden=false;
  $('combat-close').hidden=false;$('combat-close').focus();
  $('battle-result').innerHTML=summary(r);
  await new Promise(resolve=>{$('combat-close').onclick=()=>{ $('combat-overlay').hidden=true;document.body.classList.remove('in-combat');resolve(); };});
}
async function action(callback){
  if(busy)return;busy=true;error('');
  document.querySelectorAll('[data-fight],[data-boss-attack],[data-heal],[data-merge],[data-equip]').forEach(b=>b.disabled=true);
  try{await callback();}catch(e){error(e.message);}
  finally{busy=false;try{await refreshHero();await loaders[currentView]();}catch(e){error(e.message);}}
}
async function runFight(path,body){
  const request={path,body:{...body,request_id:crypto.randomUUID()}};
  sessionStorage.setItem('pending-battle',JSON.stringify(request));
  const r=await api(request.path,request.body);
  sessionStorage.removeItem('pending-battle');await animateBattle(r);
}
document.addEventListener('click',event=>{
  const el=event.target.closest('button');if(!el||el.disabled)return;
  if(el.dataset.view)switchView(el.dataset.view);
  if(el.dataset.location&&!busy){chosenLocation=Number(el.dataset.location);loadAdventure().catch(e=>error(e.message));}
  if(el.dataset.fight)action(()=>runFight('/battles',{monster_id:Number(el.dataset.fight)}));
  if(el.hasAttribute('data-boss-attack'))action(()=>runFight('/boss/attack',{}));
  if(el.dataset.equip)action(async()=>toast((await api(`/inventory/${el.dataset.equip}/${el.dataset.enabled==='true'?'equip':'unequip'}`,{})).message));
  if(el.dataset.merge)action(async()=>toast((await api(`/inventory/${el.dataset.merge}/merge`,{})).message));
  if(el.hasAttribute('data-heal'))action(async()=>toast((await api('/character/heal',{})).message));
  if(el.dataset.claim)action(async()=>toast((await api(`/quests/${el.dataset.claim}/claim`,{})).message));
});
$('logout').onclick=async()=>{if(busy)return;try{await api('/auth/logout',{});sessionStorage.removeItem('pending-battle');location.href='/';}catch(e){error(e.message);}};
$('chat-form').onsubmit=event=>{event.preventDefault();const text=$('chat-text').value.trim();if(text)action(async()=>{await api('/chat',{text});$('chat-text').value='';});};
let polling=false;
setInterval(async()=>{
  if(document.hidden||busy||polling)return;polling=true;
  try{await refreshHero();if(!busy){if(currentView==='adventure')renderMonsters();else await loaders[currentView]();}}
  catch(e){error('Не удалось обновить данные: '+e.message);}finally{polling=false;}
},5000);
(async()=>{
  try{
    await refreshHero();await loadAdventure();
    const pending=sessionStorage.getItem('pending-battle');
    if(pending){
      const request=JSON.parse(pending);
      await action(async()=>{try{const r=await api(request.path,request.body);sessionStorage.removeItem('pending-battle');await animateBattle(r);}catch(e){sessionStorage.removeItem('pending-battle');throw e;}});
    }else{
      const history=await api('/battles');
      if(history.length){const r=history[0].result;$('battle-result').innerHTML=summary(r);if(hero.in_battle)await action(()=>animateBattle(r));}
    }
  }catch(e){error('Не удалось загрузить игру: '+e.message);}
})();
