import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

export class WorldKit {
  constructor(descriptor) {
    this.THREE = THREE;
    this.root = new THREE.Group();
    this.width = descriptor.width; this.depth = descriptor.depth;
    this.colliders = []; this.surfaces = []; this.features = [];
    this.interactions = []; this.animated = [];
    this.materials = new Map(); this.geometries = new Map(); this.textures = [];
    this.descriptor = descriptor;
  }
  material(color, options = {}) {
    const key = JSON.stringify([color, options]);
    if (!this.materials.has(key)) this.materials.set(key, new THREE.MeshStandardMaterial({color, roughness:.88, ...options}));
    return this.materials.get(key);
  }
  geometry(key, create) {
    if (!this.geometries.has(key)) this.geometries.set(key, create());
    return this.geometries.get(key);
  }
  mesh(geometry, color, x, y, z, options = {}) {
    const mesh = new THREE.Mesh(geometry, options.material || this.material(color));
    mesh.position.set(x,y,z); mesh.rotation.y = options.rot || 0;
    mesh.castShadow = true; mesh.receiveShadow = true;
    mesh.userData.dynamic = !!options.dynamic;
    this.root.add(mesh); return mesh;
  }
  box(x,y,z,w,h,d,color,options={}) {
    const m = this.mesh(this.geometry(`b:${w},${h},${d}`,()=>new THREE.BoxGeometry(w,h,d)),color,x,y,z,options);
    if(options.solid) this.collide(x,z,w,d,{y:y-h/2,h,rot:options.rot || 0});
    return m;
  }
  cylinder(x,y,z,r,h,color,options={}) {
    const top=options.top ?? r, segments=options.segments ?? 12;
    const m=this.mesh(this.geometry(`c:${top},${r},${h},${segments}`,()=>new THREE.CylinderGeometry(top,r,h,segments)),color,x,y,z,options);
    if(options.solid)this.collide(x,z,r*2,r*2,{y:y-h/2,h});
    return m;
  }
  sphere(x,y,z,r,color,scale=[1,1,1]) {
    const m=this.mesh(this.geometry(`s:${r}`,()=>new THREE.SphereGeometry(r,12,8)),color,x,y,z);
    m.scale.set(...scale); return m;
  }
  cone(x,y,z,r,h,color,segments=12) {
    return this.mesh(this.geometry(`n:${r},${h},${segments}`,()=>new THREE.ConeGeometry(r,h,segments)),color,x,y,z);
  }
  torus(x,y,z,r,tube,color,rotation=[Math.PI/2,0,0]) {
    const m=this.mesh(this.geometry(`t:${r},${tube}`,()=>new THREE.TorusGeometry(r,tube,6,24)),color,x,y,z);
    m.rotation.set(...rotation); return m;
  }
  line(points,color,radius=.04) {
    if(points.length<2) return null;
    const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
    return this.mesh(new THREE.TubeGeometry(curve,Math.max(8,points.length*4),radius,5,false),color,0,0,0);
  }
  text(text,x,y,z,{width=1.3,height=.45,color='#f7efd5',background='#334c42',rot=0}={}) {
    const canvas=document.createElement('canvas'); canvas.width=512; canvas.height=128;
    const ctx=canvas.getContext('2d'); ctx.fillStyle=background;ctx.fillRect(0,0,512,128);
    ctx.strokeStyle=color;ctx.lineWidth=5;ctx.strokeRect(8,8,496,112);
    ctx.fillStyle=color;ctx.font='bold 44px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,256,66,470);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;this.textures.push(texture);
    const mat=new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide});
    const m=new THREE.Mesh(new THREE.PlaneGeometry(width,height),mat);m.position.set(x,y,z);m.rotation.y=rot;this.root.add(m);return m;
  }
  floor(width,depth,color,{tile='stone',y=0}={}) {
    const texture=this.pattern(tile,color,width,depth);
    const material=new THREE.MeshStandardMaterial({map:texture,roughness:tile==='water'?.34:.92,metalness:tile==='water'?.12:0});
    this.box(0,y-.09,0,width,.18,depth,color,{material});this.surface(0,0,width,depth,y);
  }
  pattern(kind,color,width,depth) {
    const c=document.createElement('canvas');c.width=c.height=256;const ctx=c.getContext('2d');
    ctx.fillStyle=color;ctx.fillRect(0,0,256,256);
    let seed=31973;const random=()=>{seed=(seed*16807)%2147483647;return(seed-1)/2147483646;};
    for(let i=0;i<1500;i++){ctx.fillStyle=`rgba(${random()>.5?'255,255,230':'20,30,20'},${random()*.055})`;ctx.fillRect(random()*256,random()*256,random()*5+1,random()*3+1);}
    ctx.lineWidth=kind==='wood'?2:3;ctx.strokeStyle=kind==='wood'?'#60462c45':'#34423432';
    if(kind==='stone'||kind==='tile'||kind==='wood'){
      const rows=kind==='wood'?8:4;
      for(let row=0;row<rows;row++){
        const yy=row*256/rows;ctx.beginPath();ctx.moveTo(0,yy);ctx.lineTo(256,yy);ctx.stroke();
        const offset=kind==='stone'||kind==='wood'?(row%2)*32:0;
        for(let xx=offset;xx<256;xx+=kind==='wood'?128:64){ctx.beginPath();ctx.moveTo(xx,yy);ctx.lineTo(xx,yy+256/rows);ctx.stroke();}
      }
    }
    if(kind==='grass'){for(let i=0;i<150;i++){const x=random()*256,z=random()*256;ctx.strokeStyle=i%2?'#56773b35':'#effbb225';ctx.beginPath();ctx.moveTo(x,z);ctx.lineTo(x+2,z-5);ctx.stroke();}}
    if(kind==='water'){for(let i=0;i<48;i++){const x=random()*256,z=random()*256,len=8+random()*35;ctx.strokeStyle=i%3?'#d4f6f633':'#245d7123';ctx.lineWidth=.7+random();ctx.beginPath();ctx.moveTo(x,z);ctx.quadraticCurveTo(x+len*.5,z-3,x+len,z);ctx.stroke();}}
    const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
    texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(width/2,depth/2);texture.anisotropy=4;
    this.textures.push(texture);return texture;
  }
  wall(x,z,w,h,d,color,rot=0){return this.box(x,h/2,z,w,h,d,color,{rot,solid:true});}
  platform(x,y,z,w,d,color){this.box(x,y-.1,z,w,.2,d,color,{solid:true});this.surface(x,z,w,d,y);}
  stairs(x,z,w,count,rise,run,color,heading=0) {
    const total=count*run;
    for(let i=0;i<count;i++){
      const localZ=total/2-(i+.5)*run;
      const xx=x+Math.sin(heading)*localZ, zz=z+Math.cos(heading)*localZ, top=(i+1)*rise;
      this.box(xx,top/2,zz,w,top,run,color,{rot:heading});this.surface(xx,zz,w,run,top,{rot:heading});
      this.box(xx,top+.008,zz,w,.018,.05,'#bba982',{rot:heading});
    }
  }
  collide(x,z,w,d,{y=0,h=10,rot=0,camera=true,support=true,shape='rect',...metadata}={}){this.colliders.push({x,z,w,d,y,h,rot,camera,support,shape,...metadata});}
  surface(x,z,w,d,y,{rot=0}={}){this.surfaces.push({x,z,w,d,y,rot});}
  optimize() {
    // Material batches are spatial outdoors: a distant grove no longer keeps
    // every tree of that color inside the camera frustum. All original triangles
    // and indexed vertices survive; moving groups and authored instances remain.
    this.root.updateMatrixWorld(true);
    const candidates=[],batches=new Map(),canonical=new Map(),staticTransforms=new Set(),inverseRoot=this.root.matrixWorld.clone().invert();
    const indoor=this.descriptor.category==='실내'||this.descriptor.category==='던전';
    const span=Math.max(this.width,this.depth);
    const chunkSize=this.descriptor.renderChunkSize??(indoor?0:(span>=90||span<=40?20:24)),bounds=new THREE.Box3(),relative=new THREE.Matrix4(),center=new THREE.Vector3(),extent=new THREE.Vector3();
    const functionIds=new WeakMap(),materialKeys=new WeakMap();let nextFunction=0;
    const serialize=(value)=>{
      if(value===undefined)return ['undefined'];
      if(value===null||typeof value!=='object'){
        if(typeof value==='function'){if(!functionIds.has(value))functionIds.set(value,++nextFunction);return ['function',functionIds.get(value)];}
        return value;
      }
      if(value.isTexture)return ['texture',value.uuid];
      if(Array.isArray(value))return value.map(serialize);
      if(ArrayBuffer.isView(value))return [value.constructor.name,...value];
      if(typeof value.toArray==='function')return [value.constructor.name,...value.toArray()];
      return Object.fromEntries(Object.keys(value).sort().filter(key=>!key.startsWith('_')).map(key=>[key,serialize(value[key])]));
    };
    const materialKey=material=>{
      if(materialKeys.has(material))return materialKeys.get(material);
      if(!material.isMeshStandardMaterial||Object.values(material).some(v=>v?.isTexture))return null;
      // Custom shader hooks can depend on material/object identity.
      if(material.onBeforeCompile!==THREE.Material.prototype.onBeforeCompile||material.customProgramCacheKey!==THREE.Material.prototype.customProgramCacheKey)return null;
      const ignored=new Set(['id','uuid','name','version','userData','_listeners']);
      const key=JSON.stringify(Object.keys(material).sort().filter(key=>!ignored.has(key)).map(key=>[key,serialize(material[key])]));
      materialKeys.set(material,key);return key;
    };
    this.root.traverse(m=>{if(m.isMesh&&!m.isInstancedMesh&&!m.isSkinnedMesh)candidates.push(m);});
    for(const m of candidates){
      let moving=false,visible=true;
      for(let ancestor=m;ancestor;ancestor=ancestor.parent){moving ||= !!ancestor.userData.dynamic;visible &&= ancestor.visible;}
      const g=m.geometry,mat=m.material;
      if(moving||!visible||Array.isArray(mat)||mat.transparent||!g.attributes.position||Object.keys(g.morphAttributes).length)continue;
      if(g.drawRange.start!==0||Number.isFinite(g.drawRange.count))continue;
      if(m.onBeforeRender!==THREE.Object3D.prototype.onBeforeRender||m.onAfterRender!==THREE.Object3D.prototype.onAfterRender)continue;
      if(m.customDepthMaterial||m.customDistanceMaterial||m.onBeforeShadow!==THREE.Object3D.prototype.onBeforeShadow||m.onAfterShadow!==THREE.Object3D.prototype.onAfterShadow)continue;
      if(Object.values(g.attributes).some(a=>a.gpuType!==undefined&&a.gpuType!==THREE.FloatType))continue;
      const key=materialKey(mat);
      if(key!==null){
        if(canonical.has(key)){
          m.material=canonical.get(key);
          if(m.material!==mat)this.materials.set(`optimized-original:${mat.uuid}`,mat);
        }else canonical.set(key,mat);
      }
      // Extra custom attributes with different item sizes require distinct batches.
      const custom=Object.keys(g.attributes).filter(a=>!['position','normal','uv','uv1','uv2','color','tangent'].includes(a)).sort().map(a=>`${a}:${g.attributes[a].itemSize}`).join(',');
      let cell='room';
      if(chunkSize>0&&m.frustumCulled){
        if(!g.boundingBox)g.computeBoundingBox();relative.multiplyMatrices(inverseRoot,m.matrixWorld);
        bounds.copy(g.boundingBox).applyMatrix4(relative);bounds.getCenter(center);bounds.getSize(extent);
        // A huge floor or terrace must not enlarge a batch of small nearby props.
        cell=Math.max(extent.x,extent.z)>chunkSize*1.75?`large:${m.uuid}`:`${Math.floor((center.x+this.width/2)/chunkSize)},${Math.floor((center.z+this.depth/2)/chunkSize)}`;
      }
      const batchKey=[m.material.uuid,m.castShadow,m.receiveShadow,m.layers.mask,m.renderOrder,m.frustumCulled,custom,cell].join('/');
      if(!batches.has(batchKey))batches.set(batchKey,[]);batches.get(batchKey).push(m);
      m.updateMatrix();m.matrixAutoUpdate=false;staticTransforms.add(m);
    }
    for(const meshes of batches.values()){
      if(meshes.length<2)continue;
      const clones=[],schemas=new Map();let compatible=true;
      try{
        for(const m of meshes){
          const clone=m.geometry.clone(),transform=inverseRoot.clone().multiply(m.matrixWorld);
          clones.push(clone);if(!clone.attributes.normal)clone.computeVertexNormals();
          // Deinterleave and normalize attribute storage so custom roofs without
          // UVs can merge with boxes, while preserving every supplied attribute.
          for(const [name,attribute] of Object.entries(clone.attributes)){
            const data=new Float32Array(attribute.count*attribute.itemSize);
            for(let i=0;i<attribute.count;i++)for(let c=0;c<attribute.itemSize;c++)data[i*attribute.itemSize+c]=attribute.getComponent(i,c);
            clone.setAttribute(name,new THREE.BufferAttribute(data,attribute.itemSize));
            if(schemas.has(name)&&schemas.get(name)!==attribute.itemSize)compatible=false;
            schemas.set(name,attribute.itemSize);
          }
          clone.applyMatrix4(transform);
          if(transform.determinant()<0){
            // The renderer flips front faces for mirrored objects. Once their
            // transform is baked, their triangle order must perform that flip.
            if(clone.index){const a=clone.index.array;for(let i=0;i<a.length;i+=3){const swap=a[i+1];a[i+1]=a[i+2];a[i+2]=swap;}}
            else for(const attribute of Object.values(clone.attributes))for(let i=0;i<attribute.count;i+=3)for(let c=0;c<attribute.itemSize;c++){const a=attribute.array,j=(i+1)*attribute.itemSize+c,l=(i+2)*attribute.itemSize+c,swap=a[j];a[j]=a[l];a[l]=swap;}
            const tangent=clone.attributes.tangent;if(tangent?.itemSize===4)for(let i=0;i<tangent.count;i++)tangent.setW(i,-tangent.getW(i));
          }
          clone.clearGroups();
        }
        if(!compatible)continue;
        if(!schemas.has('uv'))schemas.set('uv',2);
        for(let i=0;i<clones.length;i++){
          let clone=clones[i];
          for(const [name,size] of schemas)if(!clone.attributes[name]){
            const data=new Float32Array(clone.attributes.position.count*size);
            if(name==='color')data.fill(1);
            if(name==='tangent')for(let v=0;v<clone.attributes.position.count;v++){data[v*size]=1;if(size===4)data[v*size+3]=1;}
            clone.setAttribute(name,new THREE.BufferAttribute(data,size));
          }
          // Keep shared indexed vertices instead of expanding every triangle.
          // Existing non-indexed geometry gets identity indices: no welding,
          // coordinate rounding, seam changes or detail reduction is involved.
          if(!clone.index){
            const count=clone.attributes.position.count,indices=count>65535?new Uint32Array(count):new Uint16Array(count);
            for(let v=0;v<count;v++)indices[v]=v;
            clone.setIndex(new THREE.BufferAttribute(indices,1));
          }
        }
        const geometry=mergeGeometries(clones,false);if(!geometry)continue;
        geometry.computeBoundingBox();geometry.computeBoundingSphere();
        const first=meshes[0],combined=new THREE.Mesh(geometry,first.material);
        combined.castShadow=first.castShadow;combined.receiveShadow=first.receiveShadow;combined.layers.mask=first.layers.mask;
        combined.renderOrder=first.renderOrder;combined.frustumCulled=first.frustumCulled;combined.name=chunkSize>0?'Static map chunk':'Static map geometry';
        combined.updateMatrix();combined.matrixAutoUpdate=false;combined.userData.staticMapBatch=true;
        for(const m of meshes){
          // Keep unowned source resources reachable for WorldKit.dispose; caches
          // and authored instances may still share their original geometry.
          this.geometries.set(`optimized-original:${m.geometry.uuid}`,m.geometry);
          m.parent.remove(m);
        }
        this.root.add(combined);
      }finally{for(const clone of clones)clone.dispose();}
    }
    // The architectural world is stationary. Calculate final world matrices
    // once, then skip scene-wide forced recalculation of these exact matrices.
    // Dynamic ancestors (the harbor ship) and individual flames stay live.
    this.root.updateMatrixWorld(true);
    const freeze=(object,moving=false)=>{
      moving ||= !!object.userData.dynamic;
      if(!moving&&object!==this.root&&(staticTransforms.has(object)||object.userData.staticMapBatch||object.isInstancedMesh||object.isGroup)){
        object.matrixAutoUpdate=false;object.matrixWorldAutoUpdate=false;
      }
      for(const child of object.children)freeze(child,moving);
    };
    freeze(this.root);
  }
  dispose() {
    const geometries=new Set(),materials=new Set(),textures=new Set(this.textures);
    this.root.traverse(m=>{if(!m.isMesh)return;geometries.add(m.geometry);for(const mat of Array.isArray(m.material)?m.material:[m.material]){materials.add(mat);for(const val of Object.values(mat))if(val?.isTexture)textures.add(val);}});
    for(const g of this.geometries.values())geometries.add(g);
    for(const m of this.materials.values())materials.add(m);
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
    this.root.clear();
  }
}
