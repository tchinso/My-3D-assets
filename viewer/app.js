import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

const $ = id => document.getElementById(id);
const stage = $('stage');
const renderer = new THREE.WebGLRenderer({canvas:$('canvas'),antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#f6f8fb');
const camera = new THREE.PerspectiveCamera(30,1,.001,100);
const controls = new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;
controls.dampingFactor=.08;
controls.maxPolarAngle=Math.PI*.93;
scene.add(new THREE.HemisphereLight(0xffffff,0xc8d5e8,2));
const key = new THREE.DirectionalLight(0xffffff,2.1);
key.position.set(-3,5,4);scene.add(key);
const rim = new THREE.DirectionalLight(0xddeaff,.8);
rim.position.set(2,3,-3);scene.add(rim);
const loader = new GLTFLoader();
const clock = new THREE.Clock();
let entries=[],current=null,model=null,mixer=null,clips=[],action=null,playing=true,dark=false,loadToken=0;
let modelCenter = new THREE.Vector3(0,.5,0),modelHeight=1;
let currentURL='';

function resize(){
  const width=stage.clientWidth,height=stage.clientHeight;
  renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);resize();

function resetView(){
  controls.target.copy(modelCenter);
  const distance=modelHeight*2.35/Math.min(camera.aspect,1);
  camera.position.copy(modelCenter).add(new THREE.Vector3(modelHeight*.44,modelHeight*.10,distance));
  camera.near=modelHeight*.001;camera.far=modelHeight*100;camera.updateProjectionMatrix();
  controls.minDistance=modelHeight*.35;controls.maxDistance=modelHeight*12;controls.update();
}

function disposeModel(object){
  object.traverse(child=>{
    if(!child.isMesh)return;
    child.geometry.dispose();
    const materials=Array.isArray(child.material)?child.material:[child.material];
    for(const material of materials){
      for(const value of Object.values(material))if(value?.isTexture)value.dispose();
      material.dispose();
    }
  });
}

function setClip(clip){
  if(!mixer)return;
  mixer.stopAllAction();
  if(clip){
    const looping=['Idle','Walk','Run'].includes(clip.name);
    action=mixer.clipAction(clip);
    action.reset().setLoop(looping?THREE.LoopRepeat:THREE.LoopOnce,looping?Infinity:1);
    action.clampWhenFinished=!looping;
    action.play();
  }
  else action=null;
  playing=true;$('play').textContent='Ⅱ';$('timeline').value=0;
  for(const button of $('clips').children)button.classList.toggle('active',button.dataset.clip===(clip?.name||'Bind pose'));
}

function palette(entry){
  let colors=entry.palette||['#91b9e3','#ffffff','#1c2b40'];
  if(!Array.isArray(colors))colors=Object.values(colors);
  $('palette').replaceChildren();
  for(let color of colors){
    if(typeof color==='object')color=color.hex||color.color;
    const swatch=document.createElement('span');swatch.style.background=color;swatch.title=color;$('palette').append(swatch);
  }
}

async function selectCharacter(entry,forceRefresh=false){
  const token=++loadToken;current=entry;
  for(const button of $('characters').children)button.classList.toggle('active',button.dataset.slug===entry.slug);
  $('number').textContent=`CHARACTER / ${String(entry.id).padStart(2,'0')}`;
  $('name').textContent=entry.name||entry.slug;$('name-ko').textContent=entry.name_ko||'';
  $('tagline').textContent=entry.tagline||'';
  const revision=encodeURIComponent(entry.sha256??entry.revision??entry.bytes??0);
  const query=`?revision=${revision}${forceRefresh?`&refresh=${Date.now()}`:''}`;
  currentURL=`../characters/${entry.slug}/${entry.slug}.glb${query}`;
  $('download').href=currentURL;$('sheet').href=`../characters/${entry.slug}/${entry.slug}_sheet.png${query}`;
  $('status').textContent='모델을 불러오는 중';$('status').classList.remove('error');
  palette(entry);
  if(model){scene.remove(model);disposeModel(model);model=null;}
  mixer=null;action=null;clips=[];$('clips').replaceChildren();
  try{
    const gltf=await loader.loadAsync(currentURL);
    if(token!==loadToken){disposeModel(gltf.scene);return;}
    model=gltf.scene;
    let firstMouth=null;
    model.traverse(object=>{
      if(object.isMesh && object.name.toLowerCase().startsWith('mouth_')){
        if(firstMouth===null)firstMouth=object.name;
        else if(object.name!==firstMouth)object.visible=false;
      }
    });
    scene.add(model);model.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(model),size=bounds.getSize(new THREE.Vector3());
    bounds.getCenter(modelCenter);modelHeight=Math.max(size.y,size.x*.78,size.z,0.01);resetView();
    clips=gltf.animations;mixer=new THREE.AnimationMixer(model);
    mixer.addEventListener('finished',()=>{playing=false;$('play').textContent='▶';});
    for(const clip of clips){
      const button=document.createElement('button');button.textContent=clip.name;button.dataset.clip=clip.name;
      button.addEventListener('click',()=>setClip(clip));$('clips').append(button);
    }
    const bind=document.createElement('button');bind.textContent='기본 자세';bind.dataset.clip='Bind pose';bind.addEventListener('click',()=>setClip(null));$('clips').append(bind);
    $('clip-info').textContent=`${clips.length} ANIMATIONS`;
    setClip(clips.find(clip=>/idle/i.test(clip.name))||clips[0]||null);
    $('status').textContent='3D PREVIEW / READY';
  }catch(error){
    if(token!==loadToken)return;
    $('status').textContent=`불러오기 실패: ${error.message}`;$('status').classList.add('error');console.error(error);
  }
}

$('reset').addEventListener('click',resetView);
$('refresh').addEventListener('click',async()=>{
  if(!current)return;
  try{
    const manifest=await loadManifest();
    const updated=manifest.find(entry=>entry.slug===current.slug)||current;
    await selectCharacter(updated,true);
  }catch(error){$('status').textContent=error.message;$('status').classList.add('error');}
});
$('background').addEventListener('click',()=>{dark=!dark;scene.background.set(dark?'#202e43':'#f6f8fb');stage.classList.toggle('dark',dark);});
$('capture').addEventListener('click',()=>{
  renderer.render(scene,camera);
  const link=document.createElement('a');link.download=`${current?.slug||'character'}_preview.png`;
  link.href=renderer.domElement.toDataURL('image/png');link.click();
});
$('play').addEventListener('click',()=>{
  if(!playing&&action&&action.time>=action.getClip().duration){action.reset().play();}
  playing=!playing;$('play').textContent=playing?'Ⅱ':'▶';
});
$('timeline').addEventListener('input',()=>{
  if(!action)return;
  action.time=Number($('timeline').value)*action.getClip().duration;
  action.paused=false;
  mixer.update(0);
  playing=false;$('play').textContent='▶';
});
renderer.setAnimationLoop(()=>{
  const delta=Math.min(clock.getDelta(),.05);
  if(mixer&&playing)mixer.update(delta*Number($('speed').value));
  if(action){
    const duration=action.getClip().duration;
    $('timeline').value=duration?action.time/duration:0;
    $('time').textContent=`${action.time.toFixed(2)} / ${duration.toFixed(2)}s`;
  }else $('time').textContent='기본 자세';
  controls.update();renderer.render(scene,camera);
});

async function loadManifest(){
  const response=await fetch('../characters/manifest.json',{cache:'no-store'});
  if(!response.ok)throw new Error(`manifest ${response.status}`);
  const manifest=await response.json();
  return Array.isArray(manifest)?manifest:manifest.characters||manifest.models||[];
}

try{
  entries=await loadManifest();
  for(const entry of entries){
    const button=document.createElement('button');button.className='character';button.dataset.slug=entry.slug;
    const badge=document.createElement('span');badge.className='badge';badge.textContent=String(entry.id).padStart(2,'0');
    const labels=document.createElement('span'),name=document.createElement('strong'),korean=document.createElement('small');
    name.textContent=entry.name||entry.slug;korean.textContent=entry.name_ko||'';labels.append(name,korean);button.append(badge,labels);
    button.addEventListener('click',()=>selectCharacter(entry));$('characters').append(button);
  }
  if(entries.length)await selectCharacter(entries[0]);else throw new Error('캐릭터 manifest가 비어 있습니다.');
}catch(error){$('status').textContent=error.message;$('status').classList.add('error');console.error(error);}
