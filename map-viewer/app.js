import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { WorldKit } from './world-kit.js';
import { floorAt, moveWithCollisions, blocked } from './navigation.js';
import { interiorMaps } from './maps/interiors.js';
import { cityMaps } from './maps/cities.js';
import { natureMaps } from './maps/nature.js';

const $ = id => document.getElementById(id);
const mapOrder = ['Academy','Asuria','BoilerRoom','CapitalCity','CuriousMansion','Deran','EagleTown','in-Academy','Library','Mine','NormalTown','Nymphen','Odanka','PEStorage','Port','PrimitiveTown','Restaurant','Sauna','ScienceRoom','SnowyTown','SpiralStair','Storage','Toilet','Underground','Village'];
const maps = [...interiorMaps, ...cityMaps, ...natureMaps].sort((a,b)=>mapOrder.indexOf(a.id)-mapOrder.indexOf(b.id));
const labels = {Idle:['대기','◇'],Walk:['걷기','↣'],Run:['달리기','↟'],Attack:['공격','⚔'],Defend:['방어','◈'],Victory:['승리','♧'],Lose:['패배','☾']};
const motionKeys = {KeyQ:'Attack',KeyF:'Defend',KeyV:'Victory',KeyL:'Lose',KeyX:'Idle'};
let renderer, scene, camera, world, avatar, model, mixer, action, entries = [], selectedMap, selectedCharacter;
let loadToken = 0, loaded = false, overrideMotion = null, runToggle = false, nearestInteraction = null;
let loadedAvatarSlug = null;
let yaw = Math.PI*.24, pitch = .42, distance = 6.2, view = 'follow', verticalSpeed = 0, lastTime = performance.now(), elapsed = 0;
let toastUntil = 0, minimapTime = 0, currentMotion = 'Idle';
const position = new THREE.Vector3(), keys = new Set(), joystick = {x:0,z:0,pointer:null};
const cameraTarget = new THREE.Vector3();
const loader = new GLTFLoader();
let dragging = null, pixelRatio = Math.min(devicePixelRatio, 1.6);

function showError(error) {
  loaded = false; $('loading').hidden = true; $('error').hidden = false;
  $('error-detail').textContent = error.message || String(error); console.error(error);
}
function toast(message, seconds = 4) {
  $('toast').textContent = message; $('toast').hidden = false; toastUntil = performance.now() + seconds*1000;
}
function clearInput() { keys.clear(); resetJoystick(); dragging=null; }
function dialogOpen() { return !!document.querySelector('dialog[open]'); }
function openDialog(id) { if(!loaded)return;clearInput(); $(id).showModal(); }
function saveSelection() {
  if (!selectedMap || !selectedCharacter) return;
  const url = new URL(location.href);url.searchParams.set('map',selectedMap.id);url.searchParams.set('character',selectedCharacter.name);
  history.replaceState(null,'',url);
  try { localStorage.setItem('little-world-selection',JSON.stringify({map:selectedMap.id,character:selectedCharacter.name})); } catch { /* optional persistence */ }
}
function disposeModel(object) {
  const geometries=new Set(),materials=new Set(),textures=new Set();
  object.traverse(child=>{if(!child.isMesh)return;geometries.add(child.geometry);for(const mat of Array.isArray(child.material)?child.material:[child.material]){materials.add(mat);for(const value of Object.values(mat))if(value?.isTexture)textures.add(value);}});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}
function setMotion(name, force = false) {
  if(!mixer)return;
  const clip = mixer._clips.find(clip=>clip.name===name);
  if(!clip)return;
  if(currentMotion===name && action && !force)return;
  const next=mixer.clipAction(clip), previous=action;
  const loop=['Idle','Walk','Run'].includes(name);
  next.reset().setLoop(loop?THREE.LoopRepeat:THREE.LoopOnce,loop?Infinity:1);
  next.clampWhenFinished=!loop; next.enabled=true;next.setEffectiveTimeScale(1).setEffectiveWeight(1).play();
  if(previous && previous!==next) { previous.fadeOut(.14);next.fadeIn(.14); }
  action=next;currentMotion=name;
  document.querySelectorAll('#action-buttons button').forEach(button=>{const on=button.dataset.motion===name;button.classList.toggle('active',on);button.setAttribute('aria-pressed',String(on));});
}
function triggerMotion(name) {
  if(!loaded || dialogOpen())return;
  overrideMotion = name==='Idle'?null:name;
  setMotion(name,true);
}
function resetPosition() {
  if(!world || !selectedMap)return;
  position.set(selectedMap.spawn[0],floorAt(world.surfaces,...selectedMap.spawn) ?? 0,selectedMap.spawn[1]);
  // A bad decorative overlap must never trap the traveler at their starting point.
  if(blocked(world.colliders,position.x,position.z,position.y)) {
    let found=false;
    for(let radius=.5;radius<8&&!found;radius+=.5)for(let i=0;i<24&&!found;i++){
      const x=selectedMap.spawn[0]+Math.cos(i*Math.PI/12)*radius,z=selectedMap.spawn[1]+Math.sin(i*Math.PI/12)*radius;
      const y=floorAt(world.surfaces,x,z);
      if(y!==null && Math.abs(x)<world.width/2-.3&&Math.abs(z)<world.depth/2-.3&&!blocked(world.colliders,x,z,y)) { position.set(x,y,z);found=true; }
    }
  }
  verticalSpeed=0;overrideMotion=null;
  if(avatar)avatar.position.copy(position);
  cameraTarget.copy(position).add(new THREE.Vector3(0,1,0));
  if(mixer)setMotion('Idle',true);
}
function updateTitles() {
  $('map-title').textContent=selectedMap.name;$('map-description').textContent=selectedMap.description;
  $('journey-title').textContent=`${selectedMap.name} · ${selectedCharacter.name}`;
  $('map-number').textContent=`${String(maps.indexOf(selectedMap)+1).padStart(2,'0')} OF ${maps.length}`;
  $('region-type').textContent=selectedMap.category;$('character-name').textContent=selectedCharacter.name;
  $('character-portrait').src=`portraits/${selectedCharacter.slug}.webp`;$('character-portrait').alt=selectedCharacter.name_ko;
  document.title=`${selectedMap.name} · ${selectedCharacter.name} | 작은 세계`;
  document.querySelectorAll('.map-choice').forEach(b=>{const on=b.dataset.map===selectedMap.id;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on));});
  document.querySelectorAll('.character-choice').forEach(b=>{const on=b.dataset.character===selectedCharacter.slug;b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on));});
}
async function select(map, character, changeMap=true, changeCharacter=true) {
  const token=++loadToken;loaded=false;clearInput();$('loading').hidden=false;$('error').hidden=true;
  $('loading-detail').textContent=`${map.name} · ${character.name}`;
  selectedMap=map;selectedCharacter=character;
  try {
    if(changeMap || !world) {
      if(world){scene.remove(world.root);world.dispose();}
      world=new WorldKit(map);map.build(world);world.optimize();scene.add(world.root);
      world.cameraColliders=world.colliders.filter(c=>c.camera!==false);
      scene.background=new THREE.Color(map.sky||'#9dbfca');
      scene.fog=new THREE.Fog(map.fog||map.sky||'#9dbfca',Math.max(map.width,map.depth)*.8,Math.max(map.width,map.depth)*2.2);
      const indoor=map.category==='실내'||map.category==='던전';
      scene.getObjectByName('ambient').intensity=indoor?2.0:2.35;
      const sun=scene.getObjectByName('sun');sun.intensity=indoor?1.5:2.25;
      const size=Math.max(map.width,map.depth);sun.shadow.camera.left=-size/2;sun.shadow.camera.right=size/2;sun.shadow.camera.top=size/2;sun.shadow.camera.bottom=-size/2;sun.shadow.camera.updateProjectionMatrix();
      sun.position.set(-size*.3,Math.max(18,size*.65),size*.3);
      yaw=Math.PI*.24;pitch=.42;distance=indoor?5.0:6.2;resetPosition();
    }
    if(changeCharacter || !avatar || loadedAvatarSlug!==character.slug) {
      const gltf=await loader.loadAsync(`../${character.glb}?revision=${encodeURIComponent(character.sha256 || character.revision)}`);
      if(token!==loadToken){disposeModel(gltf.scene);return;}
      if(avatar){scene.remove(avatar);mixer.stopAllAction();mixer.uncacheRoot(model);disposeModel(avatar);}
      avatar=new THREE.Group();model=gltf.scene;
      let firstMouth=null;model.traverse(object=>{
        if(object.isMesh){object.castShadow=true;object.receiveShadow=true;
          if(object.name.toLowerCase().startsWith('mouth_')){if(firstMouth===null)firstMouth=object.name;else if(object.name!==firstMouth)object.visible=false;}
        }
      });
      model.updateMatrixWorld(true);
      const bounds=new THREE.Box3().setFromObject(model),size=bounds.getSize(new THREE.Vector3());
      const scale=1.5/Math.max(size.y,.01),center=bounds.getCenter(new THREE.Vector3());
      model.scale.multiplyScalar(scale);model.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);
      avatar.add(model);avatar.position.copy(position);scene.add(avatar);
      loadedAvatarSlug=character.slug;
      mixer=new THREE.AnimationMixer(model);mixer._clips=gltf.animations;
      mixer.addEventListener('finished',event=>{
        if(event.action===action && overrideMotion!=='Lose') { overrideMotion=null;setMotion('Idle'); }
      });
      action=null;currentMotion='';overrideMotion=null;setMotion('Idle');
      $('action-buttons').replaceChildren();
      for(const name of ['Idle','Walk','Run','Attack','Defend','Victory','Lose']) {
        const button=document.createElement('button');button.dataset.motion=name;
        const strong=document.createElement('strong'),icon=document.createElement('span'),label=document.createElement('span');
        icon.className='motion-icon';icon.textContent=`${labels[name][1]} `;label.textContent=labels[name][0];strong.append(icon,label);
        const small=document.createElement('span');small.textContent=name;button.append(strong,small);
        button.disabled=!gltf.animations.some(clip=>clip.name===name);
        button.setAttribute('aria-label',`${labels[name][0]} ${name}`);button.addEventListener('click',()=>triggerMotion(name));$('action-buttons').append(button);
      }
      setMotion('Idle',true);
    }
    if(token!==loadToken)return;
    avatar.position.copy(position);avatar.visible=view!=='first';loaded=true;
    updateTitles();saveSelection();$('loading').hidden=true;
    // Allows repeatable end-to-end inspection without exposing implementation in the UI.
    window.mapExplorer={maps,characters:entries,get world(){return world;},get position(){return position.clone();},get motion(){return currentMotion;},get selected(){return {map:selectedMap.id,character:selectedCharacter.name};},get avatarSlug(){return loadedAvatarSlug;},get avatarHeight(){return new THREE.Box3().setFromObject(avatar).getSize(new THREE.Vector3()).y;},selectMap:async id=>select(maps.find(m=>m.id===id),selectedCharacter,true,false),selectCharacter:async name=>select(selectedMap,entries.find(c=>c.name===name),false,true),get renderer(){return renderer;}};
  } catch(error) { if(token===loadToken)showError(error); }
}
function buildPickers() {
  for(const map of maps) {
    const button=document.createElement('button');button.className='map-choice';button.dataset.map=map.id;button.dataset.category=map.category;
    const img=document.createElement('img');img.src=`references/${map.id}_thumb.webp`;img.alt=`${map.name} 참고 이미지`;img.loading='lazy';
    const names=document.createElement('span'),name=document.createElement('strong'),category=document.createElement('small');
    name.textContent=map.name;category.textContent=map.category;names.append(name,category);button.append(img,names);
    button.title=map.description;button.addEventListener('click',()=>{$('world-picker').close();select(map,selectedCharacter,true,false);});$('map-grid').append(button);
  }
  for(const entry of entries) {
    const button=document.createElement('button');button.className='character-choice';button.dataset.character=entry.slug;
    const img=document.createElement('img');img.src=`portraits/${entry.slug}.webp`;img.alt=entry.name_ko;img.loading='lazy';
    const name=document.createElement('strong'),korean=document.createElement('small');name.textContent=entry.name;korean.textContent=entry.name_ko;
    button.append(img,name,korean);button.addEventListener('click',()=>{$('character-picker').close();select(selectedMap,entry,false,true);});$('character-grid').append(button);
  }
}
let activeFilter='all';
function filterMaps() {
  const search=$('map-search').value.toLocaleLowerCase();let count=0;
  for(const button of $('map-grid').children){const map=maps.find(m=>m.id===button.dataset.map);const show=(activeFilter==='all'||map.category===activeFilter)&&`${map.name} ${map.id} ${map.description}`.toLocaleLowerCase().includes(search);button.hidden=!show;if(show)count++;}
  $('search-empty').hidden=count>0;
}
function setView(next) {
  if(next==='first'&&view!=='first')pitch=.03;
  if(next==='follow'&&view==='first')pitch=.42;
  view=next;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===next));
  if(avatar)avatar.visible=view!=='first';
  toast({follow:'3인칭 탐험 · 드래그로 회전, 휠로 거리 조절',first:'1인칭 탐험 · 드래그로 시선을 돌려 보세요',overview:'전체 맵 · 방향키와 조이스틱으로 계속 이동할 수 있어요'}[view],2.5);
}
function resetJoystick() {joystick.x=joystick.z=0;joystick.pointer=null;$('joystick-knob').style.transform='';$('joystick').setAttribute('aria-valuenow','0');}
function joystickMove(event) {
  const rect=$('joystick').getBoundingClientRect(),max=rect.width*.32;
  let x=event.clientX-(rect.left+rect.width/2),z=event.clientY-(rect.top+rect.height/2),length=Math.hypot(x,z);
  if(length>max){x*=max/length;z*=max/length;length=max;}
  joystick.x=x/max;joystick.z=z/max;$('joystick-knob').style.transform=`translate(${x}px,${z}px)`;$('joystick').setAttribute('aria-valuenow',String(Math.round(length/max*100)));
}
function interact() {
  if(!nearestInteraction)return;
  const p=nearestInteraction;
  toast(`${p.name} — ${p.text || '맵의 실제 입체 사물입니다.'}${p.kind==='seat'?` · 좌석 높이 ${p.position[1].toFixed(2)}m`:''}`,6);
}
function setupInput() {
  $('choose-world').onclick=()=>openDialog('world-picker');$('choose-character').onclick=()=>openDialog('character-picker');
  $('reference-button').onclick=()=>{if(!selectedMap)return;$('reference-title').textContent=selectedMap.name;$('reference-image').src=`references/${selectedMap.file}`;$('reference-image').alt=`${selectedMap.name} 원본 이미지`;openDialog('reference-dialog');};
  $('help-button').onclick=()=>openDialog('help-dialog');
  for(const d of document.querySelectorAll('dialog')){d.querySelector('.close-dialog').onclick=()=>d.close();d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});}
  $('map-search').oninput=filterMaps;
  document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{activeFilter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(f=>f.classList.toggle('selected',f===b));filterMaps();});
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
  $('reset-position').onclick=()=>{resetPosition();toast('시작 위치로 돌아왔어요.',2);};
  $('retry').onclick=()=>select(selectedMap,selectedCharacter,true,true);
  $('run-button').onclick=()=>{runToggle=!runToggle;$('run-button').setAttribute('aria-pressed',String(runToggle));};
  $('interact-button').onclick=interact;
  $('fullscreen-button').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('world').requestFullscreen();}catch{toast('이 브라우저에서는 전체 화면을 사용할 수 없어요.');}};
  $('capture').onclick=()=>{if(!loaded)return;renderer.render(scene,camera);const a=document.createElement('a');a.download=`${selectedMap.id}-${selectedCharacter.name}.png`;a.href=renderer.domElement.toDataURL('image/png');a.click();toast('탐험 화면을 PNG로 저장했어요.',2);};
  window.addEventListener('keydown',event=>{
    if(dialogOpen()||/INPUT|TEXTAREA|SELECT/.test(event.target.tagName))return;
    if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.code))event.preventDefault();
    keys.add(event.code);
    if(event.repeat)return;
    if(motionKeys[event.code])triggerMotion(motionKeys[event.code]);
    if(event.code==='KeyE')interact();
  });
  window.addEventListener('keyup',event=>keys.delete(event.code));window.addEventListener('blur',clearInput);document.addEventListener('visibilitychange',()=>{if(document.hidden)clearInput();});
  const joy=$('joystick');joy.addEventListener('pointerdown',e=>{if(!loaded)return;e.preventDefault();joystick.pointer=e.pointerId;joy.setPointerCapture(e.pointerId);joystickMove(e);});
  joy.addEventListener('pointermove',e=>{if(e.pointerId===joystick.pointer)joystickMove(e);});joy.addEventListener('pointerup',resetJoystick);joy.addEventListener('pointercancel',resetJoystick);joy.addEventListener('lostpointercapture',resetJoystick);
  $('scene').addEventListener('pointerdown',e=>{if(!loaded||dialogOpen())return;dragging={id:e.pointerId,x:e.clientX,y:e.clientY};$('scene').setPointerCapture(e.pointerId);});
  $('scene').addEventListener('pointermove',e=>{if(dragging?.id!==e.pointerId)return;yaw-=(e.clientX-dragging.x)*.006;pitch=Math.max(view==='first'?-1.35:-.15,Math.min(view==='first'?1.35:1.2,pitch+(e.clientY-dragging.y)*.005));dragging.x=e.clientX;dragging.y=e.clientY;});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])$('scene').addEventListener(type,()=>dragging=null);
  $('scene').addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(2.4,Math.min(18,distance+e.deltaY*.008));},{passive:false});
  $('scene').addEventListener('contextmenu',e=>e.preventDefault());
}
function updateCamera(dt) {
  const smooth=1-Math.exp(-dt*9);
  if(view==='overview') {
    const size=Math.max(world.width,world.depth),target=new THREE.Vector3(0,2,0);
    const desired=new THREE.Vector3(Math.sin(yaw)*size*.6,size*.95,Math.cos(yaw)*size*.6);
    const aspectCorrection=Math.max(1,1/camera.aspect);desired.multiplyScalar(aspectCorrection);
    camera.position.lerp(desired,smooth);cameraTarget.lerp(target,smooth);camera.lookAt(cameraTarget);return;
  }
  const target=position.clone().add(new THREE.Vector3(0,view==='first'?1.25:1.05,0));
  cameraTarget.lerp(target,smooth);
  if(view==='first') {
    camera.position.copy(target);
    camera.lookAt(target.clone().add(new THREE.Vector3(-Math.sin(yaw)*Math.cos(pitch),-Math.sin(pitch),-Math.cos(yaw)*Math.cos(pitch))));return;
  }
  const offset=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));
  let cameraDistance=distance;
  // Camera obstruction uses the same physical walls as movement. Sampling avoids
  // raycasting every small leaf/book/rope, keeping large maps usable on phones.
  for(let d=.3;d<distance;d+=.16){
    if(blocked(world.cameraColliders,target.x+offset.x*d,target.z+offset.z*d,target.y+offset.y*d,.08,.12)){
      cameraDistance=Math.max(.55,d-.18);break;
    }
  }
  const desired=cameraTarget.clone().addScaledVector(offset,cameraDistance);
  camera.position.lerp(desired,Math.min(1,smooth*1.5));camera.lookAt(cameraTarget);
}
function drawMinimap() {
  const ctx=$('minimap').getContext('2d'),w=240,h=240;
  const scale=220/Math.max(world.width,world.depth),cx=120,cy=120;
  ctx.fillStyle='#234638';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#91ad7630';ctx.lineWidth=.6;
  for(let i=10;i<240;i+=22){ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,240);ctx.moveTo(0,i);ctx.lineTo(240,i);ctx.stroke();}
  ctx.save();ctx.translate(cx,cy);ctx.scale(scale,scale);
  for(const s of world.surfaces){ctx.save();ctx.translate(s.x,s.z);ctx.rotate(-(s.rot||0));ctx.fillStyle=s.y>.1?'#a3ad7960':'#75956345';ctx.fillRect(-s.w/2,-s.d/2,s.w,s.d);ctx.restore();}
  for(const c of world.colliders){ctx.save();ctx.translate(c.x,c.z);ctx.rotate(-(c.rot||0));ctx.fillStyle='#172f25b0';ctx.fillRect(-c.w/2,-c.d/2,c.w,c.d);ctx.restore();}
  ctx.restore();
  ctx.fillStyle='#ddc484';for(const interaction of world.interactions){ctx.beginPath();ctx.arc(cx+interaction.position[0]*scale,cy+interaction.position[2]*scale,1.5,0,Math.PI*2);ctx.fill();}
  ctx.save();ctx.translate(cx+position.x*scale,cy+position.z*scale);ctx.rotate(-avatar.rotation.y);
  ctx.fillStyle='#fff5c3';ctx.shadowColor='#fff5c3';ctx.shadowBlur=6;ctx.beginPath();ctx.moveTo(0,7);ctx.lineTo(-5,-5);ctx.lineTo(0,-2);ctx.lineTo(5,-5);ctx.closePath();ctx.fill();ctx.restore();
  $('coordinates').textContent=`${position.x.toFixed(1)}, ${position.z.toFixed(1)}`;$('level').textContent=`${position.y.toFixed(1)} m`;
}
function updateInteractions() {
  nearestInteraction=null;let nearestDistance=2.0;
  for(const point of world.interactions){const p=point.position,d=Math.hypot(p[0]-position.x,p[2]-position.z);if(d<nearestDistance&&Math.abs(p[1]-position.y)<2){nearestInteraction=point;nearestDistance=d;}}
  $('interaction-hint').hidden=!nearestInteraction;
  if(nearestInteraction)$('interaction-hint').querySelector('span').textContent=nearestInteraction.name;
}
function frame(now) {
  const dt=Math.min(Math.max((now-lastTime)/1000,0),.05);lastTime=now;elapsed+=dt;
  if(loaded && !document.hidden) {
    let x=0,z=0;
    if(!dialogOpen()) {
      x=(keys.has('ArrowRight')||keys.has('KeyD')?1:0)-(keys.has('ArrowLeft')||keys.has('KeyA')?1:0)+joystick.x;
      z=(keys.has('ArrowDown')||keys.has('KeyS')?1:0)-(keys.has('ArrowUp')||keys.has('KeyW')?1:0)+joystick.z;
    }
    const length=Math.hypot(x,z),moving=length>.09;
    const running=runToggle||keys.has('ShiftLeft')||keys.has('ShiftRight');
    if(moving) {
      if(overrideMotion==='Lose'||['Walk','Run'].includes(overrideMotion))overrideMotion=null;
      if(!overrideMotion) {
        const factor=1/Math.max(length,1),dx=(x*Math.cos(yaw)+z*Math.sin(yaw))*factor,dz=(-x*Math.sin(yaw)+z*Math.cos(yaw))*factor;
        const speed=running?4.0:1.75;moveWithCollisions(world,position,dx*dt*speed,dz*dt*speed);
        const heading=Math.atan2(dx,dz),diff=Math.atan2(Math.sin(heading-avatar.rotation.y),Math.cos(heading-avatar.rotation.y));
        avatar.rotation.y+=diff*(1-Math.exp(-dt*14));setMotion(running?'Run':'Walk');
      }
    } else if(!overrideMotion)setMotion('Idle');
    const floor=floorAt(world.surfaces,position.x,position.z,position.y);
    if(floor!==null){if(position.y>floor+.015){verticalSpeed-=12*dt;position.y=Math.max(floor,position.y+verticalSpeed*dt);}else{position.y=floor;verticalSpeed=0;}}
    if(position.y<-5)resetPosition();
    avatar.position.copy(position);if(mixer)mixer.update(dt);
    for(const animate of world.animated)animate(dt,elapsed);
    updateCamera(dt);
    if(now-minimapTime>130){drawMinimap();updateInteractions();minimapTime=now;}
    renderer.render(scene,camera);
  }
  if(toastUntil && now>toastUntil){$('toast').hidden=true;toastUntil=0;}
  requestAnimationFrame(frame);
}
async function boot() {
  try {
    renderer=new THREE.WebGLRenderer({canvas:$('scene'),antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});
    renderer.setPixelRatio(pixelRatio);renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.18;
    renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(52,1,.04,600);camera.position.set(6,5,9);
    const ambient=new THREE.HemisphereLight('#fff3d5','#697857',2.35);ambient.name='ambient';scene.add(ambient);
    const sun=new THREE.DirectionalLight('#fff4d8',2.25);sun.name='sun';sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.bias=-.0004;sun.shadow.normalBias=.035;sun.shadow.camera.near=.1;sun.shadow.camera.far=200;scene.add(sun);
    const fill=new THREE.DirectionalLight('#c5dded',.6);fill.position.set(10,8,-14);scene.add(fill);
    const resize=()=>{const w=$('world').clientWidth,h=$('world').clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe($('world'));resize();
    setupInput();
    const response=await fetch('../characters/manifest.json');if(!response.ok)throw new Error(`캐릭터 목록 ${response.status}`);entries=await response.json();
    if(maps.length!==25||entries.length!==14)throw new Error('25개 맵 / 14개 캐릭터 목록을 확인해 주세요.');
    buildPickers();
    const params=new URLSearchParams(location.search);let saved={};try{saved=JSON.parse(localStorage.getItem('little-world-selection')||'{}');}catch{ /* optional */ }
    const mapRequest=params.get('map')||saved.map,characterRequest=params.get('character')||saved.character;
    const map=maps.find(m=>m.id.toLowerCase()===String(mapRequest).toLowerCase()||m.name===mapRequest)||maps[0];
    const character=entries.find(e=>e.name.toLowerCase()===String(characterRequest).toLowerCase()||String(e.id)===characterRequest||e.slug===characterRequest)||entries[0];
    requestAnimationFrame(frame);await select(map,character);
  }catch(error){showError(error);}
}
boot();
