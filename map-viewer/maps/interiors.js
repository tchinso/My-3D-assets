// Interior geometry is built at metre scale: table 0.75 m, seat 0.44 m,
// doorway 2.3 m. Reference illustrations inform the architecture and props.
const C = { wood:'#805e42', darkWood:'#513d32', brass:'#b9a16b', cream:'#ddd4b4', iron:'#464e49' };

function instances(k,geometry,items,roughness=.85) {
  if(!items.length) return;
  const T=k.THREE, material=new T.MeshStandardMaterial({color:0xffffff,roughness});
  const mesh=new T.InstancedMesh(geometry,material,items.length), obj=new T.Object3D();
  items.forEach((p,i)=>{obj.position.set(p.x,p.y,p.z); obj.rotation.set(p.rx||0,p.rot||0,p.rz||0);obj.scale.set(p.w||1,p.h||1,p.d||1);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);mesh.setColorAt(i,new T.Color(p.color||C.wood));});
  mesh.castShadow=true;mesh.receiveShadow=true;k.root.add(mesh);return mesh;
}
const batch=(k,a)=>instances(k,new k.THREE.BoxGeometry(1,1,1),a);
function cylinder(k,x,y,z,r,h,color,rotation=[0,0,0],top=r) {
  const m=new k.THREE.Mesh(new k.THREE.CylinderGeometry(top,r,h,16),new k.THREE.MeshStandardMaterial({color,roughness:.78}));
  m.position.set(x,y,z);m.rotation.set(...rotation);m.castShadow=true;m.receiveShadow=true;k.root.add(m);return m;
}
function lathe(k,x,y,z,height,radius,color,shape='jar') {
  const profiles={jar:[[0,0],[.65,0],[.9,.1],[1,.35],[.92,.65],[.55,.82],[.55,.95],[.62,1]],bottle:[[0,0],[.7,0],[.82,.1],[.78,.48],[.35,.7],[.25,.74],[.25,.98],[.33,1]],vase:[[0,0],[.55,0],[.85,.17],[1,.43],[.75,.68],[.35,.82],[.4,1]],urn:[[0,0],[.6,0],[.7,.05],[.92,.25],[1,.48],[.7,.72],[.56,.84],[.67,.89],[.67,1]]};
  const p=(profiles[shape]||profiles.jar).map(([a,b])=>new k.THREE.Vector2(a*radius,b*height));
  const m=new k.THREE.Mesh(new k.THREE.LatheGeometry(p,16),new k.THREE.MeshStandardMaterial({color,roughness:.6}));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;k.root.add(m);return m;
}
function roundSolid(k,x,z,r,y,h) {
  k.collide(x,z,r*2,r*2,{y,h});
  // Navigation uses the conservative rectangle for indexing, then the actual
  // circular outline to keep pillar corners from blocking a landing turn.
  k.colliders[k.colliders.length-1].shape='circle';
}
function room(k,w,d,{floor='#bbb39a',wall='#b7b29b',tile='stone',height=3.8,brick=false}={}) {
  k.floor(w,d,floor,{tile});k.wall(0,-d/2,w,height,.22,wall);k.wall(-w/2,0,.22,height,d,wall);
  k.collide(w/2,0,.18,d,{h:height,camera:false});k.collide(0,d/2,w,.18,{h:height,camera:false});
  const parts=[];
  for(let y=.14;y<height;y+=.4){parts.push({x:0,y,z:-d/2+.12,w,h:.018,d:.02,color:'#786b60'});parts.push({x:-w/2+.12,y,z:0,w:.02,h:.018,d,color:'#786b60'});if(brick){for(let x=-w/2+.3;x<w/2;x+=.8)parts.push({x:x+(Math.round(y/.4)%2)*.4,y:y+.19,z:-d/2+.125,w:.015,h:.38,d:.02,color:'#786b60'});for(let z=-d/2+.3;z<d/2;z+=.8)parts.push({x:-w/2+.125,y:y+.19,z:z+(Math.round(y/.4)%2)*.4,w:.02,h:.38,d:.015,color:'#786b60'});}}
  if(brick)batch(k,parts);
  k.box(0,.1,-d/2+.14,w,.2,.12,C.darkWood);k.box(-w/2+.14,.1,0,.12,.2,d,C.darkWood);
}
function woodFloor(k,x,z,w,d,y=0) {
  k.platform(x,y,z,w,d,'#a48a67');const a=[];
  for(let zz=-d/2;zz<d/2;zz+=.24)a.push({x,y:y+.012,z:z+zz,w,h:.018,d:.012,color:'#685540'});batch(k,a);
}
function table(k,x,z,w=2.3,d=.9,y=0,color=C.wood) {
  k.box(x,y+.77,z,w,.1,d,color);const a=[];
  for(const xx of [-1,1])for(const zz of [-1,1])a.push({x:x+xx*(w/2-.12),y:y+.36,z:z+zz*(d/2-.1),w:.13,h:.72,d:.13,color:C.darkWood});
  a.push({x,y:y+.54,z,w:w-.2,h:.15,d:.1,color:C.darkWood});batch(k,a);k.collide(x,z,w,d,{y,h:.82});
}
function bench(k,x,z,w=2.2,rot=0,y=0,color=C.wood) {
  k.box(x,y+.44,z,w,.09,.4,color,{rot});const a=[];
  for(const s of [-1,1]){const xx=s*(w/2-.22);a.push({x:x+xx*Math.cos(rot),y:y+.2,z:z-xx*Math.sin(rot),w:.13,h:.4,d:.34,color:C.darkWood,rot});}
  batch(k,a);k.collide(x,z,w,.4,{y,h:.52,rot});k.interactions.push({name:'나무 벤치',position:[x,y+.44,z],kind:'seat',text:'목재 판재와 두 다리로 만든 벤치입니다.'});
}
function chair(k,x,z,rot=0,y=0,color=C.wood) {
  const T=k.THREE,g=new T.Group();g.position.set(x,y,z);g.rotation.y=rot;k.root.add(g);
  const add=(xx,yy,zz,w,h,d,c)=>{const m=new T.Mesh(new T.BoxGeometry(w,h,d),new T.MeshStandardMaterial({color:c,roughness:.85}));m.position.set(xx,yy,zz);m.castShadow=true;g.add(m);};
  add(0,.44,0,.48,.085,.47,color);for(const xx of [-.18,.18])for(const zz of [-.16,.16])add(xx,.21,zz,.065,.42,.065,C.darkWood);
  add(0,.86,-.19,.45,.12,.07,color);for(const xx of [-.2,0,.2])add(xx,.69,-.19,.035,.38,.035,color);
  k.collide(x,z,.48,.5,{y,h:.95,rot});k.interactions.push({name:'의자',position:[x,y+.44,z],kind:'seat',text:'등받이 살과 네 다리가 있는, 사람 크기에 맞춘 의자입니다.'});
}
function bookcase(k,x,z,w=2.5,h=2.6,rot=0,y=0,seed=0) {
  const a=[],books=[],rows=Math.max(3,Math.floor(h/.4)), T=k.THREE;
  const put=(xx,yy,zz,ww,hh,dd,color)=>{a.push({x:x+xx*Math.cos(rot)+zz*Math.sin(rot),y:y+yy,z:z-xx*Math.sin(rot)+zz*Math.cos(rot),w:ww,h:hh,d:dd,color,rot});};
  put(0,h/2,-.18,w,h,.07,C.darkWood);put(-w/2,h/2,0,.1,h,.48,C.wood);put(w/2,h/2,0,.1,h,.48,C.wood);
  for(let row=0;row<=rows;row++)put(0,row*h/rows,0,w,.075,.5,C.wood);
  const colors=['#667652','#777ba0','#9f5b43','#b89962','#606b72','#ad977b','#824f55'];
  for(let row=0;row<rows;row++)for(let n=0;n<Math.floor(w/.13)-1;n++){
    const xx=-w/2+.13+n*.13,yy=row*h/rows+.065,hh=.22+((n*7+row*3+seed)%9)*.013;
    books.push({x:x+xx*Math.cos(rot)+.035*Math.sin(rot),y:y+yy+hh/2,z:z-xx*Math.sin(rot)+.035*Math.cos(rot),w:.075+((n+row)%3)*.013,h:hh,d:.24,color:colors[(n+row*3+seed)%colors.length],rot});
    books.push({x:x+xx*Math.cos(rot)+.165*Math.sin(rot),y:y+yy+hh*.65,z:z-xx*Math.sin(rot)+.165*Math.cos(rot),w:.052,h:.012,d:.01,color:'#d7bf8b',rot});
  }
  batch(k,a);batch(k,books);k.collide(x,z,w,.55,{y,h,rot});
}
function frame(k,x,y,z,w,h,color='#65735b',rot=0) {
  k.box(x,y,z,w,h,.06,C.darkWood,{rot});k.box(x+Math.sin(rot)*.04,y,z+Math.cos(rot)*.04,w-.1,h-.1,.03,color,{rot});
  for(let i=0;i<3;i++){const xx=(i-1)*w*.17;k.box(x+xx*Math.cos(rot)+Math.sin(rot)*.065,y-.03,z-xx*Math.sin(rot)+Math.cos(rot)*.065,w*.14,h*.27,.02,['#c7b58b','#6c8070','#d9c9a5'][i],{rot});}
}
function door(k,x,z,width=1.3,y=0,color='#866450',height=2.14) {
  k.box(x,y+height/2,z,width,height,.13,color,{solid:true});k.sphere(x,y+height,z,width/2,color,[1,1,.13]);
  const tor=new k.THREE.Mesh(new k.THREE.TorusGeometry(width/2+.06,.055,6,20,Math.PI),new k.THREE.MeshStandardMaterial({color:C.brass}));tor.position.set(x,y+height,z+.09);k.root.add(tor);
  batch(k,[{x:x-width/2-.06,y:y+height/2,z:z+.09,w:.11,h:height+.06,d:.12,color:C.brass},{x:x+width/2+.06,y:y+height/2,z:z+.09,w:.11,h:height+.06,d:.12,color:C.brass},{x,y:y+height*.19,z:z+.08,w:width-.18,h:.05,d:.04,color:C.darkWood},{x,y:y+height*.75,z:z+.08,w:width-.18,h:.04,d:.04,color:C.darkWood}]);k.sphere(x+width*.3,y+height*.49,z+.14,.055,C.brass);
}
function sconce(k,x,y,z) {
  k.sphere(x,y,z,.12,C.brass,[.6,1,.4]);k.line([[x,y,z],[x,y-.14,z+.12],[x,y+.12,z+.35]],C.brass,.03);k.cylinder(x,y+.24,z+.35,.035,.28,'#fff4cb');k.sphere(x,y+.43,z+.35,.06,'#ffe09a',[.5,1,.5]);
}
function pipe(k,points,r=.11,color=C.iron) {k.line(points,color,r);for(let i=0;i<points.length-1;i++){const a=points[i],b=points[i+1],p=a.map((n,j)=>n+(b[j]-n)*.25);const dx=b[0]-a[0],dy=b[1]-a[1];k.torus(...p,r*1.07,.025,color,dy!==0?[Math.PI/2,0,0]:dx!==0?[0,Math.PI/2,0]:[0,0,0]);}}
function barrel(k,x,z,r=.38,h=.85,y=0,color='#8e7754') {
  lathe(k,x,y,z,h,r,color,'jar');for(const yy of [.1,.4,.77])k.torus(x,y+yy*h/.85,z,r*(yy===.4?.97:.74),.033,'#4f4f44');k.cylinder(x,y+h+.012,z,r*.58,.035,color);roundSolid(k,x,z,r,y,h);
}
function crate(k,x,z,w=.85,h=.85,d=.85,y=0,color='#987f56') {
  k.box(x,y+h/2,z,w,h,d,color,{solid:true});const a=[];
  for(let i=-2;i<=2;i++){a.push({x:x+i*w/5,y:y+h/2,z:z+d/2+.015,w:.02,h:h-.06,d:.025,color:C.darkWood});a.push({x:x+i*w/5,y:y+h+.013,z,w:.02,h:.02,d:d-.08,color:C.darkWood});}
  for(const yy of [.06,h-.06])a.push({x,y:y+yy,z:z+d/2+.035,w,h:.085,d:.055,color:'#ae9164'});batch(k,a);
}
function sack(k,x,z,r=.3,h=.7,y=0,color='#b4a88a') {
  k.sphere(x,y+h*.4,z,r,color,[1,h*.68/r,.8]);k.cylinder(x,y+h*.82,z,r*.34,h*.15,color);k.torus(x,y+h*.83,z,r*.35,.02,C.darkWood);k.sphere(x,y+h*.98,z,r*.45,color,[1,.35,.8]);k.collide(x,z,r*1.8,r*1.8,{y,h});
}
function plant(k,x,z,y=0,h=1,color='#577655') {
  lathe(k,x,y,z,.3,.21,'#8a8065');k.cylinder(x,y+h/2+.23,z,.035,h*.8,'#786751');for(let i=0;i<5;i++)k.sphere(x+Math.sin(i*2.4)*.18,y+.36+i*h*.13,z+Math.cos(i*2.4)*.14,.27,color,[1,.8,1]);
}
function ladder(k,x,z,h=2.7,y=0,rot=0) {
  const a=[];for(const s of [-1,1])a.push({x:x+s*.23*Math.cos(rot),y:y+h/2,z:z-s*.23*Math.sin(rot),w:.06,h,d:.06,color:C.wood,rot});for(let yy=.2;yy<h;yy+=.28)a.push({x,y:y+yy,z,w:.48,h:.055,d:.065,color:C.wood,rot});batch(k,a);k.collide(x,z,.5,.2,{y,h,rot});
}
function stairsZ(k,x,z,w,count,rise,run,color,y=0,direction=-1) {
  const a=[];for(let i=0;i<count;i++){const zz=z+direction*(i+.5)*run,top=y+(i+1)*rise;a.push({x,y:top-.08,z:zz,w,h:.16,d:run+.015,color});k.surface(x,zz,w,run+.03,top);}
  batch(k,a);return y+count*rise;
}
function railing(k,x1,z1,x2,z2,y=0,color=C.brass) {
  const len=Math.hypot(x2-x1,z2-z1),a=[],rot=Math.atan2(-(z2-z1),x2-x1);k.line([[x1,y+.94,z1],[x2,y+.94,z2]],color,.035);
  for(let i=0;i<=Math.ceil(len/.45);i++){const f=i/Math.ceil(len/.45);a.push({x:x1+(x2-x1)*f,y:y+.47,z:z1+(z2-z1)*f,w:.04,h:.94,d:.04,color,rot});}batch(k,a);k.collide((x1+x2)/2,(z1+z2)/2,len,.11,{y,h:1.1,rot});
}
function landingGuard(k,x1,z1,x2,z2,y) {
  const color='#554e45',len=Math.hypot(x2-x1,z2-z1),rot=Math.atan2(-(z2-z1),x2-x1),count=Math.max(1,Math.ceil(len/.45));
  const ring=k.geometry('landing-ring:.07,.012,5,12',()=>new k.THREE.TorusGeometry(.07,.012,5,12));
  const cap=k.geometry('landing-cap:.045,8,6',()=>new k.THREE.SphereGeometry(.045,8,6));
  k.line([[x1,y+.94,z1],[x2,y+.94,z2]],color,.035);
  for(const height of [.16,.49])k.line([[x1,y+height,z1],[x2,y+height,z2]],color,.019);
  // Cached primitives merge into the room's existing material batches rather
  // than introducing one authored instance draw call per short guard section.
  for(let i=0;i<count;i++){const t=(i+.5)/count;k.mesh(ring,'#ab9470',x1+(x2-x1)*t,y+.64,z1+(z2-z1)*t,{rot});}
  for(let i=0;i<=count;i++){const t=i/count,x=x1+(x2-x1)*t,z=z1+(z2-z1)*t;k.box(x,y+.47,z,.04,.94,.04,color,{rot});k.mesh(cap,'#baa480',x,y+.965,z);}
  k.collide((x1+x2)/2,(z1+z2)/2,len,.11,{y,h:1.1,rot});
}
function light(k,x,y,z,color='#ffd996',intensity=2,distance=7) {const l=new k.THREE.PointLight(color,intensity,distance,2);l.position.set(x,y,z);k.root.add(l);}
function inspect(k,name,x,y,z,text) {k.interactions.push({name,position:[x,y,z],kind:'inspect',text});}
function flame(k,x,y,z,size=.3) {const a=k.sphere(x,y,z,size,'#ff7a2e',[.7,1.7,.7]);if(a){a.userData.dynamic=true;k.animated.push((dt,t)=>{a.scale.y=1.5+Math.sin(t*6)*.16;});}k.sphere(x,y-.05,z,size*.55,'#ffe8a0',[.8,1.6,.8]);light(k,x,y,z,'#ffad58',2,5);}
function statue(k,x,z,y=0,scale=1) {
  k.cylinder(x,y+.17*scale,z,.32*scale,.34*scale,'#8d9882');k.torus(x,y+.35*scale,z,.31*scale,.04*scale,'#bac0a3');k.sphere(x,y+.86*scale,z,.35*scale,'#9bab8e',[.85,1.35,.7]);k.sphere(x,y+1.36*scale,z,.27*scale,'#a7b89a',[1.1,1,.9]);
  for(const s of [-1,1]){k.sphere(x+s*.26*scale,y+.9*scale,z,.2*scale,'#a9b89c',[.45,1.5,.6]);k.sphere(x+s*.11*scale,y+1.42*scale,z+.23*scale,.045*scale,'#536750');k.cone(x+s*.19*scale,y+1.68*scale,z,.085*scale,.29*scale,'#adbd9d');k.sphere(x+s*.16*scale,y+.52*scale,z+.14*scale,.16*scale,'#879c7f',[.6,.7,1.3]);}
  k.sphere(x,y+1.2*scale,z+.21*scale,.19*scale,'#bac6a9',[1,.6,.6]);k.line([[x,y+.56*scale,z-.2*scale],[x+.35*scale,y+.4*scale,z-.45*scale],[x+.48*scale,y+.74*scale,z-.3*scale]],'#9ead90',.1*scale);k.collide(x,z,.8*scale,.8*scale,{y,h:1.8*scale});
}

function boiler(k) {
  room(k,13,10,{floor:'#a89e87',wall:'#9d9682',brick:true,height:4.8});
  k.platform(-3.8,.8,-3.55,4.4,2.4,'#a89e87');k.box(-3.8,.4,-3.55,4.4,.8,2.4,'#8e8b7b',{solid:true});stairsZ(k,-3.8,-.8,2.5,5,.16,.31,'#b0a792');
  railing(k,-6,-2.3,-5,-2.3,.8,'#545548');railing(k,-2.5,-2.3,-1.6,-2.3,.8,'#545548');railing(k,-5.1,-2.2,-5.1,-.7,0,'#545548');
  door(k,-4.1,-4.83,1.1,.8,'#524c41');k.box(-4.1,2.75,-4.66,1.05,1.1,.06,'#343b37');
  const seams=[];for(let i=0;i<9;i++)seams.push({x:-4.56+i*.11,y:2.75,z:-4.59,w:.025,h:.95,d:.03,color:'#717869'});batch(k,seams);
  const make=(x,z,r,h,col)=>{k.cylinder(x,h/2,z,r,h,col,{solid:true,segments:24});k.torus(x,.18,z,r,.07,'#525548');k.torus(x,h*.75,z,r,.06,'#737b63');k.torus(x,h-.1,z,r,.06,'#6b735c');k.cylinder(x,h+.6,z,r*.47,1.3,'#485348',{segments:20});k.cylinder(x,h+1.28,z,r*.47,.05,'#232b27');};
  make(3.5,-3.1,1.05,2.8,'#4c806e');k.cone(3.5,3.25,-3.1,1.05,.9,'#4c806e',24);make(1,-3.65,.68,2.5,'#a1a985');make(-5.45,2.4,.6,2.2,'#514e3f');
  k.box(3.5,.98,-2.04,.75,.48,.04,'#ffe5a0');k.box(3.5,1.02,-1.99,.52,.26,.045,'#d88d42');k.box(3.5,1.9,-2.04,.5,.28,.04,'#a98049');flame(k,3.5,.95,-1.95,.15);
  for(let i=0;i<6;i++)k.box(.55+i*.18,1.55,-2.96,.08,.45,.035,'#c3c39a');
  pipe(k,[[-5.4,3.1,2.4],[-5.4,3.7,2.4],[-5.4,3.7,-4.55],[1,3.7,-4.55],[1,3.4,-3.65]],.2,'#586958');
  pipe(k,[[-5.45,.7,2.4],[-4.55,.7,2.4],[-4.25,.4,2.65],[-4.25,.2,3.3]],.18,'#646653');
  pipe(k,[[3.5,2.2,-3.1],[5.55,2.2,-3.1],[6.2,2.2,-3.1]],.25,'#587363');
  pipe(k,[[-.25,.45,-3.5],[-.25,.8,-3.5],[-1,.8,-3.5],[-1,.8,-4.7],[-1,2.5,-4.7],[-.4,2.5,-4.7]],.15,'#707569');
  pipe(k,[[.7,.4,-2.2],[.7,.55,-2.2],[-.2,.55,-2.2],[-.2,.55,-4.7]],.19,'#707569');
  k.box(3.5,.12,-3.1,3.2,.24,2.8,'#8d7861');
  // The open coal bay, its timber lip, individual coal lumps and scattered dust.
  const coal=[];for(let i=0;i<100;i++){const x=.2+(i%14)*.39,z=2.7+Math.floor(i/14)*.22;coal.push({x,y:.18+Math.sin(i*3.6)*.12,z,w:.48,h:.4,d:.42,rot:i*1.7,color:i%3?'#33352e':'#44463b'});}batch(k,coal);
  k.box(2.8,.4,2.45,5.9,.75,.14,'#806e55',{solid:true});k.box(-.12,.4,3.9,.14,.75,2.9,'#806e55',{solid:true});
  k.line([[2.2,.16,-1.8],[2.7,1.7,-1.5]],'#b3a281',.035);k.box(2.17,.15,-1.79,.28,.05,.38,'#c5bb9b');k.line([[-4.8,.83,-3.65],[-4.75,2.1,-3.65]],'#b0a482',.035);k.box(-4.8,.85,-3.65,.23,.06,.3,'#b9b290');
  barrel(k,5.7,-.9,.34,.75);sack(k,-3.9,-4.5,.25,.52,.8,'#796752');inspect(k,'대형 보일러',3.5,1.4,-2,'석조 벽을 따라 연결된 배관과 석탄 화로입니다.');k.features.push('석탄 저장 구역 · 세 종류의 보일러 · 굽은 배관과 이음쇠 · 삽 · 난간과 계단');
}

function mansion(k) {
  room(k,18,16,{floor:'#c6b795',wall:'#a4a282',tile:'stone',height:7});
  const bands=[];for(const x of [-8,-4,0,4,8]){bands.push({x,y:3.5,z:-7.82,w:.26,h:7,d:.16,color:'#bd9381'});bands.push({x,y:.4,z:-7.7,w:4,h:.14,d:.2,color:'#bf9683'});}
  batch(k,bands);k.platform(0,3.2,-5.8,18,4.3,'#bd9484');k.box(0,3.24,-5.8,17.4,.04,3.5,'#a33448');
  stairsZ(k,-6,3.8,2.35,10,.16,.29,'#bd9a87');k.box(-6,.04,2.3,2.05,.08,3.2,'#a02d42');
  k.platform(-6,1.6,.075,3.4,1.75,'#c5ad88');k.box(-6,1.63,.075,2.5,.04,1.65,'#a52d43');stairsZ(k,-6,-.8,2.35,10,.16,.29,'#bd9a87',1.6);
  for(let i=0;i<10;i++){k.box(-6,(i+1)*.16+.014,3.8-(i+.5)*.29,2.05,.02,.3,'#ad354b');k.box(-6,1.6+(i+1)*.16+.014,-.8-(i+.5)*.29,2.05,.02,.3,'#ad354b');}
  railing(k,-7.4,3.75,-7.4,.75,0,'#d2b796');railing(k,-4.6,3.75,-4.6,.75,0,'#d2b796');railing(k,-4.6,-.8,-4.6,-3.7,1.6,'#d2b796');
  railing(k,-3.8,-3.65,8.8,-3.65,3.2,'#d2b796');
  for(const x of [-7.7,-3.5,.5,4.5]){door(k,x,-7.68,1.55,3.5,'#ede5b5');k.box(x,4.55,-7.53,.045,2.1,.07,'#c2bb92');k.box(x,4.7,-7.52,1.48,.07,.07,'#c2bb92');k.torus(x,5.56,-7.49,.32,.045,'#c2bb92',[0,0,0]);}
  door(k,7,-7.64,2,3.2,'#c7bc60');k.torus(7,4.4,-7.5,.59,.065,'#a69649',[0,0,0]);k.box(7,4.4,-7.48,.045,2.2,.04,'#a69649');
  // Recessed guardian alcove with an arched sculpted lintel.
  k.box(4.25,1.45,-6.95,2.4,2.9,.35,'#514d43',{solid:true});door(k,4.25,-6.65,2.5,0,'#b79581');k.box(4.25,1.35,-6.5,1.86,2.6,.08,'#515748');statue(k,4.25,-5.65,0,1.5);k.torus(4.25,2.94,-6.45,.46,.065,'#7a6656',[0,0,0]);
  for(const p of [[-5,4.2],[-1.2,4.2],[2.8,5.2]])statue(k,p[0],p[1],0,1);
  for(const x of [-6,-2,2,6])for(const y of [2.4,5.7]){sconce(k,x,y,-7.48);sconce(k,x+.22,y,-7.47);}
  const carpet=[];for(let i=0;i<14;i++)carpet.push({x:Math.sin(i*.53)*3.4,y:.025,z:-.7+i*.5,w:8.7,h:.025,d:.52,color:i%2?'#c19d8d':'#cba697'});batch(k,carpet);
  for(const p of [[-2,3,1],[1,1.2,1.2],[2.2,3,.25],[-3,1,.3]])k.torus(p[0],.048,p[1],p[2],.027,'#68564a');
  frame(k,-1.5,1.8,-7.5,1,1.8,'#687d68');inspect(k,'수호상',4.25,1.1,-5.3,'장식 문양을 새긴 아치와 녹색 수호상이 있는 저택입니다.');k.features.push('붉은 계단 카펫 · 두 층의 회랑 · 아치 창과 촛대 · 녹색 수호상 · 바닥 원형 문양');
}

function academy(k) {
  const w=26,d=23,level=3.6;room(k,w,d,{floor:'#aa9782',wall:'#d99e7e',height:18});
  const floor=[],columns=[],trim=[];
  // Ground floor medallion tiles and four complete open gallery levels.
  for(let x=-12.5;x<13;x++)for(let z=-11;z<11.5;z++)floor.push({x,y:.018,z,w:.99,h:.028,d:.99,color:Math.abs(x)<8&&z>0&&z<8&&((Math.round(x)+Math.round(z))%5===0)?'#ad7260':'#ad9e86'});
  for(let l=0;l<=4;l++){
    const y=l*level;
    if(l>0){k.platform(0,y,-8.45,26,6,'#b6a185');
      // Open stairwell: side strips and end landings support the gallery without
      // placing a ceiling slab through the ascending character's head.
      k.platform(-12.5,y,0,1,10.1,'#b6a185');k.platform(-10.5,y,0,.4,10.1,'#b6a185');k.platform(-8.3,y,0,.6,10.1,'#b6a185');
      k.platform(-10.4,y,5.75,5.2,1.4,'#b6a185');k.platform(-10.4,y,-5.75,5.2,1.4,'#b6a185');
      k.platform(10.5,y,0,5,11,'#b6a185');
      for(let x=-12.5;x<13;x++)for(let z=-11;z<=-6;z++)floor.push({x,y:y+.018,z,w:.99,h:.025,d:.99,color:(Math.round(x+z)%2)?'#e8dfc0':'#524d41'});
      for(const xx of [-10.5,10.5])for(let x=xx-2;x<xx+2.5;x++)for(let z=-5;z<6;z++){if(xx<0&&x>-12.4&&x<-8.6&&z>-5&&z<5)continue;const side=xx<0&&x>-9&&Math.abs(z)<5;floor.push({x:side?-8.3:x,y:y+.018,z,w:side?.59:.99,h:.025,d:.99,color:(Math.round(x+z)%2)?'#e8dfc0':'#524d41'});}
      railing(k,-8,-5.5,8,-5.5,y,l===4?'#d0c7ad':'#605e4d');railing(k,-8,-5.5,-8,5.5,y,'#605e4d');railing(k,8,-5.5,8,5.5,y,'#605e4d');
      // Guard the flat switchback landings while keeping both tread entrances
      // and the back-gallery route open. Slots match the existing stair rails.
      landingGuard(k,-12.96,6.4,-7.86,6.4,y);
      landingGuard(k,-7.86,6.4,-7.86,5.62,y);
      landingGuard(k,-7.86,5.62,-8,5.5,y);
      for(const z of [-5.08,5.08])for(const [left,right] of [[-12.96,-12.19],[-10.71,-10.24],[-8.76,-8.02]])landingGuard(k,left,z,right,z,y);
      trim.push({x:0,y:y-.18,z:-5.5,w:16,h:.2,d:.18,color:'#947764'},{x:-8,y:y-.18,z:0,w:.18,h:.2,d:11,color:'#947764'},{x:8,y:y-.18,z:0,w:.18,h:.2,d:11,color:'#947764'});
    }
    for(const x of [-11.8,-7.5,-3.8,0,3.8,7.5,11.8]){
      k.cylinder(x,y+1.6,-5.9,l===0?.2:.16,3.2,'#9fa08c');k.cylinder(x,y+.12,-5.9,.3,.24,'#b4af94');k.cylinder(x,y+3.24,-5.9,.28,.16,'#b4af94');k.torus(x,y+.32,-5.9,.23,.04,'#8e907d');
      roundSolid(k,x,-5.9,l===0?.2:.16,y+.16,3.2);roundSolid(k,x,-5.9,.3,y,.24);
    }
    for(const x of [-8,8])for(const z of [0,5.5]){k.cylinder(x,y+1.6,z,.16,3.2,'#9fa08c');k.cylinder(x,y+.12,z,.3,.24,'#b4af94');k.cylinder(x,y+3.24,z,.28,.16,'#b4af94');roundSolid(k,x,z,.16,y+.16,3.2);roundSolid(k,x,z,.3,y,.24);}
    if(l<4){for(const x of [-9,-5,0,5,9])door(k,x,-11.22,1.55,y,'#ad795a');for(const x of [-7,-2,3,7])sconce(k,x,y+2.05,-11.07);}
    else{
      for(const x of [-6,6]){k.cylinder(x,y+1.75,-8.4,.65,3.5,'#96968a',{solid:true});k.cylinder(x,y+.15,-8.4,.84,.3,'#7b7c72');k.torus(x,y+.5,-8.4,.74,.09,'#999d8d');k.torus(x,y+3.1,-8.4,.7,.09,'#7a7e71');}
      stairsZ(k,0,-5.9,8,4,.13,.36,'#656253',y);k.platform(0,y+.52,-8.8,8,4.2,'#b7a989');
      door(k,0,-11.16,2.35,y+.52,'#624e59');k.box(0,y+1.95,-11.02,1.8,2.2,.03,'#775468');
      const windowColors=['#89aa8e','#d7958e','#bea779','#80a3a3'];for(const x of [-10,-8,8,10]){door(k,x,-11.14,1.1,y+.6,'#b2b18b');for(let q=0;q<4;q++)k.box(x-.37+q*.25,y+1.85,-10.97,.23,1.45,.025,windowColors[q]);}
    }
    trim.push({x:0,y:y+3.45,z:-11.3,w:26,h:.15,d:.14,color:'#9a7c65'});
  }
  batch(k,floor);batch(k,columns);batch(k,trim);
  // Each flight joins a landing exactly at the gallery surface height.
  for(let l=0;l<4;l++){
    const y=l*level,dir=l%2?-1:1,start=l%2?5.1:-5.1,sx=l%2?-9.5:-11.45;
    // Adjacent switchback lanes prevent one flight's surface from being picked
    // while descending the flight directly below it in the opposite direction.
    stairsZ(k,sx,start,1.45,24,.15,.425,'#b78f76',y,dir);
    for(let i=0;i<=24;i++){const z=start+dir*i*.425,yy=y+i*.15;for(const side of [-1,1])k.cylinder(sx+side*.74,yy+.47,z,.023,.95,'#554e45');}
    for(const side of [-1,1])k.line([[sx+side*.74,y+.95,start],[sx+side*.74,y+level+.95,start+dir*10.2]],'#554e45',.045);
    for(let i=0;i<24;i++)for(const side of [-1,1])k.collide(sx+side*.74,start+dir*(i+.5)*.425,.075,.445,{y:y+i*.15,h:1.25});
  }
  // Ground hall wainscoting, elaborate entrance doors, bulletin board and clock.
  const panels=[];for(let x=-12.4;x<13;x+=.24)panels.push({x,y:.68,z:-11.15,w:.18,h:1.3,d:.13,color:'#b8a076'});batch(k,panels);
  for(const p of [[-5,'#79805b'],[0,'#978f73'],[5,'#9f4439']])door(k,p[0],-11.02,2.05,0,p[1]);
  k.box(-8.5,1.8,-11.01,2.5,1.15,.12,'#668267');for(let i=0;i<5;i++)k.box(-9.3+i*.37,1.83+(i%2)*.08,-10.92,.32,.44,.025,'#ebe6c9');
  k.box(8.7,1.35,-10.95,.58,2.7,.32,'#695642',{solid:true});k.cylinder(8.7,2.46,-10.68,.31,.08,'#e9dfb8',{segments:24});k.torus(8.7,2.46,-10.58,.29,.035,C.brass,[0,0,0]);k.line([[8.7,2.46,-10.54],[8.7,2.62,-10.54]],'#423f35',.015);k.line([[8.7,2.46,-10.54],[8.83,2.4,-10.54]],'#423f35',.015);
  inspect(k,'학원 게시판',-8.5,1.8,-10.7,'여러 층의 회랑과 계단을 직접 올라가며 학원 내부를 탐험할 수 있습니다.');k.features.push('4개 상층 회랑 · 연결 계단 96단 · 체크 무늬 바닥 · 황동 난간 · 기둥 · 스테인드글라스 · 게시판과 시계');
}

function library(k) {
  room(k,17,14,{floor:'#c1bca8',wall:'#93aea4',height:6.4});
  const rings=[];for(let x=-7.9;x<8.4;x+=.82)for(let z=-6.3;z<7;z+=.82)rings.push({x,y:.025,z,w:.29,h:.29,d:.29,rx:Math.PI/2,color:'#a19786'});instances(k,new k.THREE.TorusGeometry(1,.045,4,16),rings);
  k.platform(3.1,2.7,-4.1,10.6,5.8,'#c6c3ae');k.box(3.1,2.56,-1.2,10.6,.2,.16,'#afa58d');
  for(const x of [-1.8,3.1,7.9]){k.cylinder(x,1.32,-1.28,.095,2.65,'#7d826b');roundSolid(k,x,-1.28,.095,-.005,2.65);}
  bookcase(k,3.25,-6.56,9.7,3.5,0,2.7,2);bookcase(k,7.95,-4.1,4.8,2.5,Math.PI/2,0,7);
  bookcase(k,-.6,.1,5.7,2.05,0,0,3);bookcase(k,3.4,3.1,5.7,2.05,0,0,1);
  stairsZ(k,-5,-.8,3.05,10,.135,.24,'#cdcbb7');k.platform(-5,1.35,-4,4.4,1.5,'#c5c7b2');stairsZ(k,-4.65,-4.65,1.5,9,.15,.19,'#bfc2ac',1.35);
  k.box(-4.65,2.62,-6.39,1.5,.16,.08,'#bfc2ac');k.surface(-4.65,-6.39,1.5,.08,2.7);
  k.platform(-3.2,2.7,-6.7,3.2,.6,'#c6c3ae');
  ladder(k,2,-6.25,3.5,2.7);ladder(k,5.8,-6.25,3.5,2.7);
  for(const p of [[-7,2],[-5.3,2.5]]){table(k,p[0],p[1],1.1,.8);chair(k,p[0],p[1]+.7,0);}
  k.box(-6,.49,2.2,3.2,.98,1.3,'#8c7752',{solid:true});k.cylinder(-7.65,.99,2.2,.65,.12,'#b59e73');k.cylinder(-4.35,.99,2.2,.65,.12,'#b59e73');
  for(let i=0;i<6;i++)k.box(-7.3+i*.19,1.18,2.25,.15,.34,.22,['#806f69','#688574','#aaa581'][i%3]);k.box(-5.4,1.055,2.34,.5,.05,.38,'#e5dabc');plant(k,-4.7,2.25,1.05,.5);
  const shelf=[];for(const y of [.7,1.6,2.5,3.4,4.3,5.2])shelf.push({x:-8.28,y,z:0,w:.09,h:.055,d:14,color:'#9b7d60'});batch(k,shelf);
  for(const p of [[-6.8,2.25,1.7],[-6.6,3.9,1.3],[-2.2,4.4,1.5]])frame(k,p[0],p[1],-6.82,p[2],1.1,'#b6b393');
  for(const p of [[-2.6,1.9,1.4],[1.2,1.9,1.1],[4.4,1.9,.8]])frame(k,-8.32,p[1],p[0],p[2],1.1,'#b6b393',Math.PI/2);
  k.box(-2.25,1.45,-2.5,.5,2.9,.38,'#8a755b',{solid:true});k.torus(-2.25,2.6,-2.27,.23,.035,C.brass,[0,0,0]);k.sphere(-2.25,2.6,-2.26,.22,'#e8e5cc',[1,1,.08]);k.line([[-2.25,2.6,-2.21],[-2.25,2.74,-2.21]],'#645e48',.013);k.line([[-2.25,2.6,-2.21],[-2.11,2.54,-2.21]],'#645e48',.013);
  inspect(k,'도서 검색',-.6,1.2,.45,'책등, 금빛 라벨, 이동 사다리가 있는 서가입니다. 상층 열람 구역까지 계단이 연결됩니다.');k.features.push('수백 권의 입체 책 · 상층 서가와 사다리 · 두 구간 계단 · 원형 타일 무늬 · 대출 데스크 · 벽 그림과 괘종시계');
}

function peStorage(k) {
  room(k,12,10,{floor:'#868476',wall:'#615f53',height:3.6});
  const wall=[];for(let x=-5.8;x<6;x+=.19)wall.push({x,y:1.7,z:-4.86,w:.012,h:3.3,d:.012,color:'#48493f'});batch(k,wall);
  for(const x of [-3.3,1]){k.box(x,2.2,-4.82,2.4,.85,.05,'#d9ded3');for(const y of [1.75,2.62])k.box(x,y,-4.73,2.65,.065,.09,'#817a65');k.box(x,2.2,-4.72,.075,.82,.1,'#706b58');k.line([[x-1.35,1.7,-4.65],[x+1.3,2.7,-4.65]],'#a1967b',.025);k.line([[x-1.3,2.68,-4.65],[x+1.3,2.9,-4.65]],'#a1967b',.025);}
  pipe(k,[[-5.8,3.25,-4.65],[5.8,3.25,-4.65]],.08,'#5b594c');
  bench(k,-3.7,-2.3,3.8,.3);table(k,-.8,-3.1,2.8,.8);crate(k,-.5,-3.1,.8,.7,.65,.83);
  const shelf=[];for(const yy of [.08,.85,1.62,2.39,3.16])shelf.push({x:4.55,y:yy,z:-3.9,w:2.3,h:.12,d:1,color:'#8d795a'});for(const x of [3.4,5.7])shelf.push({x,y:1.65,z:-3.9,w:.1,h:3.3,d:1,color:'#685c47'});batch(k,shelf);k.collide(4.55,-3.9,2.4,1,{h:3.3});
  function ball(x,y,z,r,type='basket') {k.sphere(x,y,z,r,type==='football'?'#cbcec0':'#8b6651');for(let i=0;i<3;i++)k.torus(x,y,z,r+.003,.009,'#4a4a3e',i===0?[0,0,0]:i===1?[Math.PI/2,0,0]:[0,Math.PI/2,0]);if(type==='football')for(let i=0;i<5;i++)k.sphere(x+Math.sin(i*2.4)*r*.6,y+Math.cos(i*2.4)*r*.6,z+r*.7,r*.24,'#535b50',[1,1,.18]);}
  ball(4.1,1.98,-3.7,.25,'football');ball(5.07,1.94,-3.7,.22);ball(4.6,2.69,-3.8,.26);ball(-3.8,.22,-2.8,.22,'football');ball(1.5,.23,-2.8,.24);ball(-1.7,.1,1,.1,'football');ball(-4.8,.1,3.2,.11);ball(-.2,.89,-3,.1,'football');
  crate(k,-4.9,2.4,.7,.7,.7);for(let i=0;i<4;i++){k.line([[-5.1+i*.16,.3,2.4],[-5.2+i*.2,1.45+i*.07,2.4]],'#968c72',.035);k.sphere(-5.2+i*.2,1.5+i*.07,2.4,.065,'#a39578',[1,1.6,1]);}
  // Athletics hurdle with a striped top bar, freestanding feet and metal uprights.
  batch(k,[{x:3,y:1.05,z:-.9,w:2.2,h:.25,d:.11,color:'#cccbbc'},{x:2.08,y:.48,z:-.9,w:.065,h:.93,d:.065,color:'#77796b'},{x:3.92,y:.48,z:-.9,w:.065,h:.93,d:.065,color:'#77796b'},{x:2.08,y:.06,z:-.9,w:.13,h:.1,d:.75,color:'#6b6e61'},{x:3.92,y:.06,z:-.9,w:.13,h:.1,d:.75,color:'#6b6e61'}]);for(const x of [2.2,2.9,3.6])k.box(x,1.05,-.831,.33,.245,.015,'#555d59');k.collide(3,-.9,2.3,.7,{h:1.18});
  k.platform(2.5,.16,2.25,5.8,3.4,'#807d6e');k.box(2.5,.08,2.25,5.8,.16,3.4,'#63655b');
  const litter=[];for(let i=0;i<16;i++)litter.push({x:-4.8+(i*2.71)%10,y:.03,z:-.8+(i*1.31)%5.1,w:.13+(i%4)*.08,h:.008,d:.16,rot:i*1.7,color:i%3?'#babdb3':'#a5a99f'});batch(k,litter);
  for(let i=0;i<4;i++)k.box(2.3+i*.34,.21,3.6,.12,.16,2.1,'#6b5e46',{rot:-.7+i*.4});
  frame(k,5.55,2.1,-2.95,1.1,1.7,'#b4b3a2');k.text('WANTED',5.55,2.6,-2.88,{width:.83,height:.15,color:'#636454',background:'transparent'});inspect(k,'체육 기구',3,1.05,-.6,'허들, 축구공, 농구공, 야구 배트와 체육용 매트가 모여 있습니다.');k.features.push('기울어진 벤치 · 공 선반 · 줄무늬 허들 · 배트 상자 · 낮은 매트 단상 · 구겨진 종이 · 창틀과 배관');
}

function restaurant(k) {
  room(k,14,11,{floor:'#a99d8d',wall:'#b2a085',tile:'wood',height:4.5,brick:true});
  k.platform(2.7,.18,-2.1,7.2,5.8,'#b6ac91');k.box(2.7,.09,-2.1,7.2,.18,5.8,'#867961');
  // Brick dome kiln, recessed arched fire door, flue, burner and ventilation hood.
  k.cylinder(1.2,.35,-4,1.5,.7,'#b39a77',{segments:24,solid:true});k.sphere(1.2,1.2,-4,1.5,'#b79872',[1,.85,1]);k.cylinder(1.2,2.35,-4,.43,.5,'#777967');k.cylinder(1.2,3.3,-4,.21,1.7,'#777967');
  roundSolid(k,1.2,-4,1.5,0,2.35);
  for(const y of [.65,1.2,1.65])k.torus(1.2,y,-4,1.45-Math.max(0,y-.8)*.5,.027,'#806f59');k.box(1.2,.94,-2.54,.85,1.05,.04,'#664b30');k.sphere(1.2,1.46,-2.55,.44,'#664b30',[1,1,.08]);k.box(1.2,.97,-2.5,.68,.8,.025,'#ffce73');k.sphere(1.2,1.35,-2.5,.34,'#ffc66f',[1,1,.06]);flame(k,1.2,.75,-2.43,.24);
  for(let i=0;i<3;i++)k.box(1.2,.15+i*.16,-2.1-i*.23,1.05,.15,.28,'#ad9878');
  table(k,-3.5,-3.75,3,1,.18,'#baac86');k.cylinder(-4.05,1.15,-3.75,.42,.5,'#846c48');k.torus(-4.05,1.42,-3.75,.42,.035,'#c0a773');k.line([[-4.12,1.4,-3.7],[-4.25,1.88,-3.7]],'#baa079',.025);k.cylinder(-2.8,1.05,-3.75,.38,.1,'#594d3c');k.cone(-2.8,1.2,-3.75,.34,.2,'#856e4d');
  k.box(-3.6,2.64,-4.75,1.4,.22,.75,'#756f59');k.cone(-3.6,2.3,-4.53,.9,.7,'#858675',4);k.cylinder(-3.6,3.5,-4.75,.16,1.6,'#777b68');
  pipe(k,[[1.6,1.9,-4],[3.3,1.9,-4],[3.7,1.5,-4],[3.7,.35,-4]],.21,'#888977');pipe(k,[[-.2,1.2,-4],[-.9,1.2,-4],[-1.2,.95,-4]],.1,'#7e8c70');
  for(const x of [3.6,4])lathe(k,x,.18,-3.65,.65,.17,'#a59a7c','jar');
  for(const p of [[-3,1.1],[-.2,-.65]]){table(k,p[0],p[1],2.75,1.05);bench(k,p[0],p[1]+.85,2.6);bench(k,p[0],p[1]-.85,2.6);for(const xx of [p[0]-1.65,p[0]+1.65])chair(k,xx,p[1],xx<p[0]?Math.PI/2:-Math.PI/2);}
  // Pantry rack: bowls, plate stacks, grain sacks, folded towels and hanging pans.
  const rack=[];for(const y of [.3,1.05,1.8,2.55])rack.push({x:5.6,y,z:-1.6,w:2.1,h:.09,d:.85,color:'#88775d'});for(const x of [4.55,6.65])rack.push({x,y:1.5,z:-1.6,w:.09,h:3,d:.9,color:'#695b47'});batch(k,rack);k.collide(5.6,-1.6,2.2,1,{y:.18,h:3});
  for(let i=0;i<10;i++)k.cylinder(4.9+(i%5)*.3,1.86+(Math.floor(i/5)*.08),-1.55,.13,.045,'#c7c1a4');for(let i=0;i<4;i++)lathe(k,4.95+i*.39,1.13,-1.6,.32,.14,['#9aafa5','#b4bca8','#bac0a3','#8ba49c'][i],'jar');sack(k,5.2,-1.6,.28,.48,2.6);sack(k,5.9,-1.6,.3,.46,2.6);
  for(let i=0;i<3;i++)k.box(5.9,2.67+i*.055,-1.55,.62,.045,.5,'#e0d7ba');table(k,5,-4.35,2.8,.7,.18);for(let i=0;i<5;i++)lathe(k,4.1+i*.33,1.02,-4.35,.23,.09,'#c5c6ad','jar');
  k.box(5,2.25,-5.34,2.7,1.1,.15,'#695c48');for(let i=0;i<7;i++)k.box(5,1.78+i*.145,-5.2,2.4,.075,.06,'#987a58');
  barrel(k,-6,2,.42,.9);barrel(k,6.3,-3.9,.35,.82,.18);cylinder(k,4.75,.52,.65,.39,.75,'#9b805b',[0,0,Math.PI/2]);k.torus(4.42,.52,.65,.39,.035,'#6c6049',[0,Math.PI/2,0]);k.collide(4.75,.65,.78,.78,{y:.13,h:.78});
  k.box(-5.8,.5,-1.1,1.8,.68,.9,'#9c795c',{solid:true});k.sphere(-5.8,.89,-1.1,.92,'#a88766',[1,.5,.5]);k.box(-5.8,.76,-.61,1.4,.06,.05,C.brass);k.box(-5.8,.66,-.6,.22,.19,.05,C.brass);for(const x of [-6.3,-5.3])k.torus(x,.79,-.59,.1,.025,C.brass,[0,0,0]);
  k.box(-5.55,2.4,-5.28,2.5,.09,.52,'#987857');for(const x of [-6.4,-6.05])lathe(k,x,2.44,-5.3,.3,.095,'#8b8d6a','bottle');k.box(-5.2,2.55,-5.32,.6,.28,.34,'#bcb296');
  inspect(k,'벽돌 오븐',1.2,1,-2,'벽돌 돔 오븐의 불빛과 조리대, 식기 선반이 있는 식당입니다.');k.features.push('벽돌 돔 오븐 · 연통과 환기 후드 · 냄비와 국자 · 두 식탁과 의자 · 식기와 수건 선반 · 식량 상자와 통');
}

function sauna(k) {
  room(k,27,19,{floor:'#c4d0cb',wall:'#bccdcc',tile:'tile',height:3.3});
  woodFloor(k,-8.1,2,9.4,12);woodFloor(k,-8.1,-6,9.4,3.9);
  const partitions=[[-3.3,2,.12,1.35,11],[-8.1,-3.95,9.4,1.45,.12],[-8.1,8,9.4,1.35,.12],[.35,-2,1.7,1.05,.12],[6.85,-2,4.3,1.05,.12],[12,-2,1,1.05,.12]];
  for(const [x,z,w,h,d] of partitions){k.box(x,h/2,z,w,h,d,'#91b9b1',{solid:true});k.box(x,h+.04,z,w+.06,.08,d+.06,'#536f69');}
  for(let i=0;i<8;i++){const x=-10.8+(i%2)*4.2,z=-1.85+Math.floor(i/2)*2.55;k.box(x,.12,z,2.8,.23,1.5,'#f2f1d6',{solid:true});k.box(x+.8,.36,z,1.1,.3,1.22,'#e7c532');cylinder(k,x+.35,.37,z,.28,1.23,'#faf4d8',[Math.PI/2,0,0]);for(let q=0;q<2;q++)k.torus(x+.35,.37,z+(q?-.63:.63),.19,.035,'#d2d6b8',[0,0,0]);k.interactions.push({name:'휴식 매트',position:[x,.25,z],kind:'seat',text:'폭신한 매트와 말아 둔 노란 수건입니다.'});}
  for(const x of [-11,-6.3]){k.box(x,1.5,-9.27,1.4,.8,.07,'#665f45');k.box(x,1.5,-9.2,1.22,.63,.025,'#f2f2d5');k.box(x,1.5,-9.17,.06,.65,.03,'#a4a18a');}
  k.sphere(-8.1,.9,-7.1,1.25,'#aa8550',[1,.85,.8]);k.box(-8.1,.49,-6.17,.75,.8,.04,'#493a27');flame(k,-8.1,.55,-6.12,.28);k.cylinder(-8.1,2.3,-7.1,.12,1.6,'#8b805c');for(const x of [-9.8,-6.5]){k.box(x,.23,-6.9,.9,.3,.8,'#d4bb5d');for(let i=0;i<4;i++)k.sphere(x-.3+i*.19,.4,-6.9,.09,'#f1c953');}
  k.collide(-8.1,-7.1,2.5,2,{y:0,h:1.97});
  // Raised pools have actual rims, water geometry, steps and ripple animation.
  const waterMat=new k.THREE.MeshStandardMaterial({color:'#81b9bc',transparent:true,opacity:.76,roughness:.17,metalness:.15});
  function pool(x,z,w,d,y){k.box(x,y-.15,z,w,.3,d,'#a9bab5');k.box(x,y+.13,z-d/2,w,.3,.25,'#d5dfc9',{solid:true});k.box(x,y+.13,z+d/2,w,.3,.25,'#d5dfc9',{solid:true});k.box(x-w/2,y+.13,z,.25,.3,d,'#d5dfc9',{solid:true});k.box(x+w/2,y+.13,z,.25,.3,d,'#d5dfc9',{solid:true});k.box(x,y+.01,z,w-.3,.035,d-.3,'#82bfc0',{material:waterMat});k.surface(x,z,w-.5,d-.5,y-.12);k.collide(x,z,w,d,{y:-1,h:y-.01});for(let i=0;i<4;i++)k.torus(x+(i-1.5)*w*.16,y+.055,z+Math.sin(i*2)*.3,.26+i*.07,.007,'#c3e3dc');inspect(k,'온탕',x,y+.4,z,'타일로 둘러싼 따뜻한 온탕입니다.');}
  k.platform(3.2,.6,-6.05,8,5.9,'#d4dfd4');pool(3.2,-6.7,6,3.6,.6);stairsZ(k,3.2,-1.9,3,4,.15,.3,'#b6c2b1');
  k.platform(10.2,.3,-5.5,5.8,6,'#d5dfd4');pool(10.2,-6.1,4.4,3.8,.3);stairsZ(k,10.2,-1.9,2,2,.15,.3,'#b9c5b4');
  // Three individual shower screens with metal shower heads and yellow towels.
  for(let i=0;i<3;i++){const x=7.4+i*1.9,z=-.1;k.box(x,1.24,z,1.8,2.48,.055,'#d5e8db');k.box(x-.9,1.24,z+.85,.055,2.48,1.7,'#d5e8db');for(const xx of [x-.9,x+.9])k.cylinder(xx,1.24,z,.035,2.48,'#b4b888');k.box(x,2.47,z,1.9,.065,.065,'#b9bc8e');pipe(k,[[x+.4,.2,z-.12],[x+.4,2.5,z-.12],[x+.4,2.5,z+.3]],.025,'#83aaa5');k.sphere(x+.4,2.48,z+.34,.13,'#91b8b0',[1,.2,1]);k.box(x,.9,z+.08,.55,.68,.045,'#efda49');k.line([[x-.33,1.25,z+.13],[x+.33,1.25,z+.13]],'#aeb777',.02);k.collide(x,z,1.8,.13,{h:2.5});}
  table(k,3.5,3.1,5.2,2,.05,'#a77642');bench(k,3.5,4.55,5.1,0,0,'#a77642');bench(k,3.5,1.65,5.1,0,0,'#a77642');
  for(const p of [[-.8,-1.7],[7,-1.7]]){table(k,p[0],p[1],2.2,.55);lathe(k,p[0]-.6,.84,p[1],.37,.09,'#ba7386','bottle');lathe(k,p[0]-.35,.84,p[1],.3,.08,'#ddd7b7','bottle');k.box(p[0]+.5,.84,p[1],.38,.035,.26,'#d2bc8e');plant(k,p[0]+1.6,p[1],0,1.2);}
  k.box(1,.4,-2.4,1.8,.8,.9,'#866443',{solid:true});for(let i=0;i<4;i++)k.box(.55+i*.27,.85,-2.4,.4,.1,.5,['#74bac2','#8abfc1'][i%2]);
  k.box(-1.4,.26,5.1,3.3,.5,1.5,'#8b6850',{solid:true});k.box(-1.4,.52,5.1,2.8,.025,1.02,'#5c8a79');plant(k,-3.25,5.1,0,.8);
  // Rock garden at the entrance: paving stones, fountain, cypress and shrubs.
  k.platform(6.5,0,7.5,9,3,'#88956a');for(let i=0;i<19;i++)k.sphere(2.5+(i*1.7)%8,.025,6.3+(i*.83)%2.2,.2+(i%3)*.1,'#c9c4a0',[1,.2,.7]);for(const p of [[4,8.5],[10.1,7.5],[8.8,8.6]]){plant(k,p[0],p[1],0,1.5);for(let i=0;i<4;i++)k.sphere(p[0]+Math.sin(i)*.35,.2,p[1]+Math.cos(i)*.35,.37,'#657b52',[1,.8,1]);}
  k.cylinder(7.7,.16,7.4,.85,.3,'#969e7b');k.cylinder(7.7,.31,7.4,.65,.06,'#729f91');for(let i=0;i<6;i++)k.sphere(7.7+Math.sin(i)*.28,.47+i*.075,7.4+Math.cos(i)*.2,.23,'#92987a',[1,.55,1]);
  k.features.push('8개 휴식 매트 · 노란 수건 · 석조 난로 · 두 온탕과 계단 · 3개 샤워실 · 세면용품 · 중앙 벤치 · 입구 돌 정원');
}

function science(k) {
  room(k,14,11,{floor:'#c0c5a7',wall:'#b1c8b4',height:4.1});
  k.platform(4,.38,-1.8,5.8,5.8,'#cbd0b4');stairsZ(k,3.6,1.85,5.7,3,.1267,.26,'#b1b99c');
  const panel=[];for(let x=-6.8;x<7;x+=.26)panel.push({x,y:.64,z:-5.31,w:.19,h:1.2,d:.14,color:'#8b8b61'});batch(k,panel);
  function drawers(x,z,w=2.15,h=3.3){k.box(x,h/2,z,w,h,.55,'#6c8e80',{solid:true});const a=[];for(let row=0;row<7;row++)for(let col=0;col<3;col++){const xx=x-w/2+.13+col*w/3+w/6,yy=.22+row*.45;a.push({x:xx,y:yy,z:z+.31,w:w/3-.065,h:.4,d:.06,color:'#92b3a2'});a.push({x:xx,y:yy+.07,z:z+.37,w:.08,h:.07,d:.03,color:'#425f51'});if((row+col)%5===1){a.push({x:xx,y:yy-.09,z:z+.52,w:w/3-.1,h:.07,d:.5,color:'#81a391'});}}batch(k,a);}
  drawers(-5.55,-4.8);drawers(-2.05,-4.8);
  k.box(-3.85,1.7,-4.9,1.6,3.4,.48,'#728c73');for(const y of [.3,1.4,2.8])k.box(-3.85,y,-4.59,1.6,.085,.62,'#a3af89');
  for(let i=0;i<5;i++)lathe(k,-4.45+i*.28,2.85,-4.55,.38+(i%3)*.2,.11,['#8fb29e','#baa35c','#bbab7a','#c6b990','#8da5a1'][i],'bottle');
  ladder(k,-6,-4.1,2.85);lathe(k,-4.25,.38,-4.55,.8,.19,'#c4bb8c','vase');lathe(k,-3.6,1.46,-4.55,.55,.16,'#b6c8b7','bottle');lathe(k,-3.12,1.46,-4.55,.45,.17,'#d8d5b0','jar');
  table(k,-1.7,-.8,4.3,1.4,0,'#988055');k.box(-1.7,.78,-1.55,3.6,.12,.12,'#745c3d');
  for(const x of [-3.55,.1]){k.cylinder(x,.37,-.8,.13,.55,'#806541');k.sphere(x,.18,-.8,.15,'#826744',[1,.7,1]);}
  // Retort stand, burner, suspended globe, glass pipettes and coiled condenser.
  k.box(-2.95,.85,-.8,.65,.045,.55,'#766953');k.cylinder(-2.95,1.33,-.8,.02,1,'#716c55');k.sphere(-2.95,1.45,-.8,.22,'#d0dbb6');k.torus(-2.95,1.45,-.8,.23,.018,'#9cab74',[0,0,0]);k.cylinder(-2.95,1.15,-.8,.13,.18,'#baaa6d');
  for(let i=0;i<6;i++)k.cylinder(-2.35+i*.17,1.03,-.83,.025,.32+(i%3)*.07,['#aabdaf','#c7ccb1','#cfba85'][i%3]);k.box(-1.91,.87,-.83,1.15,.045,.19,'#d2c9a0');
  for(let i=0;i<5;i++)k.torus(-1.66+i*.17,1.47,-1.1,.15,.018,'#c4c9ab',[0,Math.PI/2,0]);pipe(k,[[-2.15,1.45,-1.1],[-2.4,1.6,-1.1]],.025,'#b9c3a3');
  lathe(k,-.7,.85,-.6,.46,.23,'#7e785a','jar');k.cylinder(-.7,1.33,-.6,.21,.025,'#b6ab77');lathe(k,-.15,.85,-1.05,.56,.09,'#a9baa1','bottle');lathe(k,.05,.85,-.4,.23,.12,'#cfcead','jar');
  k.box(-.05,.85,-.95,.75,.04,.49,'#ede1b2');k.box(-.35,.91,-.95,.38,.03,.46,'#e8d9ac',{rot:-.15});k.box(.1,.91,-.95,.38,.03,.46,'#e8d9ac',{rot:.15});
  pipe(k,[[-.1,4,-5.15],[-.1,2.5,-5.15],[-.1,1.7,-5.15],[.7,1.7,-5.15],[.9,1.15,-5.15]],.11,'#9d9d7b');pipe(k,[[-.8,4,-5.15],[-.8,.4,-5.15],[-.45,.4,-5.15]],.08,'#a9a78b');
  barrel(k,1.8,-4.65,.48,.98);lathe(k,2.65,0,-4.65,.9,.17,'#b9c8a9','bottle');
  k.box(.55,2.37,-5.23,.65,1.65,.06,'#e1dcba');k.text('ALCHEMY',.55,2.91,-5.18,{width:.52,height:.1,color:'#8a8f72',background:'transparent'});
  const frames=[];for(let i=0;i<12;i++)frames.push({x:2.2+(i%3)*.56,y:2.05+Math.floor(i/3)*.43,z:-5.21,w:.39,h:.32,d:.055,color:['#b29264','#b6a77a','#aaa789'][i%3]});batch(k,frames);
  chair(k,3.85,-3.3,0,.38);for(const s of [-1,1])k.line([[3.85+s*.23,.4,-3.65],[3.85+s*.24,.28,-3.3],[3.85+s*.23,.4,-2.95]],'#6e5137',.035);
  k.box(6,1.2,-4.3,1.6,1.6,.85,'#886c42',{solid:true});door(k,5.62,-3.82,.57,.39,'#636e54',1.22);door(k,6.33,-3.82,.57,.39,'#636e54',1.22);for(let i=0;i<4;i++)lathe(k,5.4+i*.4,2.07,-4.3,.44+(i%2)*.15,.12,['#b06246','#51846a','#507e64','#b7aa7d'][i],'bottle');
  for(const p of [[5.45,-2.4],[6.25,-2.1]])lathe(k,p[0],.38,p[1],.9,.23,'#d1d0a6','vase');
  k.box(0,.035,3.2,2.8,.025,1.7,'#ad6543');for(let i=0;i<4;i++)k.torus(0,.055,3.2,.25+i*.16,.018,'#c18754');
  k.box(2.9,.52,3.7,2.65,.5,.83,'#854a36',{solid:true});k.box(2.9,.93,4.03,2.6,.8,.16,'#9a5740');for(const x of [1.6,4.2])k.sphere(x,.84,3.7,.22,'#a56645',[.5,.8,1.6]);k.interactions.push({name:'연구실 소파',position:[2.9,.77,3.6],kind:'seat',text:'둥근 팔걸이와 붉은 가죽 등받이가 있는 소파입니다.'});
  lathe(k,-5.4,0,-1.5,.43,.4,'#967d50');k.torus(-5.4,.44,-1.5,.38,.03,'#c2b98e');k.box(-5.4,.46,-1.5,.48,.045,.42,'#bbae7b');
  inspect(k,'연금술 실험대',-1.7,1,-.3,'유리관, 나선형 응축기, 플라스크, 지구본과 열린 연구 노트가 놓여 있습니다.');k.features.push('약재 서랍 42개 · 열려 있는 서랍 · 유리관과 응축기 · 실험 노트 · 배관 · 흔들의자 · 약병 장식장 · 붉은 소파');
}

function storage(k) {
  room(k,13,11,{floor:'#b7a578',wall:'#ac9b85',height:3.8,brick:true});
  const crates=[[-5.4,1,.9,.8,.9,0],[-3.5,-3.45,1.25,1.2,1,0],[-.8,-4.65,1.65,1.35,1.2,.25],[3.25,-3.9,1.3,1.4,1.1,.65],[3,-2.45,1.55,1.2,1.25,0],[5.4,1.9,1,.85,.9,0],[-.8,4.1,1.1,.9,.85,0]];
  for(const [x,z,w,h,d,y] of crates)crate(k,x,z,w,h,d,y);
  for(const p of [[-5.3,2.35,.4,.95],[-3.5,4,.45,.95],[1.2,-4.6,.43,1],[4.25,2.25,.38,.8]])barrel(k,...p);
  lathe(k,-5.3,0,-2.7,2.3,.67,'#d2d0a5','urn');for(let i=0;i<5;i++)k.sphere(-5.3+Math.sin(i*1.3)*.42,.74+i*.24,-2.2,.18,'#a96848',[.65,1.5,.12]);
  lathe(k,-4.8,0,3.3,1.2,.56,'#594d32','jar');k.torus(-4.8,1.17,3.3,.34,.035,'#c0a866');
  roundSolid(k,-5.3,-2.7,.67,0,2.3);roundSolid(k,-4.8,3.3,.56,0,1.2);
  for(const p of [[-4.4,.15,.3,.8],[-2.9,-4.15,.35,.95],[4.5,-2.65,.48,.8],[3.6,4,.55,1.1],[0,4.8,.43,.8]])sack(k,...p);
  k.box(-.3,.61,-1.45,3.9,.12,.8,'#826448',{solid:true});for(const x of [-1.95,1.35])k.box(x,.29,-1.45,.17,.58,.64,'#73583e');
  k.box(-.65,.65,.6,2.6,1.2,1,'#916546',{solid:true});k.sphere(-.65,1.27,.6,1.3,'#9e7754',[1,.34,.4]);for(const x of [-1.65,.35])k.box(x,.8,1.15,.09,.95,.06,'#c3b58a');k.box(-.65,.75,1.14,.23,.22,.06,'#bdae81');k.line([[-.69,.74,1.2],[-.64,.74,1.2]],'#535346',.026);
  lathe(k,-2.2,0,.7,1.05,.24,'#8c9d79','bottle');lathe(k,4.65,0,-1,1.1,.3,'#b0aa8a','vase');lathe(k,-.75,1.63,-4.4,.56,.25,'#b8b39a','jar');lathe(k,-.08,1.63,-4.4,.65,.18,'#cbc3a0','bottle');
  k.box(-2.05,.52,-4.6,.82,1.04,.7,'#9f6f49');k.box(-2.05,1.03,-4.92,.82,1.2,.13,'#ac7853');for(const x of [-2.42,-1.68])k.box(x,.23,-4.6,.06,.46,.6,'#67523c');
  for(let i=0;i<3;i++)k.line([[-1.7+i*.14,.4,-5],[-1.95+i*.14,2.5,-5]],'#587765',.06);k.line([[2.35,.3,-4.75],[2.2,2.7,-4.75]],'#b6ad88',.028);k.sphere(2.2,2.77,-4.75,.075,'#c8bc98');
  // Lanterns, basket, folded burlap, books, bottles and loose gloves.
  for(const p of [[1,-3.65,.85],[.6,3.1,0]]){const [x,z,y]=p;k.cylinder(x,y+.18,z,.2,.36,'#9b855b');k.cylinder(x,y+.48,z,.14,.43,'#d4c38a');k.cone(x,y+.78,z,.24,.2,'#8d7550');for(const s of [-1,1])k.line([[x+s*.16,y+.22,z],[x+s*.16,y+.73,z]],'#776749',.024);k.torus(x,y+.91,z,.12,.02,'#7e7351',[0,0,0]);}
  k.box(1.3,.085,3.4,1.1,.16,.9,'#d4c8a5');k.box(-3.3,.1,-.9,.87,.2,.53,'#9a8159');k.box(-3.3,.23,-.9,.76,.025,.5,'#cbb891');for(let i=0;i<7;i++)k.box(-3.6+i*.1,.251,-.9,.018,.008,.41,'#a99572');
  for(let i=0;i<8;i++)k.sphere(.9+(i%4)*.14,.08,-.1+Math.floor(i/4)*.2,.12,'#a99a70',[.45,.25,1]);
  k.box(-1.7,.12,3.8,.8,.22,.65,'#928265',{rot:-.4});lathe(k,-2.5,0,3.7,1.1,.095,'#648273','bottle');
  k.box(-.3,.56,4.05,.92,.95,.92,'#697b64');for(const x of [-.65,.05])k.box(x,.56,4.53,.06,1.03,.05,'#505b52');for(const y of [.15,.83])k.box(-.3,y,4.55,1,.08,.07,'#708084');
  const chips=[];for(let i=0;i<24;i++)chips.push({x:-5.5+(i*2.13)%11,y:.025,z:-3.1+(i*.91)%7.4,w:.06+(i%4)*.05,h:.04,d:.08,rot:i,color:['#938c6e','#bbae8a','#827e64'][i%3]});batch(k,chips);
  inspect(k,'여행용 보물 상자',-.65,1,.6,'쌓인 나무 상자와 항아리 사이에 놓인 금속 잠금장치의 보물 상자입니다.');k.features.push('쌓인 나무 상자 · 손잡이 보물상자 · 도자기와 포대 · 랜턴 · 장부 · 술병 · 접은 천 · 잡동사니');
}

function toilet(k) {
  room(k,13,11,{floor:'#d0dbd7',wall:'#b5cac6',tile:'tile',height:3.5});
  const details=[];for(let x=-6;x<6.5;x+=.75)for(let y=.45;y<3.3;y+=.75)details.push({x,y,z:-5.36,w:.13,h:.13,d:.02,color:'#667e79',rz:Math.PI/4});for(let z=-5;z<5.5;z+=.75)for(let y=.45;y<3.3;y+=.75)details.push({x:-6.36,y,z,w:.02,h:.13,d:.13,color:'#667e79',rx:Math.PI/4});batch(k,details);
  k.box(0,1.65,-5.28,13,.16,.12,'#71938e');k.box(-6.28,1.65,0,.12,.16,11,'#71938e');
  for(let i=0;i<4;i++){
    const x=-1.5+i*1.75,z=-3.8;k.box(x,.98,z+1,1.6,1.96,.08,'#b4b4a0',{solid:true});k.box(x-.84,1.05,z,.07,2.1,2,'#91a49a',{solid:true});k.box(x+.84,1.05,z,.07,2.1,2,'#91a49a',{solid:true});
    k.box(x,.98,z+1.06,1.37,1.79,.05,'#c5c3a9');k.box(x,1.44,z+1.1,.55,.22,.018,'#7b8170');k.line([[x-.54,.91,z+1.12],[x-.54,1.13,z+1.12]],'#6b776c',.018);for(const yy of [.28,1.6])k.box(x+.68,yy,z+1.14,.04,.1,.025,'#67796e');
    k.box(x,.7,z-.6,.55,.9,.18,'#d6ded0');k.sphere(x,.44,z-.3,.31,'#d9e4d4',[1,.65,1.4]);k.torus(x,.63,z-.3,.245,.045,'#edefda');k.cylinder(x,.22,z-.3,.13,.35,'#bcccbc');k.box(x+.66,.75,z-.4,.13,.04,.22,'#788c79');cylinder(k,x+.66,.83,z-.4,.075,.19,'#efe7cf',[0,0,Math.PI/2]);
  }
  // Three sculpted urinals against the left wall, with basin cavities and valves.
  for(let i=0;i<3;i++){const z=-3.6+i*1.25;k.sphere(-5.99,.8,z,.36,'#c6d6ca',[.5,1.8,.8]);k.sphere(-5.78,.85,z,.24,'#728e80',[.13,1.9,.75]);k.sphere(-5.72,.48,z,.31,'#d6e2d1',[.7,.4,1]);k.line([[-6.05,1.3,z],[-6.05,1.62,z],[-5.95,1.62,z]],'#7f9d8c',.025);k.torus(-5.91,1.63,z,.065,.016,'#bdd0ba',[0,Math.PI/2,0]);k.collide(-5.84,z,.6,.7,{h:1.6});}
  // Circular pedestal sink, mirror and chrome tap between cubicles and floor.
  lathe(k,-1.65,0,-1.4,.78,.41,'#a5beb1','urn');k.torus(-1.65,.79,-1.4,.4,.045,'#d0dbca');k.cylinder(-1.65,.76,-1.4,.32,.025,'#75988b');pipe(k,[[-1.65,.79,-1.68],[-1.65,1.05,-1.68],[-1.65,1.05,-1.5]],.03,'#d0d5bd');k.box(-1.65,1.64,-2.61,1.45,1.08,.08,'#6e7868');k.box(-1.65,1.64,-2.55,1.27,.92,.025,'#b6dcd2');
  roundSolid(k,-1.65,-1.4,.41,0,.84);
  k.box(5.43,.47,2,1.5,.95,.9,'#b5c4b7',{solid:true});k.box(5.43,.97,2,1.4,.075,.85,'#dbe2cd');k.box(5.43,1.02,2,.95,.025,.58,'#839d8c');for(const x of [5.15,5.7])pipe(k,[[x,1.06,1.71],[x,1.23,1.71],[x,1.23,1.86]],.018,'#a5b9a6');
  for(const x of [4.8,5.15,5.5]){k.line([[x,.12,-4.2],[x-.18,1.7,-4.2]],'#a0936f',.025);k.box(x,.07,-4.14,.32,.06,.23,'#969e81');}k.box(5.8,1.48,-5.15,1.6,.55,.1,'#b8c4ad');k.text('청결을 지켜주세요',5.8,1.48,-5.07,{width:1.3,height:.16,color:'#667d6d',background:'#cdd7bd'});
  for(let i=0;i<4;i++)k.torus(4.8+i*.24,1.1,-5.1,.18,.022,['#7f9e89','#c3d0b5'][i%2],[0,0,0]);
  for(const x of [-4.1,-1.2,2.2]){k.box(x,2.49,-5.2,.57,.57,.08,'#d9dfc5');k.torus(x,2.49,-5.12,.19,.025,'#a8b89d',[0,0,0]);batch(k,[{x,y:2.49,z:-5.085,w:.045,h:.35,d:.015,color:'#91a58d',rz:.6},{x,y:2.49,z:-5.085,w:.35,h:.045,d:.015,color:'#91a58d',rz:.6}]);}
  inspect(k,'세면대',-1.65,1,-1.35,'네 개의 칸막이, 소변기, 환기 팬과 청소 도구까지 배치된 화장실입니다.');k.features.push('4개 개별 칸막이와 변기 · 3개 소변기 · 거울과 세면대 · 환기 팬 · 마름모 타일 · 대걸레와 수건');
}

export const interiorMaps = [
  {id:'BoilerRoom',name:'보일러실',category:'실내',file:'BoilerRoom.png',description:'연결된 배관과 대형 보일러, 석탄 저장고가 있는 지하 기계실',width:13,depth:10,spawn:[-1,2],fog:'#2c3430',sky:'#343b34',build:boiler},
  {id:'CuriousMansion',name:'신비한 저택',category:'실내',file:'CuriousMansion.jpg',description:'붉은 카펫과 촛대, 아치 창과 수호상이 있는 대저택',width:18,depth:16,spawn:[0,6.5],fog:'#58584c',sky:'#727361',build:mansion},
  {id:'in-Academy',name:'학원 내부',category:'실내',file:'in-Academy.png',description:'네 층의 상층 회랑, 체크 무늬 바닥과 연속 계단의 학원 홀',width:26,depth:23,spawn:[0,8.5],fog:'#b79375',sky:'#c5a584',build:academy},
  {id:'Library',name:'도서관',category:'실내',file:'Library.jpg',description:'책으로 가득한 서가, 대출 데스크와 상층 열람 공간',width:17,depth:14,spawn:[-3,5.6],fog:'#6c8074',sky:'#96a092',build:library},
  {id:'PEStorage',name:'체육 창고',category:'실내',file:'PEStorage.png',description:'농구공과 축구공, 허들, 배트와 체육 매트가 있는 창고',width:12,depth:10,spawn:[-2.4,3.5],fog:'#5d6358',sky:'#757a66',build:peStorage},
  {id:'Restaurant',name:'식당',category:'실내',file:'Restaurant.png',description:'벽돌 돔 오븐, 조리대, 식기 선반과 나무 식탁',width:14,depth:11,spawn:[1.8,3.8],fog:'#736b56',sky:'#a39777',build:restaurant},
  {id:'Sauna',name:'사우나',category:'실내',file:'Sauna.png',description:'휴식 매트, 온탕, 샤워실과 돌 정원이 있는 목욕탕',width:27,depth:19,spawn:[5.5,7],fog:'#8ca79a',sky:'#b4c8b3',build:sauna},
  {id:'ScienceRoom',name:'과학 연구실',category:'실내',file:'ScienceRoom.png',description:'약재 서랍, 유리 실험 장비, 연구 노트와 흔들의자',width:14,depth:11,spawn:[-1.8,3.8],fog:'#82917c',sky:'#b5c2a3',build:science},
  {id:'Storage',name:'보관 창고',category:'실내',file:'Storage.png',description:'상자와 도자기, 여행용 보물상자와 각종 잡동사니',width:13,depth:11,spawn:[4.5,4.2],fog:'#756e56',sky:'#a69b74',build:storage},
  {id:'Toilet',name:'화장실',category:'실내',file:'Toilet.png',description:'칸막이와 변기, 소변기, 거울, 세면대와 청소 도구',width:13,depth:11,spawn:[0,3.6],fog:'#91aaa0',sky:'#b8c9b8',build:toilet},
];
