// Reference-specific outdoor maps. All architecture, water, foliage and props
// are real geometry; the reference images are used only by the map picker.
const C = { stone:'#d5d0b5', dark:'#514737', wood:'#855334', leaf:'#65943e', grass:'#a3bb69', glass:'#526768' };

function rng(seed) { return () => { seed = (Math.imul(seed,1664525)+1013904223) >>> 0; return seed/4294967296; }; }
function stroke(k,points,color,radius=.04){
  if(points.length!==2)return k.line(points,color,radius);
  const a=new k.THREE.Vector3(...points[0]),b=new k.THREE.Vector3(...points[1]),direction=b.clone().sub(a),length=direction.length();
  if(length<.001)return null;
  const m=k.cylinder(0,0,0,radius,1,color,{segments:6});m.position.copy(a.add(b).multiplyScalar(.5));m.scale.y=length;m.quaternion.setFromUnitVectors(new k.THREE.Vector3(0,1,0),direction.normalize());return m;
}
function mesh(k, geometry, color, x=0,y=0,z=0,rotation=0, roughness=.86) {
  const m = new k.THREE.Mesh(geometry,new k.THREE.MeshStandardMaterial({color,roughness}));
  m.position.set(x,y,z); m.rotation.y=rotation; m.castShadow=true; m.receiveShadow=true; k.root.add(m); return m;
}
function prism(k, points, bottom, top, color) {
  const T=k.THREE, contour=points.map(p=>new T.Vector2(p[0],p[1]));
  const triangles=T.ShapeUtils.triangulateShape(contour,[]), verts=[], indices=[];
  for (const y of [bottom,top]) for (const p of points) verts.push(p[0],y,p[1]);
  const n=points.length;
  for (const [a,b,c] of triangles) indices.push(a,b,c,a+n,c+n,b+n);
  for(let i=0;i<n;i++){const j=(i+1)%n;indices.push(i,j,j+n,i,j+n,i+n);}
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(verts,3));g.setIndex(indices);g.computeVertexNormals();
  return mesh(k,g,color);
}
function path(k,points,width,color,y=.035) {
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);
    k.box((a[0]+b[0])/2,y,(a[1]+b[1])/2,width,.055,length+.5,color,{rot:Math.atan2(dx,dz)});
    k.cylinder(a[0],y,a[1],width/2,.05,color,{segments:16});
  }
}
function water(k,points,width=6) {
  path(k,points,width,'#47a6bf',.02);
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
    k.collide((a[0]+b[0])/2,(a[1]+b[1])/2,width,len,{y:-3,h:3.18,rot:Math.atan2(dx,dz),support:false});
    const perp=[dz/len,-dx/len];
    for(let side of [-1,1])stroke(k,[[a[0]+perp[0]*width*.52,.13,a[1]+perp[1]*width*.52],[b[0]+perp[0]*width*.52,.13,b[1]+perp[1]*width*.52]],'#8a9980',.14);
    for(let j=0;j<4;j++){const t=(j+.3)/4; stroke(k,[[a[0]+dx*t-.45,.075,a[1]+dz*t],[a[0]+dx*t+.45,.075,a[1]+dz*t+.05]],'#93dce0',.02);}
  }
}
function roof(k,x,y,z,w,d,h,color='#bf6946',rot=0,tile=true) {
  const vertices=[-w/2,0,-d/2,w/2,0,-d/2,0,h,-d/2,-w/2,0,d/2,w/2,0,d/2,0,h,d/2];
  const geometry=new k.THREE.BufferGeometry();geometry.setAttribute('position',new k.THREE.Float32BufferAttribute(vertices,3));geometry.setIndex([0,2,1,3,4,5,0,5,2,0,3,5,2,4,1,2,5,4,0,4,3,0,1,4]);geometry.computeVertexNormals();
  const m=mesh(k,geometry,color,x,y,z,rot);
  if(tile){
    const group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);
    const original=k.root;k.root=group;
    for(let side of [-1,1])for(let a=1;a<=5;a++){
      const f=a/5,xx=side*w*.5*f,yy=h*(1-f)+.04;
      stroke(k,[[xx,yy,-d*.5],[xx,yy,d*.5]],'#8f644d',.027);
    }
    for(let j=0;j<=8;j++){const zz=-d/2+d*j/8;stroke(k,[[-w/2,.025,zz],[0,h+.035,zz],[w/2,.025,zz]],'#d6945b',.021);}
    stroke(k,[[0,h+.07,-d*.54],[0,h+.07,d*.54]],color,.09);k.root=original;
  }
  return m;
}
function pyramidalRoof(k,x,y,z,w,d,h,color) {
  const v=[-w/2,0,-d/2,w/2,0,-d/2,w/2,0,d/2,-w/2,0,d/2,0,h,0];
  const g=new k.THREE.BufferGeometry();g.setAttribute('position',new k.THREE.Float32BufferAttribute(v,3));g.setIndex([0,4,1,1,4,2,2,4,3,3,4,0,0,1,2,0,2,3]);g.computeVertexNormals();mesh(k,g,color,x,y,z);
  for(let i=1;i<6;i++){const t=i/6;stroke(k,[[x-w/2*(1-t),y+h*t+.025,z-d/2*(1-t)],[x+w/2*(1-t),y+h*t+.025,z-d/2*(1-t)],[x+w/2*(1-t),y+h*t+.025,z+d/2*(1-t)],[x-w/2*(1-t),y+h*t+.025,z+d/2*(1-t)],[x-w/2*(1-t),y+h*t+.025,z-d/2*(1-t)]], '#c6a665',.025);}
}
function window(k,x,y,z,w=.65,h=1.2,color=C.dark,rot=0,arch=false) {
  const ox=Math.sin(rot)*.035,oz=Math.cos(rot)*.035;
  k.box(x,y,z,w+.15,h+.16,.08,color,{rot});
  k.box(x+ox,y,z+oz,w,h,.085,C.glass,{rot});
  k.box(x+ox*2,y,z+oz*2,.055,h,.065,'#d1cbb1',{rot});
  k.box(x+ox*2,y,z+oz*2,w,.055,.065,'#d1cbb1',{rot});
  k.box(x,y-h/2-.1,z,w+.22,.14,.24,'#b8ae8b',{rot});
  if(arch)k.sphere(x,y+h/2-.1,z,.5,color,[w,.44,.15]);
}
function door(k,x,y,z,w=1.2,h=2.2,color='#6d4835',rot=0) {
  k.box(x,y+h/2,z,w+.22,h+.12,.12,C.dark,{rot});
  k.box(x+Math.sin(rot)*.065,y+h/2,z+Math.cos(rot)*.065,w,h,.12,color,{rot});
  for(let i=-1;i<=1;i++)k.box(x+i*w*.23*Math.cos(rot),y+h/2,z-i*w*.23*Math.sin(rot),.025,h,.18,'#b18659',{rot});
  k.sphere(x+w*.31*Math.cos(rot),y+h*.48,z+.14,.055,'#ddb45b');
}
function house(k,x,z,w=5,d=4,h=5.6,opts={}) {
  const {y=0,wall='#e6dbb5',roof:roofColor='#bd7146',timber=true,chimney=true,rot=0}=opts;
  const group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);
  const original=k.root;k.root=group;
  k.box(0,.24,0,w+.2,.48,d+.2,'#9b9584');k.box(0,h/2,0,w,h,d,wall);
  if(timber){
    for(let xx of [-w/2+.1,0,w/2-.1])k.box(xx,h/2,d/2+.03,.16,h,.12,C.dark);
    for(let yy=.4;yy<h;yy+=2.7)k.box(0,yy,d/2+.045,w,.18,.12,C.dark);
    for(let zz of [-d/2+.08,d/2-.08])k.box(w/2+.03,h/2,zz,.12,h,.16,C.dark);
    for(let yy=.4;yy<h;yy+=2.7)k.box(w/2+.04,yy,0,.12,.18,d,C.dark);
  }
  door(k,0,0,d/2+.08,1.15,2.15);
  for(let yy=1.5;yy<h-.6;yy+=2.6){for(let xx of [-w*.3,w*.3])window(k,xx,yy,d/2+.075,.6,.95);window(k,w/2+.08,yy,0,.6,.95,C.dark,Math.PI/2);}
  roof(k,0,h,0,w+.65,d+.65,w*.4,roofColor,0,opts.tile!==false);
  window(k,0,h+.62,d/2+.08,.58,.65);
  if(chimney){k.box(w*.26,h+1.2,-d*.23,.56,2.4,.6,'#a46d55');k.box(w*.26,h+2.45,-d*.23,.75,.2,.8,'#705b4a');}
  k.root=original;k.collide(x,z,w,d,{y,h,rot});
  return {x,z,w,d,h,y};
}
function tree(k,x,z,h=5,type='round',seed=0,y=0) {
  h=Math.round(h*2)/2;
  const green=['#507a39','#658c3c','#759c43','#8da84d'][seed%4];
  k.cylinder(x,y+h*.25,z,h*.055,h*.5,'#685036',{segments:7});
  if(type==='pine'){
    for(let i=0;i<3;i++)k.cone(x,y+h*(.48+i*.2),z,h*(.23-i*.042),h*.47,green,8);
  }else{
    k.sphere(x,y+h*.74,z,h*.25,green,[1.18,1,1.08]);
    k.sphere(x+h*.2,y+h*.69,z+h*.07,h*.22,green,[1,1,.95]);
    k.sphere(x-h*.19,y+h*.67,z-h*.13,h*.2,green,[1,1,1]);
  }
  k.collide(x,z,h*.15,h*.15,{y,h:h*.55});
}
function bush(k,x,z,r=.75,color='#709448',y=0){k.sphere(x,y+r*.5,z,r,color,[1,.7,1]);}
function barrel(k,x,z,r=.38,y=0){k.cylinder(x,y+r*.95,z,r,r*1.9,'#9d6c42',{segments:12});for(let dy of [.2,.65,1.35,1.7])k.torus(x,y+r*dy,z,r+.01,.025,'#55524a');k.cylinder(x,y+r*1.93,z,r*.92,.045,'#ba8d5b',{segments:12});}
function crate(k,x,z,size=.7,y=0){k.box(x,y+size/2,z,size,size,size,'#a88457');for(let v of [-.34,.34]){k.box(x+size*v,y+size/2,z+size*.51,size*.12,size,.04,'#725033');k.box(x,y+size*(v+.5),z+size*.52,size,.085,.055,'#725033');}k.box(x,y+size/2,z+size*.54,.08,size*1.1,.045,'#805836',{rot:Math.PI/4});}
function bench(k,x,z,rot=0,y=0){const group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);const old=k.root;k.root=group;for(let zz of [-.18,0,.18])k.box(0,.46,zz,1.8,.09,.16,'#936745');for(let xx of [-.65,.65]){k.box(xx,.23,0,.1,.46,.42,'#4d5049');k.box(xx,.65,-.27,.1,1,.1,'#4d5049');}for(let yy of [.78,1.02])k.box(0,yy,-.27,1.8,.17,.07,'#936745');k.root=old;k.interactions.push({name:'벤치에 앉기',position:[x,y+.5,z],kind:'seat',text:'산책길의 나무 벤치'});}
function lamp(k,x,z,h=4,y=0,color='#423e39') {
  k.cylinder(x,y+.15,z,.22,.3,color);k.cylinder(x,y+h/2,z,.09,h,color,{segments:8});
  k.box(x,y+h-.2,z,.42,.65,.42,'#cab96b');
  for(let xx of [-.24,.24])for(let zz of [-.24,.24])k.box(x+xx,y+h-.2,z+zz,.045,.76,.045,color);
  pyramidalRoof(k,x,y+h+.22,z,.7,.7,.35,color);
}
function fountain(k,x,z,r=3,y=0,color='#d6d8d0'){
  k.cylinder(x,y+.17,z,r,.34,color,{segments:32});k.cylinder(x,y+.4,z,r*.87,.14,'#64b2c9',{segments:32});k.torus(x,y+.5,z,r*.95,.18,color);
  k.cylinder(x,y+1,z,.4,1.4,color);k.cylinder(x,y+1.65,z,r*.4,.2,color,{segments:24});k.cylinder(x,y+1.79,z,r*.32,.08,'#5cbed1',{segments:24});k.sphere(x,y+2.1,z,.32,color);
  for(let i=0;i<6;i++){const a=i*Math.PI/3;stroke(k,[[x,y+2.15,z],[x+Math.cos(a)*.65,y+2.55,z+Math.sin(a)*.65],[x+Math.cos(a)*r*.72,y+.5,z+Math.sin(a)*r*.72]],'#afebef',.035);}
  k.interactions.push({name:'분수 살펴보기',position:[x+r,y+.5,z],kind:'inspect',text:'분수의 물줄기와 물결이 광장 한가운데 반짝입니다.'});
}
function hedge(k,x,z,w,d,h=1.1){k.box(x,h/2,z,w,h,d,'#60813e');for(let i=0;i<Math.ceil(w/1.5);i++)bush(k,x-w/2+(i+.5)*w/Math.ceil(w/1.5),z,.6,'#74934d',h-.3);k.collide(x,z,w,d,{h});}
function arch(k,x,y,z,w,h,d,color='#c4c3b4'){
  const T=k.THREE, r=w/2,thick=.38,shape=new T.Shape();shape.moveTo(-r,0);shape.lineTo(-r,h-r);
  for(let i=0;i<=20;i++){const a=Math.PI-i*Math.PI/20;shape.lineTo(Math.cos(a)*r,h-r+Math.sin(a)*r);}
  shape.lineTo(r,0);shape.lineTo(r-thick,0);shape.lineTo(r-thick,h-r);
  for(let i=0;i<=20;i++){const a=i*Math.PI/20;shape.lineTo(Math.cos(a)*(r-thick),h-r+Math.sin(a)*(r-thick));}
  shape.lineTo(-r+thick,0);shape.closePath();
  const g=new T.ExtrudeGeometry(shape,{depth:d,bevelEnabled:false,steps:1});g.translate(0,0,-d/2);mesh(k,g,color,x,y,z);
}
function stoneBridge(k,x,z,w=11,d=4,y=.8,color='#c8c9b8'){
  k.box(x,y-.22,z,w,.44,d,color);k.surface(x,z,w,d,y);
  for(let zz of [-d*.5,d*.5]){k.box(x,y+.35,z+zz,w,.7,.26,color);for(let i=0;i<Math.floor(w/.85);i++)k.box(x-w/2+(i+.5)*w/Math.floor(w/.85),y+.75,z+zz,.55,.16,.32,'#e6dfc9');}
  for(let xx of [-w*.28,w*.28])arch(k,x+xx,-1,z,w*.42,1.6,d-.3,'#9b9e8d');
  // Broad small steps at both banks also register their tops for walking.
  for(let side of [-1,1])for(let i=0;i<4;i++){const yy=y-(i+1)*y/4,xx=x+side*(w/2+.25+i*.5);k.box(xx,yy/2,z,.52,Math.max(.05,yy),d,color);k.surface(xx,z,.54,d,Math.max(.03,yy));}
}
function timberBridge(k,x,z,w=10,d=3,y=.6){
  for(let i=0;i<Math.ceil(w/.35);i++)k.box(x-w/2+(i+.5)*w/Math.ceil(w/.35),y-.08,z,w/Math.ceil(w/.35)-.025,.16,d,'#a17b4e');k.surface(x,z,w,d,y);
  for(let side of [-1,1]){stroke(k,[[x-w/2,y+1,z+side*d/2],[x+w/2,y+1,z+side*d/2]],'#725b3b',.065);for(let i=0;i<=4;i++)k.cylinder(x-w/2+i*w/4,y+.2,z+side*d/2,.085,1.6,'#796043');}
  for(let side of [-1,1])for(let i=0;i<3;i++){const yy=y-(i+1)*y/3,xx=x+side*(w/2+.2+i*.4);k.box(xx,Math.max(.025,yy/2),z,.42,Math.max(.05,yy),d,'#8e744d');k.surface(xx,z,.44,d,Math.max(.03,yy));}
}
function cobbles(k,points,count=35,seed=42,y=.05){const random=rng(seed);for(let i=0;i<count;i++){const a=points[i%(points.length-1)],b=points[i%(points.length-1)+1],t=random(),x=a[0]+(b[0]-a[0])*t+(random()-.5)*3,z=a[1]+(b[1]-a[1])*t+(random()-.5)*3;k.cylinder(x,y,z,.2+random()*.28,.065,'#b6b299',{segments:5});}}
function rock(k,x,z,r=2,h=3,color='#b8b294',y=0){k.sphere(x,y+h*.45,z,r,color,[1,h/r,1]);k.collide(x,z,r*1.45,r*1.45,{y,h});}
function fence(k,x,z,w,rot=0,y=0){const group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);const old=k.root;k.root=group;for(let xx=-w/2;xx<=w/2;xx+=.65)k.box(xx,.6,0,.1,1.2,.12,'#806848');for(let yy of [.38,.87])k.box(0,yy,0,w,.11,.1,'#9d8059');k.root=old;k.collide(x,z,w,.2,{y,h:1.2,rot});}
function raisedStairs(k,x,z,w,count,rise,run,color,base=0,heading=0){
  const total=count*run;
  for(let i=0;i<count;i++){const localZ=total/2-(i+.5)*run,xx=x+Math.sin(heading)*localZ,zz=z+Math.cos(heading)*localZ,top=base+(i+1)*rise;k.box(xx,top/2,zz,w,top,run,color,{rot:heading});k.surface(xx,zz,w,run,top,{rot:heading});k.box(xx,top+.008,zz,w,.018,.05,'#bba982',{rot:heading});}
}
function market(k,x,z,w=4,color='#c56b54',opts={}){
  const {y=0,rot=0,fruit=true}=opts,group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);const old=k.root;k.root=group;
  k.box(0,.6,0,w,1.2,1.3,'#a78055');for(let xx of [-w/2,w/2])for(let zz of [-.65,.65])k.cylinder(xx,1.5,zz,.06,3,'#715941');
  const slope=-.16;
  for(let i=0;i<Math.ceil(w/.45);i++){const xx=-w/2+(i+.5)*w/Math.ceil(w/.45);const m=k.box(xx,2.7,0,w/Math.ceil(w/.45),.09,2.2,i%2? '#eedcb1':color);if(m?.rotation)m.rotation.x=slope;k.box(xx,2.45,1.1,w/Math.ceil(w/.45),.3,.08,i%2?'#eedcb1':color);}
  if(fruit)for(let i=0;i<12;i++)k.sphere(-w*.4+(i%6)*w*.16,1.3,Math.floor(i/6)*.38-.2,.14,i%3?'#89a548':'#d47b41');
  k.root=old;k.collide(x,z,w,1.3,{y,h:1.2,rot});
}
function cart(k,x,z,rot=0,y=0){const group=new k.THREE.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);const old=k.root;k.root=group;k.box(0,.65,0,1.3,.12,2,'#8e6842');for(let xx of [-.7,.7]){k.box(xx,1,0,.12,.7,2.2,'#a58157');for(let zz of [-.7,.7]){const m=k.torus(xx,.48,zz,.4,.055,'#5e4b35',[0,Math.PI/2,0]);for(let j=0;j<4;j++){const a=j*Math.PI/4;stroke(k,[[xx,.48+Math.cos(a)*.34,zz+Math.sin(a)*.34],[xx,.48-Math.cos(a)*.34,zz-Math.sin(a)*.34]],'#8e7451',.035);}}}for(let xx of [-.4,.4])k.box(xx,.65,1.5,.07,.07,1.7,'#7a5b3c');crate(k,0,0,.55,.72);k.root=old;}

function academyBuilding(k,x,z,w,d,h,y=0){
  k.box(x,y+h/2,z,w,h,d,'#a77569');k.box(x,y+.3,z,w+.5,.6,d+.5,'#878374');k.collide(x,z,w,d,{y,h});
  for(let floor=0;floor<3;floor++){
    const yy=y+1.5+floor*2.6;k.box(x,yy-1,z+d/2+.03,w,.12,.1,'#645648');
    const num=Math.floor(w/1.8);for(let i=0;i<num;i++){const xx=x-w/2+(i+.5)*w/num;window(k,xx,yy,z+d/2+.09,.54,1.25,'#645748',0,floor===0);}
    for(let j=0;j<Math.floor(d/1.8);j++)window(k,x+w/2+.08,yy,z-d/2+(j+.5)*d/Math.floor(d/1.8),.55,1.15,'#645748',Math.PI/2,floor===0);
  }
  roof(k,x,y+h,z,w+.7,d+.7,3,'#a8997f');
  for(let i=0;i<Math.floor(w/3);i++){
    const xx=x-w/2+1.5+i*3;k.box(xx,y+h+1.12,z+d*.23,.9,1.6,1.1,'#d0b89b');roof(k,xx,y+h+1.9,z+d*.23,1.15,1.3,.7,'#a8997f',0,false);window(k,xx,y+h+1.2,z+d*.23+.58,.34,.66);
  }
}
function buildAcademy(k){
  k.floor(110,92,'#a6c97d',{tile:'grass'});
  water(k,[[23,-45],[27,-33],[20,-20],[25,-7],[20,7],[18,23],[26,34],[36,46]],7);
  water(k,[[-48,-27],[-33,-29],[-23,-37],[-8,-36],[9,-39],[23,-35]],5);
  // A raised brick academy island, with full accessible approach and side stairs.
  k.box(-1,1.09,-5,48,2.18,52,'#b0a58a');k.platform(-1,2.2,-5,48,52,'#e8deb9');
  for(let i=0;i<19;i++){const xx=-24+(i+.5)*48/19;if(xx>-11&&xx<3)continue;rock(k,xx,21.3,1.35,2.9,'#b4aa8d',-.8);}
  academyBuilding(k,-4,-16,25,9,8.7,2.2);academyBuilding(k,-21,-12,8,8,8.1,2.2);academyBuilding(k,15,2,8,7,6.8,2.2);
  // Gothic central entry with rose window, pediment, clock and bell tower.
  k.box(-4,7.2,-9.8,5.1,10,3.5,'#ac7969',{solid:true});roof(k,-4,12.2,-9.8,6,4.4,3.5,'#a99a80');
  door(k,-4,2.2,-7.96,2,3.1,'#63523e');arch(k,-4,2.2,-7.8,2.65,4.4,.28,'#b6b194');
  k.torus(-4,10.45,-7.79,1.02,.12,'#c9c0a4',[0,0,0]);
  for(let a=0;a<8;a++){const angle=a*Math.PI/4;stroke(k,[[-4,10.45,-7.77],[-4+Math.sin(angle)*.9,10.45+Math.cos(angle)*.9,-7.77]],'#beb99c',.04);}
  k.box(-4,14.1,-16,4.8,5.6,4.5,'#b59b7e');pyramidalRoof(k,-4,16.9,-16,5.4,5,4.8,'#968773');
  for(let xx of [-6.5,-1.5]){k.box(xx,14.1,-13.7,.25,5.5,.2,'#756d59');k.cone(xx,18,-13.7,.36,2.6,'#98896e',4);}
  window(k,-4,14.6,-13.7,1.7,2.1,'#605744',0,true);k.cylinder(-4,22,-16,.08,.8,'#686352');
  k.stairs(-4,24,13,11,.2,.56,'#cdc9b4',0);
  for(let side of [-1,1]){stroke(k,[[-4+side*6.7,.3,27],[-4+side*6.7,3.05,20.5]],'#babaa4',.09);for(let i=0;i<9;i++)k.cylinder(-4+side*6.7,.7+i*.25,26.7-i*.68,.06,.9,'#cacbb6');}
  k.stairs(-27.3,10.7,4,11,.2,.42,'#d2cbb2',-Math.PI/2);k.stairs(25.3,15.5,4,11,.2,.42,'#d2cbb2',Math.PI/2);
  path(k,[[-4,38],[-4,27]],5.5,'#e8dfb8');cobbles(k,[[-4,40],[-4,28]],20,58,.06);cobbles(k,[[-4,19],[-4,4]],40,59,2.24);
  stoneBridge(k,20,21,12,4,.8);timberBridge(k,24,-6,11,3,.6);stoneBridge(k,24,-30,10,4,.8);
  // Rock ledge, double waterfall, and a stepped ancient temple.
  for(let i=0;i<10;i++){rock(k,-48+i*3,-40,3,10+(i%3),'#bbb79a');k.cylinder(-48+i*3,11.8,-40,3,.3,'#b1c88a',{segments:8});}
  for(let xx of [-43,-39.5]){k.box(xx,5.7,-36.8,1.4,11.4,.22,'#70bfd5');stroke(k,[[xx,11.2,-36.6],[xx+.2,5,-36.6],[xx,.3,-36.6]],'#bef1ed',.2);}
  // Each terrace is split around a real central stair slot. Continuous full
  // tier boxes would hide the approach and let walkers enter its stone volume.
  const templeX=-34,templeZ=-23,stairWidth=3.2,stairTopZ=-20.95;
  // Inset each blocker below the climbable stone lip: the navigation capsule
  // must reach the last step before its centre enters the landing rectangle.
  for(let i=0;i<7;i++){
    const size=11-i*1.15,flank=(size-stairWidth)/2,top=.96+i*.95,base=i*.95;
    for(let side of [-1,1]){
      const xx=templeX+side*(stairWidth+flank)/2;
      k.box(xx,.45+base,templeZ,flank,.9,size,'#9d9b83');
      k.box(xx,.92+base,templeZ,flank,.08,size,'#c2c0a1');
      k.surface(xx,templeZ,flank,size,top);k.collide(xx,templeZ,flank,size,{y:base,h:.84});
    }
    const backZ=templeZ-size/2,rearDepth=stairTopZ-backZ,rearZ=(backZ+stairTopZ)/2;
    k.box(templeX,.45+base,rearZ,stairWidth,.9,rearDepth,'#9d9b83');
    k.box(templeX,.92+base,rearZ,stairWidth,.08,rearDepth,'#c2c0a1');
    k.surface(templeX,rearZ,stairWidth,rearDepth,top);k.collide(templeX,rearZ,stairWidth,rearDepth,{y:base,h:.84});
  }
  k.box(-34,7.3,-23,3,1.5,3,'#7e806b');k.collide(-34,-23,3,3,{y:6.55,h:1.5});
  k.stairs(-34,stairTopZ+26*.42/2,stairWidth,26,.25,.42,'#bebca2');
  for(let dx of [-4,4]){k.box(-34+dx,4.5,-29,1.6,5.2,1.5,'#aca992');for(let yy of [3.6,5.3])k.box(-34+dx,yy,-28.21,.8,.55,.06,'#6e725e');}
  // Giant tree dwelling includes roots, branch shelves and little arched doors.
  k.cylinder(39,7,-31,3,14,'#867448',{top:1.5,segments:9});
  for(let i=0;i<7;i++){const a=i*.9;stroke(k,[[39,5,-31],[39+Math.cos(a)*4,1.1,-31+Math.sin(a)*4],[39+Math.cos(a)*5.5,.1,-31+Math.sin(a)*5.5]],'#8c784b',.45);}
  for(let i=0;i<5;i++){const yy=2.2+i*2.4,xx=39+(i%2?2.1:-2.1);k.cylinder(xx,yy,-30.5,2,.24,'#827651',{segments:10});bush(k,xx,-30.5,1.8,'#718b45',yy);door(k,xx,yy+.15,-28.9,.8,1.25,'#443c2b');}
  for(let i=0;i<6;i++)k.sphere(39+Math.sin(i)*3,15+Math.cos(i)*1.5,-31+Math.cos(i)*3,3.6,'#718c43',[1.25,.8,1]);k.collide(39,-31,5,5,{h:14});
  // Round amphitheater has individual open arches and a real stepped interior.
  const ax=-5,az=34,ar=6.5;
  for(let i=0;i<24;i++){
    const a=i*Math.PI/12,xx=ax+Math.sin(a)*ar,zz=az+Math.cos(a)*ar;
    k.cylinder(xx,2.5,zz,.23,5,'#b8b192',{segments:8});
    const group=new k.THREE.Group();group.position.set(xx,0,zz);group.rotation.y=a;k.root.add(group);const old=k.root;k.root=group;arch(k,0,0,0,1.7,2.6,.34,'#c7bea0');arch(k,0,2.7,0,1.7,2.2,.34,'#c7bea0');k.box(0,2.68,0,1.9,.22,.55,'#d5cbae');k.box(0,5,0,1.9,.23,.55,'#d5cbae');k.root=old;
    if(i>1&&i<23)k.collide(xx,zz,.5,.5,{h:5});
  }
  k.cylinder(ax,.025,az,5.6,.05,'#c9bc9a',{segments:32});k.surface(ax,az,11.2,11.2,.05);
  for(let i=0;i<4;i++){
    const r=4.3+i*.4,center=.2+i*.2,segments=48;
    k.torus(ax,center,az,r,.18,'#b5a78d');
    // Tangential segments follow each seat ring, registering its actual top.
    // The same low blockers prevent entering the timber at ground height.
    for(let j=0;j<segments;j++){
      const angle=j*Math.PI*2/segments,xx=ax+Math.sin(angle)*r,zz=az+Math.cos(angle)*r,w=2*r*Math.tan(Math.PI/segments)+.025;
      // Include the .22 m capsule radius, matching the collider's edge test.
      k.surface(xx,zz,w+.44,.84,center+.18,{rot:angle});
      k.collide(xx,zz,w,.4,{y:center-.18,h:.36,rot:angle});
    }
  }
  // An entrance stair makes the outer ring reachable from the front gate.
  k.stairs(ax,az+6.26,1.8,4,.245,.32,'#b5a78d');
  k.interactions.push({name:'원형극장',position:[-5,.5,40.8],kind:'inspect',text:'두 층의 석조 아치와 원형 관람석을 따라 고대 원형극장을 둘러보세요.'});
  // Lower right town and observatory, matching the reference's secondary districts.
  house(k,37,25,5,4,6,{roof:'#bf8b58',wall:'#e0cf9e'});house(k,43,31,5,4,5,{roof:'#bca46e'});house(k,33,34,4,4,5,{roof:'#ba714d'});
  k.cylinder(39,4.8,35,1.1,9.6,'#d5cbb0',{solid:true});k.cone(39,11.2,35,1.8,4,'#dca83b',14);
  house(k,38,7,7,4,4,{roof:'#9d9674',wall:'#bbba99',timber:false});k.sphere(35.5,5.1,7,1.3,'#a5aca5',[1,1,1]);k.cylinder(35.5,4.75,7,1.3,.3,'#6f796f',{segments:16});
  arch(k,-27,0,33,6,5,.5,'#b8aa87');for(let xx of [-30, -24])k.cylinder(xx,1.3,33,.45,2.6,'#a89570');
  // Telescope atop the western sandstone overlook.
  rock(k,-39,0,6,7,'#c8bc95');k.cylinder(-39,6.9,0,4.5,.15,'#d8cba3',{segments:9});
  k.cylinder(-39,7.5,0,.08,1.2,'#6f6a51');stroke(k,[[-39.8,8.1,-.6],[-38.1,8.45,.5]],'#aaa68b',.2);
  // Guardian statue beside the grand stairs.
  k.cylinder(-15,.5,24,.7,1,'#858f7a');k.cylinder(-15,1.9,24,.28,1.7,'#889d85');k.sphere(-15,3,24,.26,'#8fa58c');
  for(let side of [-1,1])stroke(k,[[-15,2.6,24],[-15+side*1.25,3.2,23.5],[-15+side*1.5,2.6,24]],'#8f9d87',.09);
  const random=rng(404);for(let i=0;i<84;i++){let xx=(random()-.5)*104,zz=(random()-.5)*86;if(xx>-27&&xx<29&&zz>-31&&zz<41)continue;if(xx>-41&&xx<-27&&zz>-31&&zz<-9)continue;tree(k,xx,zz,4+random()*3,'pine',i);}
  for(let i=0;i<26;i++){const xx=-23+i*1.75;bush(k,xx,13.3,.65,'#69914a',2.2);}
  bench(k,-12,7,0,2.2);bench(k,7,7,0,2.2);
  k.features.push('벽돌 학원과 종탑','높낮이가 있는 석조 테라스','폭포와 계단식 유적','세 개의 다리','거목의 작은 집','고대 원형극장');
}

function onionDome(k,x,y,z,r,h,color='#e6c860'){
  const T=k.THREE,points=[];const profile=[[0,0],[.6,0],[.87,.12],[1,.33],[.9,.6],[.62,.85],[.28,1.08],[0,1.32]];
  for(const p of profile)points.push(new T.Vector2(p[0]*r,p[1]*h));mesh(k,new T.LatheGeometry(points,28),color,x,y,z,0,.55);
  k.torus(x,y+h*.23,z,r*.95,.045,'#b79637');k.torus(x,y+h*.39,z,r*.98,.04,'#f1d887');
  k.cylinder(x,y+h*1.4,z,.055,h*.2,'#ae8931');k.sphere(x,y+h*1.52,z,.15,'#e8c45f',[.6,1.8,.6]);
  for(let i=0;i<12;i++){const a=i*Math.PI/6;k.sphere(x+Math.cos(a)*r*.84,y+h*.54,z+Math.sin(a)*r*.84,.12,'#a68134',[1,.5,1]);}
}
function minaret(k,x,z,h=10,r=.68,color='#e9dc9b',roofColor='#dfb94e',y=0){
  k.cylinder(x,y+h/2,z,r,h,color,{segments:12});for(let yy of [h*.17,h*.7,h*.82])k.cylinder(x,y+yy,z,r*1.2,.25,'#b3a465',{segments:12});
  for(let a=0;a<4;a++){const angle=a*Math.PI/2;k.box(x+Math.sin(angle)*r*.99,y+h*.58,z+Math.cos(angle)*r*.99,.22,.8,.07,'#4a563d',{rot:angle});}
  onionDome(k,x,y+h,z,r*1.5,r*1.7,roofColor);k.collide(x,z,r*1.8,r*1.8,{y,h});
}
function palace(k,x,z,w,d,h,domer,color='#e1d4a2',gold='#e5c65d',y=0){
  k.box(x,y+h/2,z,w,h,d,color);k.box(x,y+.27,z,w+.4,.54,d+.4,'#d5c28b');k.box(x,y+h,z,w+.5,.24,d+.5,'#b7a66a');
  k.collide(x,z,w,d,{y,h});
  for(let i=0;i<Math.floor(w/1.25);i++)window(k,x-w/2+(i+.5)*w/Math.floor(w/1.25),y+h*.68,z+d/2+.1,.5,1.4,'#ada06a',0,true);
  k.cylinder(x,y+h+.7,z,domer*.86,1.4,color,{segments:24});
  for(let i=0;i<16;i++){const a=i*Math.PI/8;k.box(x+Math.sin(a)*domer*.85,y+h+.65,z+Math.cos(a)*domer*.85,.34,.8,.08,'#464f36',{rot:a});}
  onionDome(k,x,y+h+1.4,z,domer,domer*.85,gold);
  door(k,x,y,z+d*.5+.11,1.8,2.8,'#a4874a');
}
function buildAsuria(k){
  k.floor(76,65,'#d6cd8c',{tile:'sand'});
  prism(k,[[25,-32],[38,-32],[38,32],[25,32],[17,24],[24,10],[21,-6]],-.3,.03,'#63bdd1');k.collide(32,0,12,65,{y:-3,h:3.2,support:false});
  water(k,[[-5,-32],[-4,-22],[-9,-12],[-6,-3],[6,3],[17,12],[25,26]],5.7);
  water(k,[[1,-30],[9,-27],[20,-29],[27,-23]],4);
  palace(k,12,-14,17,11,5.4,5.6);palace(k,23,-6,5.5,5.5,5.9,3.2);palace(k,10,-5,8,5,3.4,3.3);
  for(let [x,z,h] of [[2,-21,10],[22,-21,10],[1,-7,9],[23,0,9],[18,-12,13]])minaret(k,x,z,h,.64);
  // Older peach-domed palace across the canal has a genuine column arcade.
  palace(k,-22,-21,14,10,5.1,4.7,'#e1d5bc','#d9b378');palace(k,-32,-15,5,5,3.9,2.7,'#dfd7bd','#d6b478');palace(k,-13,-17,5,5,3.9,2.7,'#dfd7bd','#d6b478');
  k.platform(-22,.65,-10.5,21,7,'#deded1');
  for(let xx=-31;xx<-11;xx+=1.35){k.cylinder(xx,1.8,-10,.12,2.3,'#c1bca1');arch(k,xx+.65,.7,-10,1.25,2.5,.15,'#d0c7ab');}
  k.stairs(-22,-5.6,12,3,.22,.45,'#dbd6c1');
  // Pale outer city walls connect pointed purple watchtowers around the islands.
  const walls=[[[-37,-28],[-2,-28]],[[-37,24],[8,24]],[[27,-24],[27,2]],[[22,14],[12,22]]];
  for(let [a,b] of walls){const dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);k.box((a[0]+b[0])/2,1.9,(a[1]+b[1])/2,len,3.8,.6,'#dde4d3',{rot:-Math.atan2(dz,dx)});k.collide((a[0]+b[0])/2,(a[1]+b[1])/2,len,.6,{h:3.8,rot:-Math.atan2(dz,dx)});for(let i=0;i<=Math.ceil(len/12);i++){const t=i/Math.ceil(len/12),x=a[0]+dx*t,z=a[1]+dz*t;k.cylinder(x,2.65,z,.73,5.3,'#c7d3d1',{segments:12});k.cone(x,6.7,z,.95,2.8,'#686587',12);k.cylinder(x,4.75,z,.78,.15,'#889391');}}
  // Curved keyhole-style entry gate: two pilasters and a pointed ornamental crown.
  for(let xx of [5.3,10.7])k.cylinder(xx,2.3,24,.43,4.6,'#dce8d2');arch(k,8,3.3,24,5.5,4,.4,'#dfe8d5');
  stroke(k,[[5.25,4.2,24.28],[5.7,6.7,24.28],[8,8.8,24.28],[10.3,6.7,24.28],[10.75,4.2,24.28]],'#61738b',.11);
  k.sphere(8,8.6,24,.2,'#adbe84',[.9,1.5,.5]);
  path(k,[[8,31],[8,19],[-2,11],[-16,5],[-25,-3]],5,'#e7d69b');
  stoneBridge(k,-6,-4,12,4,.8,'#b9c7bb');stoneBridge(k,15,10,11,4,.8,'#bccdc2');
  // Lower neighborhood of differently sized round houses and terracotta shops.
  palace(k,-3,12,7,5.5,3.1,3,'#e6d29c','#c78346');palace(k,-25,14,5,4.5,2.6,2.4,'#e9d7a7','#ca7758');
  palace(k,-17,17,4,4,2.5,1.9,'#e5d2a9','#d9a24f');palace(k,-29,1,5.2,5.2,3.1,2.5,'#e2d19e','#d5be6b');
  house(k,-18,-3,4,3.4,3.2,{wall:'#eadba9',roof:'#b87a57',timber:false,chimney:false});house(k,-13,3,4.8,3.4,2.9,{wall:'#e8d4a0',roof:'#ac7956',timber:false,chimney:false});
  house(k,-7,13,4,3,2.7,{wall:'#dbc18b',roof:'#ad7460',timber:false,chimney:false});house(k,3,16,4,3,2.7,{wall:'#dfc98f',roof:'#bb835e',timber:false,chimney:false});
  house(k,-31,10,3.4,3,2.5,{roof:'#be7858',wall:'#d9c78b',timber:false,chimney:false});
  k.cylinder(-18,.07,5.6,5,.14,'#cbd3bb',{segments:40});for(let r of [2.3,3.7,4.6])k.torus(-18,.17,5.6,r,.035,'#eef0cf');
  for(let i=0;i<24;i++){const a=i*Math.PI/12;stroke(k,[[-18+Math.cos(a)*4.15,.18,5.6+Math.sin(a)*4.15],[-18+Math.cos(a)*4.75,.18,5.6+Math.sin(a)*4.75]],'#9aafaa',.022);}
  fountain(k,-5,22,3.5);market(k,-27,7,3,'#bb785a');market(k,-15,11,3,'#9c8aaf');cart(k,-29,6);
  const random=rng(218);for(let i=0;i<39;i++){let xx=(random()-.5)*70,zz=(random()-.5)*58;if((xx>-34&&xx<-9&&zz>-24&&zz<20)||(xx>0&&xx<26&&zz>-25&&zz<3))continue;if(xx>25)continue;tree(k,xx,zz,3+random()*2,'round',i);}
  for(let p of [[22,20],[27,8],[25,-28],[0,-29],[-36,17]]){bush(k,p[0],p[1],2.2);bush(k,p[0]+1.9,p[1]+1.1,1.6);}
  bench(k,-10,24);bench(k,0,22);lamp(k,-13,8,3.6);lamp(k,5,18,3.6);
  k.features.push('금빛 양파 돔과 미나레트','복숭아빛 왕궁 회랑','운하와 석조 다리','뾰족한 장식 성문','분수와 원형 광장','강변 시장');
}

function castleTower(k,x,z,r=1.7,h=12,roofColor='#6379a1',y=0,square=false){
  if(square)k.box(x,y+h/2,z,r*2,h,r*2,'#a7b2b4');else k.cylinder(x,y+h/2,z,r,h,'#dedfd0',{segments:16});
  for(let yy=1;yy<h;yy+=1.1){if(square)k.box(x,y+yy,z,r*2+.2,.14,r*2+.2,'#74868d');else k.cylinder(x,y+yy,z,r+.07,.1,'#a5aca7',{segments:16});}
  for(let a=0;a<4;a++){const angle=a*Math.PI/2;k.box(x+Math.sin(angle)*r*.98,y+h*.7,z+Math.cos(angle)*r*.98,.38,1.4,.11,'#323b3e',{rot:angle});}
  k.cone(x,y+h+2,z,r*1.25,4,roofColor,square?4:16);k.collide(x,z,r*2,r*2,{y,h});
}
function buildCapitalCity(k){
  k.floor(67,61,'#86a562',{tile:'grass'});
  prism(k,[[25,-31],[34,-31],[34,31],[25,31],[25,10]],-1,.04,'#5cb7ce');k.collide(29.5,0,9,61,{y:-3,h:3.2,support:false});
  // White cobbled civic terraces rise towards the blue-spired royal castle.
  k.platform(0,.12,6,43,31,'#e0dfcb');k.platform(0,1.5,-8,38,16,'#dcdacb');k.platform(0,3,-22,33,15,'#d6d9cf');
  k.box(0,.74,-8,38,1.48,16,'#aaa99a');k.box(0,1.49,-22,33,2.98,15,'#aeb3a6');
  k.stairs(0,-.2,8,6,.23,.44,'#c8cbbc');raisedStairs(k,0,-13.2,9,6,.25,.44,'#d7d9cb',1.5);
  k.box(0,7.3,-25,19,8.6,10,'#dedfd2');k.collide(0,-25,19,10,{y:3,h:8.6});
  for(let floor=0;floor<3;floor++)for(let i=0;i<9;i++)window(k,-8+i*2,4.5+floor*2.3,-19.9,.64,1.45,'#aaafa7',0,true);
  k.box(0,10.3,-24,8,14.6,7,'#e5e3d6');k.cylinder(0,17.7,-24,4.7,3.7,'#dedfd1',{segments:16});
  for(let i=0;i<14;i++){const a=i*Math.PI/7;k.box(Math.sin(a)*4.6,17.7,-24+Math.cos(a)*4.6,.45,2,.1,'#323f3e',{rot:a});}
  k.cylinder(0,19.7,-24,4.85,.33,'#9da7a0',{segments:16});k.cone(0,23,-24,5.4,6.3,'#657cab',16);
  castleTower(k,-10,-23,2,10.5,'#6985b2',3);castleTower(k,10,-23,2,10.5,'#6985b2',3);
  door(k,0,3,-20.35,3.4,5.1,'#363e3d');arch(k,0,3,-20.25,4.8,6.6,.35,'#b9bfb8');k.stairs(0,-17.8,5,5,.24,.35,'#d7dace');
  // Formal statue on the route to the palace.
  k.cylinder(0,2.1,-11,.7,1.2,'#b4c2bc');k.box(0,3.15,-11,.45,1.25,.36,'#a9b7ad');k.sphere(0,3.98,-11,.24,'#b3c0b5');stroke(k,[[0,3.7,-11],[.65,3.3,-11],[.65,2.8,-11]],'#9daea4',.1);
  house(k,-13,-10,7,5,5,{y:1.5,wall:'#e5e0c6',roof:'#cc8745',timber:false});house(k,13,-10,7,5,4.7,{y:1.5,wall:'#e5e0c6',roof:'#c98040',timber:false});house(k,22,-12,4,4,6,{wall:'#e6debf',roof:'#c68749',timber:false});
  house(k,-21,3,5,4,4.2,{wall:'#e3ddc4',roof:'#c88849',timber:false});market(k,-21,5.4,4,'#b84436');
  // Pavilion, bath house and open two-tier rotunda around the lower plaza.
  k.box(-11,1.8,6,4,3.6,4,'#e0ddc3',{solid:true});pyramidalRoof(k,-11,3.6,6,5,5,3.6,'#cf9657');for(let xx of [-12.4,-9.6])arch(k,xx,0,8.05,1.1,2.3,.16,'#bec8b7');
  k.cylinder(13,2.4,7,4.2,4.8,'#dedecd',{segments:24});k.sphere(13,5,7,4.3,'#d3d7c4',[1,.65,1]);
  for(let i=0;i<12;i++){const a=i*Math.PI/6;k.box(13+Math.sin(a)*4.2,2.4,7+Math.cos(a)*4.2,.4,4.6,.13,'#b4bcab',{rot:a});}door(k,13,0,11.25,1.7,2.8,'#646d5c');k.collide(13,7,8,8,{h:7});
  k.cylinder(0,.25,8,4.4,.5,'#dcdcc8',{segments:32});k.cylinder(0,1.8,8,4.2,3.6,'#dcdcc8',{segments:32});k.cylinder(0,3.75,8,4.5,.3,'#c4ccb9',{segments:32});
  for(let i=0;i<18;i++){const a=i*Math.PI/9;for(let yy of [1.2,2.7])k.box(Math.sin(a)*4.2,yy,8+Math.cos(a)*4.2,.53,.85,.12,'#55634d',{rot:a});}k.cylinder(0,3.8,8,3.8,.05,'#899c72',{segments:32});k.collide(0,8,8,8,{h:4});
  house(k,-17,16,4.6,4.2,3.4,{wall:'#ded8bd',roof:'#d69854',timber:false,chimney:false});pyramidalRoof(k,-17,3.4,16,5.3,5,2.8,'#cf9657');
  for(let p of [[-11,23],[-5,24],[2,24],[9,21],[21,5]])house(k,p[0],p[1],4,3.3,3,{wall:'#e2ddc3',roof:'#c78446',timber:false,chimney:false});
  // Pale sea wall and the front gate with circular sun medallion.
  for(let p of [[-16,27,16,0],[1,27,12,0],[20,18,17,Math.PI/2]]){k.box(p[0],2,p[1],p[2],4,.85,'#d1d5c9',{rot:p[3]});k.collide(p[0],p[1],p[2],.85,{h:4,rot:p[3]});for(let i=0;i<p[2]/2;i++)k.box(p[0]+Math.cos(p[3])*(-p[2]/2+1+i*2),4.3,p[1]-Math.sin(p[3])*(-p[2]/2+1+i*2),.8,.6,1,'#dce0d2',{rot:p[3]});}
  arch(k,12,0,27,7,7,.8,'#d2d9d1');k.torus(12,6,27.45,.78,.13,'#d8af52',[0,0,0]);for(let a=0;a<6;a++)stroke(k,[[12,6,27.5],[12+Math.cos(a*Math.PI/3)*.65,6+Math.sin(a*Math.PI/3)*.65,27.5]],'#d8af52',.045);
  stoneBridge(k,23,27,19,5,.7,'#d6dbca');
  for(let p of [[-5,-12],[5,-12],[-6,-1],[6,-1],[-10,10],[10,16],[-18,7],[18,-3]])lamp(k,p[0],p[1],4.2,p[1]<-4?1.5:0,'#594537');
  for(let p of [[-8,-4],[8,-4],[-10,1],[10,1]]){hedge(k,p[0],p[1],6,2,1.2);}
  const random=rng(321);for(let i=0;i<64;i++){let xx=(random()-.5)*62,zz=(random()-.5)*54;if(xx>-24&&xx<25&&zz>-26&&zz<25)continue;tree(k,xx,zz,3.5+random()*2.8,'round',i);}
  for(let i=0;i<20;i++){const a=i*Math.PI/10;tree(k,Math.sin(a)*27,Math.cos(a)*22,3.8,'round',i);}
  cobbles(k,[[-7,19],[-7,0],[0,-10],[0,-17]],85,42,.18);bench(k,-7,13);bench(k,7,17);
  k.features.push('푸른 첨탑의 흰 왕성','중앙 계단과 시민 광장','원형 회랑과 돔 목욕당','주황 기와 지붕','바닷가 성벽과 문장 성문');
}

function buildDeran(k){
  k.floor(73,66,'#9fb976',{tile:'grass'});
  water(k,[[-34,-26],[-26,-28],[-17,-28],[-4,-29],[15,-28],[26,-30],[36,-27]],7);
  path(k,[[0,31],[0,19],[0,6],[-3,-8],[-2,-19]],7,'#dec996');path(k,[[-23,10],[-5,3],[18,10],[27,20]],5,'#dec996');
  k.platform(-1,1.5,-22,35,14,'#d2cabb');k.box(-1,.74,-22,35,1.48,14,'#9c9a8b');k.stairs(-2,-13.6,9,6,.25,.46,'#b9b9a7');
  k.box(-1,6.2,-23,24,9.4,9,'#95a4a8');k.collide(-1,-23,24,9,{y:1.5,h:9.4});roof(k,-1,10.9,-23,25,10,3,'#566f7b',0,false);
  for(let yy of [3.4,5.8,8.2]){k.box(-1,yy-1,-18.44,24,.15,.13,'#647b85');for(let i=0;i<11;i++)window(k,-11.6+i*2.1,yy,-18.4,.5,.9,'#c2c8c2');}
  for(let p of [[-14,-19],[12,-19],[-14,-27],[12,-27]])castleTower(k,p[0],p[1],1.65,11.2,'#59717d',1.5,true);
  k.box(-1,13,-24,8,6,6,'#a5b0b0');roof(k,-1,16,-24,9,7,3,'#627c86',0,false);
  for(let p of [[-4.5,-24],[2.5,-24]])castleTower(k,p[0],p[1],1,17,'#61737c',1.5,true);
  // Castle entrance is a columned portico and pediment.
  k.box(-2,3.6,-16,9,4.2,3.5,'#a4b0af',{solid:true});for(let xx of [-6,-4,-2,0,2])k.cylinder(xx,3.6,-13.9,.23,4.2,'#bec3b9',{segments:8,solid:true});roof(k,-2,5.8,-15,10,5,2,'#5b7480',0,false);door(k,-2,1.5,-14.15,2,2.7,'#43545b');
  // Left hedge labyrinth has open corridors sized for a 1.5 m character.
  const maze=[[-24,-12,15,1],[-25,-4,13,1],[-31,-8,1,9],[-17,-9,1,7],[-25,-10,7,1],[-22,-7,1,5],[-28,-6,1,5],[-26,-1,9,1],[-16,-4,1,5],[-17,0,7,1]];
  for(const [x,z,w,d] of maze)hedge(k,x,z,w,d,1.25);
  // Long blue-roofed civic hall, external buttresses, tall central door.
  k.box(19,3.7,-5,14,7.4,8,'#a9ae92');roof(k,19,7.4,-5,15,9,3.4,'#638fa8',0,false);k.collide(19,-5,14,8,{h:7.4});
  for(let x=13;x<=25;x+=3){k.box(x,3.5,-.8,.7,7,1.4,'#d4c2a1');stroke(k,[[x,7.7,-1],[x,6.4,.6],[x,.4,.6]],'#e1c7a1',.25);}
  arch(k,14,0,-.9,2.6,5.1,.25,'#8ca194');door(k,14,0,-.75,1.7,3.4,'#506653');
  for(let x=18;x<27;x+=2.1)window(k,x,4,-.88,.57,2,'#62796b');
  k.cylinder(19,.045,-3,11,.09,'#a5b7a8',{segments:32});for(let r of [8,10])k.torus(19,.12,-3,r,.025,'#d3d7b6');
  // Small market lane with individually striped canvas stalls and wheeled carts.
  house(k,-22,7,4,3.8,4,{wall:'#e1d7b5',roof:'#628eab'});house(k,-26,13,4,3.6,3.5,{wall:'#e1d6b6',roof:'#648fae'});
  house(k,-16,3,4,4,4,{wall:'#dfd2ac',roof:'#638eaa'});house(k,-12,7,4,3.8,3.8,{wall:'#dfd1ad',roof:'#6a91a5'});house(k,-8,11,4,3.8,3.8,{wall:'#ddd3b1',roof:'#668da7'});
  for(let [x,z,c] of [[-28,3,'#ad7051'],[-23,18,'#aa634b'],[-15,11,'#877851'],[-10,16,'#a3654e'],[-4,12,'#9b6d50']])market(k,x,z,3.3,c);
  cart(k,-21,12);cart(k,-7,15);for(let p of [[-13,12],[-14,12],[-11,16],[-30,3]])barrel(k,p[0],p[1]);crate(k,-5,11);crate(k,-4,10.5,.8);crate(k,-4,10.5,.7,.8);
  house(k,12,13,5,4.2,4.2,{wall:'#e6d7b2',roof:'#ba5b45',timber:false});house(k,21,16,5,4,3.6,{wall:'#e3d1aa',roof:'#b85745',timber:false});house(k,28,13,4,3.5,4.5,{wall:'#dfd5b6',roof:'#698ead'});
  market(k,12,16,4,'#607e87');house(k,23,25,4,3.8,3.8,{wall:'#dfd1ab',roof:'#628da4'});house(k,28,23,4,3.8,3.8,{wall:'#dfd1ab',roof:'#6a92a7'});
  fountain(k,0,20,3,0,'#d2d8c9'); // Actual plaza circular relief pattern.
  for(let r of [5,6.5,8])k.torus(0,.06,20,r,.025,'#b8c8b4');
  // Massive pointed twin gate against a continuous gray wall.
  for(let p of [[-20,30,25],[20,30,25]]){k.box(p[0],2,p[1],p[2],4,.8,'#8ea2a5');k.collide(p[0],p[1],p[2],.8,{h:4});}
  arch(k,0,0,30,12,5.6,.9,'#9eadaf');for(let xx of [-6.5,6.5])castleTower(k,xx,30,1.45,6.5,'#617b86',0,true);
  for(let xx of [-31,31])k.cylinder(xx,2.6,30,1,5.2,'#9cacac',{segments:12});
  const random=rng(725);for(let i=0;i<44;i++){let xx=(random()-.5)*68,zz=(random()-.5)*60;if((xx>-17&&xx<29&&zz>-29&&zz<28)||(xx<-14&&zz>-15&&zz<19))continue;tree(k,xx,zz,4+random()*2.8,'round',i);}
  for(let p of [[-15,-13],[16,-14],[29,-9],[28,4],[12,3],[-3,2],[7,16]])tree(k,p[0],p[1],4.6,'pine');
  bench(k,7,20);bench(k,-8,22);lamp(k,5,11,4);lamp(k,-5,25,4);cobbles(k,[[0,28],[0,10],[-2,-12]],45,172,.08);
  k.features.push('회청색 왕성과 뾰족한 성문','기둥 현관과 계단','산책 가능한 생울타리 미로','푸른 지붕의 긴 회관','천막 시장과 수레','동심원 분수 광장');
}

function bamboo(k,x,z,h=4.8,seed=0){
  h=Math.round(h*2)/2;
  const colors=['#477e44','#609454','#73a369'];
  for(let i=0;i<3;i++){const xx=x+(i-1)*.22,zz=z+(i%2)*.22;k.cylinder(xx,h/2,zz,.045,h,colors[seed%3],{segments:5});for(let yy=.4;yy<h;yy+=.7)k.cylinder(xx,yy,zz,.059,.055,'#95af69',{segments:5});for(let j=0;j<3;j++){const yy=h*.55+j*.55,dir=(j%2?1:-1);stroke(k,[[xx,yy,zz],[xx+dir*.5,yy+.28,zz+.25]],colors[seed%3],.025);k.sphere(xx+dir*.42,yy+.25,zz+.25,.2,colors[seed%3],[1.6,.3,.6]);}}
  k.collide(x,z,.55,.55,{h});
}
function redCottage(k,x,z,w=5,d=4,opts={}){
  house(k,x,z,w,d,2.8,{...opts,roof:'#c94435',wall:'#efe0b9',timber:true,chimney:false});
  // Rounded terracotta ridges clearly read as East Asian glazed tiles.
  for(let i=0;i<Math.floor(d/.45);i++){const zz=z-d/2+i*.45;stroke(k,[[x-(w+.65)/2,2.86,zz],[x,2.86+w*.4,zz],[x+(w+.65)/2,2.86,zz]],'#de5644',.055);}
  roof(k,x,2.08,z+d*.62,2.3,1.3,.8,'#cf4134',0,false);
}
function buildNormalTown(k){
  k.floor(43,60,'#d9c089',{tile:'sand'});
  water(k,[[-22,22],[-12,21],[-2,22],[10,21],[22,19]],3.1);
  water(k,[[-20,-15],[-14,-13],[-13,-5],[-9,0]],2.8);
  timberBridge(k,0,22,8,3,.55);timberBridge(k,-13,-10,6,2.5,.5);
  path(k,[[0,29],[0,18],[-1,8],[1,-2],[0,-14],[-6,-23]],5.5,'#ead397');cobbles(k,[[0,26],[0,7],[0,-13],[-4,-23]],110,318,.065);
  // Rust-colored high cliffs behind the shrine, with explicit layered strata.
  for(let i=0;i<8;i++){const xx=-18+i*4.4,hh=8+(i%3)*1.6;rock(k,xx,-28,3.5,hh,'#b95532');for(let yy=1;yy<hh;yy+=1.4)stroke(k,[[xx-2.7,yy,-24.7],[xx,yy+.25,-24.4],[xx+2.7,yy-.1,-24.7]],'#e0ad78',.065);}
  redCottage(k,-8,-22,7,5);redCottage(k,10,-10,4.2,3.6);redCottage(k,10,5,5,4);redCottage(k,-9,14,5,4);
  // Reference center shop: low brown roof, circular lattice windows and red cloth.
  house(k,-9,-1,7,5,3,{wall:'#eee0ba',roof:'#94603a',timber:true,chimney:false});
  for(let xx of [-11,-7]){k.torus(xx,1.75,1.62,.44,.07,'#80563e',[0,0,0]);for(let a=0;a<3;a++)stroke(k,[[xx-.35,1.5+a*.22,1.67],[xx+.35,1.5+a*.22,1.67]],'#855c40',.025);}
  for(let xx=-10;xx<-8;xx+=.4)k.box(xx,2.22,1.8,.36,.56,.035,'#c84430');k.text('茶',-13.2,1.8,1.6,{width:.7,height:1,color:'#f4e3b3',background:'#b64032'});
  market(k,-9,3,3.2,'#c84430',{fruit:false});
  // Stone guardian pouring a narrow stream into a spring below the red cliff.
  k.box(8,.3,-23,2.4,.6,1.9,'#aaa392');k.cylinder(8,1.55,-23,.42,2.5,'#b4aa94',{segments:7});k.sphere(8,3.05,-23,.45,'#c4b69b');
  k.sphere(7.4,2.7,-22.85,.3,'#b4a48c',[.75,1.5,.7]);k.sphere(8.6,2.7,-22.85,.3,'#b4a48c',[.75,1.5,.7]);
  stroke(k,[[8,2.65,-22.6],[8,1.8,-22.2],[8,.25,-21.8]],'#96dae1',.08);k.cylinder(8,.1,-21.7,1.45,.1,'#62b7c0',{segments:18});
  for(let xx of [6.5,9.5])lamp(k,xx,-22.5,3.5,0,'#6c5239');
  // Covered foreground gate, carved stone supports and bamboo edge planting.
  for(let xx of [-1.8,1.8]){k.cylinder(xx,1.3,16,.22,2.6,'#bbae8a',{segments:8});for(let yy of [.1,1.1,2.3])k.torus(xx,yy,16,.25,.045,'#947b54');}
  roof(k,0,2.6,16,5.4,2,1.7,'#ca4437');
  k.box(0,2.6,16,4.5,.18,.22,'#967552');k.interactions.push({name:'대나무 마을 문',position:[0,.5,16.5],kind:'inspect',text:'붉은 기와와 대나무 숲, 징검돌 길이 이어지는 작은 마을입니다.'});
  k.cylinder(-3,1.35,-8,.56,2.7,'#bc7251',{segments:12});k.cylinder(-3,2.8,-8,.68,.27,'#d49a6d',{segments:12});for(let i=0;i<5;i++)k.sphere(-3+Math.sin(i)*.5,.6+i*.4,-7.6,.17,'#e1b184',[1,.6,.3]);
  cart(k,-4,-1);barrel(k,-12,2);barrel(k,13,7);crate(k,7,-8);fence(k,-15,-8,5,Math.PI/2);
  const random=rng(876);for(let side of [-1,1])for(let i=0;i<25;i++){const xx=side*(16+random()*4),zz=-23+i*1.95;bamboo(k,xx,zz,3.6+random()*2.2,i);}
  for(let p of [[-15,16],[14,12],[-5,-17],[12,-19],[4,18],[-6,23]]){for(let i=0;i<3;i++)k.sphere(p[0]+i*.13,.23,p[1],.18,'#729246',[.35,1.7,.35]);}
  bench(k,-5,10);bench(k,5,11);k.features.push('붉은 기와와 원형 창문','촘촘한 대나무 숲','붉은 절벽의 층리','수호상 샘과 실개천','목조 다리와 돌길','찻집의 붉은 천');
}

function boat(k,x,z,length=3,width=1.1,y=.15,rot=0,large=false){
  const T=k.THREE,group=new T.Group();group.position.set(x,y,z);group.rotation.y=rot;k.root.add(group);const old=k.root;k.root=group;
  // Real hollow hull assembled as curved timber strakes; no solid screenshot proxy.
  const count=large?8:4;
  for(let layer=0;layer<count;layer++)for(let side of [-1,1]){
    const yy=.05+layer*(large?.18:.1),rr=width/2*(.52+layer/count*.48),pts=[];
    for(let i=0;i<=18;i++){const t=i/18,zz=(t-.5)*length,xx=side*rr*Math.sin(Math.PI*t);pts.push([xx,yy+Math.pow(Math.abs(t-.5)*2,5)*(large?1.6:.35),zz]);}
    stroke(k,pts,layer%2?'#956548':'#b67b4f',large?.1:.06);
  }
  for(let i=1;i<15;i++){const zz=-length/2+i*length/15,ww=width*.8*Math.sin(i*Math.PI/15);k.box(0,.25,zz,ww,.1,length/15-.025,'#bb8b59');}
  for(let zz of [-length*.25,0,length*.25])k.box(0,.55,zz,width*.75,.13,.3,'#bd9568');
  if(large){
    const mh=length*.72;k.cylinder(0,mh/2,0,.095,mh,'#8d6941',{segments:10});
    stroke(k,[[-width*.43,1.4,-length*.35],[0,mh,0],[width*.43,1.4,-length*.35]],'#504a39',.035);
    stroke(k,[[-width*.44,1.4,length*.35],[0,mh,0],[width*.44,1.4,length*.35]],'#504a39',.035);
    stroke(k,[[0,1.3,-length*.48],[0,mh,0],[0,2,length*.47]],'#574a36',.035);
    stroke(k,[[-width*.45,mh*.7,0],[width*.45,mh*.7,0]],'#8a6840',.085);
    // Furled canvas hangs in four scallops along the horizontal spar.
    for(let i=0;i<4;i++){const xx=-width*.44+(i+.5)*width*.88/4;const shape=new T.Shape();shape.moveTo(-width*.11,0);shape.quadraticCurveTo(0,-.9,width*.11,0);shape.lineTo(width*.11,.12);shape.lineTo(-width*.11,.12);shape.closePath();const g=new T.ExtrudeGeometry(shape,{depth:.07,bevelEnabled:false});mesh(k,g,'#f0e8cd',xx,mh*.69,0);}
    for(let end of [-1,1]){
      const zz=end*length/2;stroke(k,[[0,.4,zz],[0,1.4,zz+end*.1],[0,3.4,zz+end*.35],[0,3.7,zz-end*.4],[0,3.2,zz-end*.65]],'#c2915d',.2);
      k.torus(0,3.4,zz-end*.4,.36,.1,'#d6a877',[0,Math.PI/2,0]);
    }
    k.torus(0,1.15,length*.24,.4,.065,'#d0a568',[0,0,0]);for(let i=0;i<6;i++){const a=i*Math.PI/3;stroke(k,[[0,1.15,length*.24],[Math.sin(a)*.36,1.15+Math.cos(a)*.36,length*.24]],'#8b623d',.04);}
    k.box(width*.25,.7,-length*.15,1.1,.4,1.2,'#73835b');k.box(-width*.2,.7,-length*.24,.85,.4,1.2,'#698061');
  }else{stroke(k,[[width*.3,.6,-length*.2],[width*1.4,.2,length*.1]],'#b19a6d',.035);}
  k.root=old;
  if(large){k.surface(x,z,width*.68,length*.75,y+.33,{rot});k.interactions.push({name:'배의 갑판',position:[x,y+.8,z],kind:'inspect',text:'휘어진 선체의 나무 판재, 말린 돛, 장력 로프와 조타륜을 가까이 살펴보세요.'});}
  return group;
}
function buildPort(k){
  k.floor(48,45,'#539fb3',{tile:'water'});
  k.box(0,-.3,10,48,.5,26,'#438fa5');k.collide(0,12,48,26,{y:-3,h:3.3,support:false});
  // Full-height quay and its walkable cobbled surface.
  k.box(0,.59,-10,48,1.18,22,'#b0b5a3');k.platform(0,1.2,-10,48,22,'#d2d1b3');
  for(let i=0;i<30;i++)k.box(-24+(i+.5)*48/30,.55,.96,1.5,.75,.12,i%2?'#9c9f88':'#a9ad92');
  for(let i=0;i<18;i++)k.box(-24+(i+.5)*48/18,1.32,1.25,2.58,.18,2.4,'#bf936b');k.surface(0,1.2,48,2.4,1.43);
  // A perpendicular pier reaching the Viking merchant vessel.
  for(let i=0;i<22;i++)k.box(-8,1.26,2.7+i*.48,5.5,.16,.44,'#b98a5d');k.surface(-8,7.8,5.5,11,1.35);
  for(let xx of [-10.3,-5.7])for(let zz of [3,6,9,12])k.cylinder(xx,.2,zz,.12,2.6,'#70593f',{segments:8});
  for(let xx=-22;xx<=22;xx+=4.5){k.cylinder(xx,1.55,1.55,.085,.55,'#96714b',{segments:8});stroke(k,[[xx,1.38,1.6],[xx,1.38,2.4],[xx+.15,.5,2.9]],'#655841',.028);}
  // Harbor backdrop: tall pastel dwellings and shop fronts under three awnings.
  house(k,-16,-15,7,6,8,{y:1.2,wall:'#b9b083',roof:'#beb18d',timber:false});house(k,-7,-17,7,6,8,{y:1.2,wall:'#d7cda0',roof:'#a29978',timber:false});
  house(k,5,-13,10,7,8,{y:1.2,wall:'#e5d5a5',roof:'#9b9b78',timber:false});house(k,18,-15,8,6,7,{y:1.2,wall:'#d4cfac',roof:'#a19477',timber:false});
  // Low green roof over timber-framed general store.
  k.box(4,3.1,-6,11,3.8,5,'#826e48');roof(k,4,5,-6,12,6,1.8,'#91a37a',Math.PI/2,false);k.collide(4,-6,11,5,{y:1.2,h:3.8});
  for(let xx of [-1,1.5,4,6.5,9])k.box(xx,3.1,-3.46,.16,3.8,.16,'#6e573b');
  window(k,3.4,3.2,-3.4,1.7,1.7,'#634d34');window(k,7,3.2,-3.4,1.7,1.7,'#634d34');door(k,0,1.2,-3.4,1.3,2.5,'#82693d');
  market(k,-2,-2.5,4.1,'#b96f4f',{y:1.2});market(k,4,-2.2,4,'#63a99a',{y:1.2,fruit:false});market(k,18,-2.5,6,'#c05d6f',{y:1.2,fruit:false});
  k.text('海の市',-2,4.1,-1.42,{width:2.7,height:.62,color:'#81984a',background:'#e6dda1'});
  for(let p of [[-15,-6],[-14,-6],[8,-2],[9,-2],[9,-1],[12,-4],[20,-6]])barrel(k,p[0],p[1],.44,1.2);
  for(let p of [[-18,-3],[-17,-3],[10,-7],[11,-7],[12,-7]])crate(k,p[0],p[1],.8,1.2);crate(k,11,-7,.75,2);
  cart(k,14,-7,Math.PI/2,1.2);k.stairs(-13,-6,4,4,.3,.4,'#b8b99f');
  // Main ship aligned along the pier; deck can be boarded from the gangplank.
  const ship=boat(k,-1,12,16,5,.28,Math.PI/2,true);
  ship.userData.dynamic=true;
  for(let i=0;i<7;i++){const xx=-5.2+i*.4,yy=1.3-i*.1;k.box(xx,yy-.04,10.1,.38,.08,1.1,'#a58256');k.surface(xx,10.1,.42,1.1,yy);}
  for(let p of [[-18,5,4,Math.PI/2],[-16,10,3.5,Math.PI/2],[15,14,4,-.7],[20,19,3.6,-.6]])boat(k,p[0],p[1],p[2],1.3,.1,p[3]);
  // Floating casks, foam strokes and softly rocking small boats.
  for(let p of [[-15,13],[12,21],[18,9]]){const group=new k.THREE.Group();group.position.set(p[0],.08,p[1]);group.rotation.z=.3;k.root.add(group);const old=k.root;k.root=group;barrel(k,0,0,.36);k.root=old;}
  k.animated.push((dt,t)=>{ship.rotation.z=Math.sin(t*.8)*.008;ship.position.y=.28+Math.sin(t*.8)*.03;});
  for(let i=0;i<38;i++){let xx=-23+(i*7.13%46),zz=3+(i*3.71%19);stroke(k,[[xx,.06,zz],[xx+.7,.06,zz+.04]],'#8fcbcf',.018);}
  lamp(k,-20,-1,4,1.2);lamp(k,12,-1,4,1.2);bench(k,-11,-7,0,1.2);
  k.features.push('탑승 가능한 긴 목조 범선','선체의 판재와 말린 돛','돛대 로프와 조타륜','나무 부두와 계선 기둥','줄무늬 차양의 항구 시장','노 젓는 배와 떠다니는 통');
}

function buildVillage(k){
  k.floor(62,58,'#c2cb8b',{tile:'grass'});
  water(k,[[-31,-25],[-24,-22],[-26,-12],[-30,-5]],7);
  water(k,[[-28,23],[-12,24],[0,25],[16,24],[30,20]],7);
  path(k,[[-20,25],[-19,14],[-12,5],[-1,1],[11,-1],[20,-8]],6,'#e9ddb0');path(k,[[0,21],[0,10],[3,1],[3,-16]],5,'#e9ddb0');
  // Tall, varied timber-framed houses with distinct warm/cool tiled roofs.
  house(k,-18,-6,5,4.5,8,{roof:'#d49c4d',wall:'#e5d7b4'});house(k,-10,-5,5,4.6,7.5,{roof:'#d7bb58',wall:'#eadfbf'});
  house(k,-24,4,4.5,4,6.3,{roof:'#d9bd61',wall:'#e9dfbb'});house(k,12,-18,6,5,9,{roof:'#9cab58',wall:'#d5cfac'});
  house(k,24,-12,5.5,4.8,10,{roof:'#68a4a6',wall:'#ded8b5'});house(k,21,7,7,6,9,{roof:'#c6ae56',wall:'#e0d7b5'});
  // Separate tower roof on the prominent foreground manor.
  pyramidalRoof(k,21,9,7,8,7,5.2,'#d6bd5f');window(k,21,10.6,10.15,1,1.15);k.box(21,1.3,10.15,1.7,2.6,.14,'#665a3c');
  // Center abbey: square belfry, buttresses, yellow roof and entrance stair.
  k.box(-1,3.3,-16,7,6.6,5,'#dfd0aa');k.collide(-1,-16,7,5,{h:6.6});roof(k,-1,6.6,-16,8,6,3,'#bca852');
  k.box(-1,7.1,-16,3.8,4.8,3.8,'#d7c7a3');pyramidalRoof(k,-1,9.5,-16,5,5,4.3,'#c9ad4b');
  for(let a=0;a<4;a++){const angle=a*Math.PI/2;window(k,-1+Math.sin(angle)*1.96,7.55,-16+Math.cos(angle)*1.96,1,1.8,'#b3a17a',angle,true);}
  door(k,-1,0,-13.45,1.7,2.7,'#756442');arch(k,-1,0,-13.3,2.6,3.6,.22,'#bcae88');k.stairs(-1,-11.7,4,3,.2,.35,'#bdbda5');
  for(let xx of [-4.5,2.5])k.box(xx,2,-15.9,.6,4,5.2,'#c4ba96');
  // Red church steeple beside the entry arch, with carved stone bell openings.
  k.box(-10,3.3,19,3.4,6.6,3.4,'#b5b393');k.box(-10,5.2,19,3.6,.18,3.6,'#8d9579');
  for(let a=0;a<4;a++){const angle=a*Math.PI/2;window(k,-10+Math.sin(angle)*1.75,5.9,19+Math.cos(angle)*1.75,.75,1.3,'#8c9379',angle,true);}
  k.cone(-10,9.1,19,2.6,5,'#a84a42',4);k.cylinder(-10,11.8,19,.05,1,'#604f39');k.box(-10,12.15,19,.75,.08,.08,'#604f39');door(k,-10,0,20.76,1.1,2,'#6c623f');k.collide(-10,19,3.4,3.4,{h:7});
  arch(k,-22,0,16,7,5,.65,'#baa987');for(let xx of [-25.5,-18.5]){k.box(xx,1.9,16,.75,3.8,.95,'#b7baa2');k.cylinder(xx,4,16,.55,.45,'#ced0b6');}stroke(k,[[-25.2,3.75,16.3],[-22,4.5,16.3],[-18.8,3.75,16.3]],'#9a7745',.5);
  // Alchemist shop with three dimensional potion sign and striped awning.
  house(k,6,4,5.7,4.5,3.2,{roof:'#bd8762',wall:'#d3a27c',timber:false,chimney:false});market(k,6,6.6,5,'#c87764',{fruit:false});
  k.box(6,4.35,6.7,4,.4,.2,'#b89e52');k.text('薬',4.8,4.85,6.85,{width:.85,height:.85,color:'#cfb254',background:'#71624a'});
  k.sphere(6,5.18,6.9,.54,'#409da2',[1,1,.4]);k.cylinder(6,5.84,6.9,.17,.8,'#619f96');k.torus(6,6.23,6.9,.18,.055,'#e3ca76');
  k.sphere(7.2,5.1,6.9,.35,'#79ad63',[1,1.3,.5]);k.cylinder(7.2,5.64,6.9,.1,.65,'#94b67e');
  stroke(k,[[3.9,4.6,6.91],[4.3,5.4,6.91],[4.9,5.1,6.91],[5.3,5.6,6.91],[5.7,4.8,6.91]],'#d3bd58',.12);
  // Fenced herb garden and open well, with bucket, axle and crank.
  for(let p of [[-4,10,7,0],[-7.5,12,4,Math.PI/2],[-.5,12,4,Math.PI/2]])fence(k,p[0],p[1],p[2],p[3]);
  k.cylinder(-4,.5,12,1.05,1,'#989c81',{segments:12});k.cylinder(-4,1.02,12,.72,.03,'#365d62',{segments:16});
  for(let xx of [-5,-3])k.box(xx,1.5,12,.1,3,.1,'#7b6847');roof(k,-4,3,12,3,2,1,'#c19b59',0,false);
  stroke(k,[[-5.1,2.3,12],[-2.9,2.3,12]],'#695737',.07);stroke(k,[[-4,2.3,12],[-4,1.1,12]],'#ab9a6a',.024);k.cylinder(-4,1.2,12,.21,.34,'#9c7d49');
  for(let i=0;i<8;i++)bush(k,-6+(i%4)*1.3,10.8+Math.floor(i/4)*2.1,.32,'#709d48');
  // Covered terrace at left, fuchsia entrance kiosk, route signs and low fences.
  market(k,-8,1,4,'#c98b53',{fruit:false});fence(k,-8,3,4);k.box(-15.5,.9,-1,1.1,1.8,1.15,'#c571a7');pyramidalRoof(k,-15.5,1.8,-1,1.3,1.3,.7,'#e5a4c2');
  k.cylinder(-1,1.55,5,.075,3.1,'#78633e');k.box(-1.45,2.7,5,.85,.3,.1,'#c5a66a');k.box(-.52,2.4,5,.85,.3,.1,'#c5a66a');
  // Front aqueduct wall with large open arches over the river.
  for(let xx of [-8,6,20]){arch(k,xx,-1,24,13,5,.8,'#a9b4aa');for(let side of [-1,1])k.box(xx+side*6.6,1.6,24,.6,5.2,1.2,'#919f98');}
  k.box(6,4.6,24,41,.45,2.4,'#bcc6b4');k.surface(6,24,41,2.4,4.83);
  for(let xx=-14;xx<=26;xx+=2)k.box(xx,5.35,24,.5,1,2.3,'#c7cdb9');
  // Bridge-side house and an accessible crossing beside the wall.
  house(k,8,21,7,4.4,4.3,{y:4.83,roof:'#cd8e53',wall:'#e7d7b2'});stoneBridge(k,-17,24,13,4,.8,'#bdc4a7');
  raisedStairs(k,16,19.2,3,19,4.83/19,.38,'#bcc4ab',0,Math.PI);
  const random=rng(613);for(let i=0;i<42;i++){let xx=(random()-.5)*58,zz=(random()-.5)*52;if(xx>-26&&xx<28&&zz>-23&&zz<27)continue;tree(k,xx,zz,4+random()*2,'round',i);}
  for(let p of [[-28,13],[28,3],[-24,-16],[20,-24],[7,-24],[25,17]])tree(k,p[0],p[1],4.8,'pine');
  for(let p of [[-17,-2],[-12,1],[3,-11],[10,-16],[23,12]]){bush(k,p[0],p[1],.8);bush(k,p[0]+.8,p[1]+.4,.65);}
  barrel(k,4,7);crate(k,9,7);bench(k,1,16);bench(k,-14,7);lamp(k,12,12,3.4);cobbles(k,[[-19,15],[-12,5],[0,1],[12,-3]],45,164,.06);
  k.features.push('다채로운 목골조 주택','황금 지붕의 종탑과 붉은 교회','입체 물약 간판의 약방','도르래 우물과 허브 정원','아치형 수로교와 다리 위 집','기와 지붕과 작은 울타리');
}

export const cityMaps = [
  {id:'Academy',name:'학원',category:'마을',file:'Academy.png',description:'종탑 학원, 폭포 유적, 거목과 원형극장이 있는 숲속 캠퍼스',width:110,depth:92,spawn:[-4,6],fog:'#cbd7b3',sky:'#c3e1e2',build:buildAcademy},
  {id:'Asuria',name:'아수리아',category:'마을',file:'Asuria.jpg',description:'강으로 나뉜 금빛 돔의 왕궁과 운하 도시',width:76,depth:65,spawn:[8,29],fog:'#d9e5bd',sky:'#a8d5e6',build:buildAsuria},
  {id:'CapitalCity',name:'수도',category:'마을',file:'CapitalCity.jpg',description:'푸른 첨탑의 왕성과 흰 돌 광장이 있는 바닷가 수도',width:67,depth:61,spawn:[10,23],fog:'#c6dfd7',sky:'#85cddd',build:buildCapitalCity},
  {id:'Deran',name:'데란',category:'마을',file:'Deran.jpg',description:'회청색 왕성, 생울타리 미로, 천막 시장과 분수 광장',width:73,depth:66,spawn:[0,27],fog:'#c8d5b5',sky:'#bfd7df',build:buildDeran},
  {id:'NormalTown',name:'붉은 기와 마을',category:'마을',file:'NormalTown.jpg',description:'대나무 숲, 붉은 절벽과 실개천을 따라 걷는 작은 마을',width:43,depth:60,spawn:[0,26],fog:'#d7cf9e',sky:'#e2dfc2',build:buildNormalTown},
  {id:'Port',name:'항구',category:'마을',file:'Port.png',description:'목조 범선에 오르고 줄무늬 차양의 항구 시장을 둘러보세요',width:48,depth:45,spawn:[-13,-3],fog:'#c5d6cb',sky:'#a1d1dd',build:buildPort},
  {id:'Village',name:'목골조 마을',category:'마을',file:'Village.jpg',description:'교회와 약방, 우물 정원과 수로교가 있는 다채로운 마을',width:62,depth:58,spawn:[0,17],fog:'#d2d9b6',sky:'#bfdad9',build:buildVillage}
];

