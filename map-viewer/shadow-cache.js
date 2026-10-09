import * as THREE from 'three';

// Keep the original 2048px PCF shadow detail. Only moving casters are drawn each
// frame; the two depth maps are combined per PCF tap, exactly like one depth map.
export class ShadowCache {
  constructor(scene, sun) {
    this.scene = scene;
    this.sun = sun;
    this.cachedLight = sun.clone();
    this.cachedLight.name = 'cached-sun';
    this.cachedLight.intensity = 0;
    this.cachedLight.shadow.autoUpdate = false;
    scene.add(this.cachedLight);
    this.staticCasters = [];
    this.dynamicBounds = new THREE.Vector4(0,0,1,1);
    this.projected = new THREE.Vector3();
    this.preparedMaterials = new WeakSet();
    this.dirty = true;
    this.installShader();
  }
  installShader() {
    const chunks = THREE.ShaderChunk;
    const source = chunks.shadowmap_pars_fragment;
    const begin = source.indexOf('\tfloat getShadow(');
    const end = source.indexOf('\tvec2 cubeToUV(', begin);
    const combined = source.slice(begin, end)
      .replace('float getShadow( sampler2D shadowMap,', 'float getCachedShadow( sampler2D shadowMap, sampler2D cachedShadowMap,')
      .replace('float shadow = 1.0;', `vec2 uvBounds = shadowCoord.xy / shadowCoord.w;
      if (any(lessThan(uvBounds, cachedDynamicBounds.xy)) || any(greaterThan(uvBounds, cachedDynamicBounds.zw))) {
        return getShadow(cachedShadowMap, shadowMapSize, shadowIntensity, shadowBias, shadowRadius, shadowCoord);
      }
      float shadow = 1.0;`)
      .replaceAll('texture2DCompare( shadowMap,', 'cachedDepthCompare( shadowMap, cachedShadowMap,');
    chunks.shadowmap_pars_fragment += `\n#ifdef USE_SHADOWMAP\nuniform vec4 cachedDynamicBounds;\nfloat cachedDepthCompare(sampler2D dynamicMap, sampler2D staticMap, vec2 uv, float compare) {\nreturn min(texture2DCompare(dynamicMap, uv, compare), texture2DCompare(staticMap, uv, compare));\n}\n${combined}\n#endif\n`;
    const original = 'directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;';
    const replacement = `#if UNROLLED_LOOP_INDEX == 0 && NUM_DIR_LIGHT_SHADOWS > 1
      directLight.color *= ( directLight.visible && receiveShadow ) ? getCachedShadow( directionalShadowMap[ i ], directionalShadowMap[ 1 ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
      #else
      ${original}
      #endif`;
    if(!chunks.lights_fragment_begin.includes(original))throw new Error('Unsupported directional shadow shader');
    chunks.lights_fragment_begin = chunks.lights_fragment_begin.replace(original, replacement);
    // The zero-intensity cached light supplies depth only. Exclude its lighting
    // branch at compile time so it does not perform a redundant PCF/BRDF pass.
    const lighting=chunks.lights_fragment_begin;
    const loop=lighting.indexOf('for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ )');
    const body=lighting.indexOf('{',loop)+1;
    const close=lighting.indexOf('\n\t}\n\t#pragma unroll_loop_end',body);
    chunks.lights_fragment_begin=lighting.slice(0,body)+'\n#if !(NUM_DIR_LIGHT_SHADOWS > 1 && UNROLLED_LOOP_INDEX == 1)\n'+lighting.slice(body,close)+'\n#endif\n'+lighting.slice(close);
  }
  setWorld(world) {
    this.prepareMaterials(world.root);
    this.dynamicBounds.set(0,0,1,1);
    this.staticCasters = [];
    const collect = (object, dynamic = false) => {
      dynamic ||= !!object.userData.dynamic;
      if(object.isMesh && object.castShadow && !dynamic)this.staticCasters.push(object);
      for(const child of object.children)collect(child, dynamic);
    };
    collect(world.root);
    this.cachedLight.position.copy(this.sun.position);
    this.cachedLight.target = this.sun.target;
    this.cachedLight.shadow.camera.copy(this.sun.shadow.camera);
    this.cachedLight.shadow.bias = this.sun.shadow.bias;
    this.cachedLight.shadow.normalBias = this.sun.shadow.normalBias;
    this.cachedLight.shadow.mapSize.copy(this.sun.shadow.mapSize);
    this.dirty = true;
  }
  prepareMaterials(root) {
    root.traverse(object=>{
      if(!object.isMesh)return;
      for(const material of Array.isArray(object.material)?object.material:[object.material]){
        if(this.preparedMaterials.has(material))continue;
        this.preparedMaterials.add(material);
        const previous=material.onBeforeCompile;
        material.onBeforeCompile=(shader,renderer)=>{previous.call(material,shader,renderer);shader.uniforms.cachedDynamicBounds={value:this.dynamicBounds};};
        material.needsUpdate=true;
      }
    });
  }
  updateBounds(avatar, world, motion) {
    // Animated scenery uses the full depth map. For a lone traveler, a generous
    // motion/weapon envelope avoids sampling an empty dynamic map elsewhere.
    if(world.animated.length || !['Idle','Walk','Run'].includes(motion)){this.dynamicBounds.set(0,0,1,1);return;}
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for(const x of [-4,4])for(const y of [-2,6])for(const z of [-4,4]){
      const p=this.projected.set(avatar.position.x+x,avatar.position.y+y,avatar.position.z+z).applyMatrix4(this.sun.shadow.matrix);
      minX=Math.min(minX,p.x);minY=Math.min(minY,p.y);maxX=Math.max(maxX,p.x);maxY=Math.max(maxY,p.y);
    }
    const margin=3/this.sun.shadow.mapSize.x;
    this.dynamicBounds.set(minX-margin,minY-margin,maxX+margin,maxY+margin);
  }
  bake(renderer, camera) {
    if(!this.dirty)return;
    const moving=[];
    const statics=new Set(this.staticCasters);
    this.scene.traverse(object=>{
      if(object.isMesh && object.castShadow && !statics.has(object)){moving.push(object);object.castShadow=false;}
    });
    this.sun.shadow.autoUpdate=false;
    this.sun.shadow.needsUpdate=true;
    this.cachedLight.shadow.needsUpdate=true;
    // Both maps start with the complete static scene. The sun map is replaced by
    // moving-only depth on the following frame, without a missing-shadow flash.
    renderer.render(this.scene,camera);
    for(const object of moving)object.castShadow=true;
    for(const object of this.staticCasters)object.castShadow=false;
    this.sun.shadow.autoUpdate=true;
    this.sun.shadow.needsUpdate=true;
    this.dirty=false;
  }
  renderReference(renderer, camera) {
    // Used by visual regression QA to compare cached depth with the original
    // complete shadow pass at exactly the same camera and animation pose.
    this.cachedLight.castShadow=false;
    for(const object of this.staticCasters)object.castShadow=true;
    renderer.render(this.scene,camera);
    for(const object of this.staticCasters)object.castShadow=false;
    this.cachedLight.castShadow=true;
  }
  compareReference(renderer, camera) {
    const gl=renderer.getContext(),size=renderer.getDrawingBufferSize(new THREE.Vector2());
    const cached=new Uint8Array(size.x*size.y*4),reference=new Uint8Array(cached.length);
    renderer.render(this.scene,camera);
    gl.readPixels(0,0,size.x,size.y,gl.RGBA,gl.UNSIGNED_BYTE,cached);
    this.renderReference(renderer,camera);
    gl.readPixels(0,0,size.x,size.y,gl.RGBA,gl.UNSIGNED_BYTE,reference);
    let sum=0,changed=0,max=0;
    for(let i=0;i<cached.length;i+=4){let pixelMax=0;for(let c=0;c<3;c++){const d=Math.abs(cached[i+c]-reference[i+c]);sum+=d;pixelMax=Math.max(pixelMax,d);}if(pixelMax>2)changed++;max=Math.max(max,pixelMax);}
    return {meanChannelDifference:sum/(size.x*size.y*3),changedPixelFraction:changed/(size.x*size.y),maximumDifference:max};
  }
}
