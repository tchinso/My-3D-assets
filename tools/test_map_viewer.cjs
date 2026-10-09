/* Browser integration QA. Uses the bundled Playwright and installed Edge. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const runtimeModules = process.env.PLAYWRIGHT_MODULES || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = require(path.join(runtimeModules, 'playwright'));
const base = process.env.MAP_VIEWER_URL || 'http://127.0.0.1:8000/map-viewer/';
const out = path.resolve('previews/maps');
fs.mkdirSync(out, {recursive:true});
let testBrowser;
const reuse = process.argv.includes('--resume-controls');
const checkpointPath=path.join(out,'validation-checkpoint.json');
const checkpoint=reuse?JSON.parse(fs.readFileSync(checkpointPath,'utf8')):null;

(async()=>{
  const browser = await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
  testBrowser=browser;
  const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[],environmentErrors=[];
  const collectError=text=>{if(/AdGuard Userscript|AdsBypasser|Web%20of%20Trust\.user\.js/.test(text))environmentErrors.push(text);else errors.push(text);};
  page.on('pageerror',e=>collectError(e.stack||e.message));page.on('console',m=>{if(m.type()==='error')collectError(m.text());});
  const failures=[];
  await page.goto(base+'?map=Academy&character=Marin');
  await page.waitForFunction(()=>window.mapExplorer && document.getElementById('loading').hidden, null, {timeout:60000});
  assert.equal(await page.locator('.map-choice').count(),25);assert.equal(await page.locator('.character-choice').count(),14);assert.equal(await page.locator('#action-buttons button').count(),7);
  await page.locator('#choose-world').click();await page.locator('[data-filter="실내"]').click();assert.equal(await page.locator('.map-choice:visible').count(),10);
  await page.locator('[data-filter="all"]').click();await page.locator('#map-search').fill('Restaurant');assert.equal(await page.locator('.map-choice:visible').count(),1);
  await page.locator('#map-search').fill('');await page.locator('#world-picker .close-dialog').click();
  const mapResults=checkpoint?.maps || [];
  const ids=await page.evaluate(()=>window.mapExplorer.maps.map(m=>m.id));
  for(const id of reuse?[]:ids){
    await page.evaluate(async id=>{await window.mapExplorer.selectMap(id);},id);
    await page.waitForTimeout(180);
    const result=await page.evaluate(()=>{
      const e=window.mapExplorer,w=e.world,p=e.position;
      return {id:e.selected.map,meshes:w.root.children.length,colliders:w.colliders.length,surfaces:w.surfaces.length,features:w.features,interactions:w.interactions.length,spawn:[p.x,p.y,p.z],calls:e.renderer.info.render.calls,triangles:e.renderer.info.render.triangles};
    });
    if(result.meshes<10||!result.surfaces)failures.push(`${id}: missing geometry or walkable surfaces`);
    await page.locator('[data-view="overview"]').click();await page.waitForTimeout(350);
    await page.screenshot({path:path.join(out,id+'.png')});
    mapResults.push(result);console.log(`MAP ${id}: ${result.meshes} objects, ${result.colliders} colliders, ${result.surfaces} surfaces`);
    await page.locator('[data-view="follow"]').click();
  }
  const characters=checkpoint?.characters || [];
  const names=await page.evaluate(()=>window.mapExplorer.characters.map(c=>c.name));
  for(const name of reuse?[]:names){
    await page.evaluate(async name=>{await window.mapExplorer.selectCharacter(name);},name);
    const r=await page.evaluate(()=>({name:window.mapExplorer.selected.character,motions:document.querySelectorAll('#action-buttons button:not(:disabled)').length,height:window.mapExplorer.avatarHeight}));
    if(r.motions!==7)failures.push(`${name}: animations missing`);characters.push(r);console.log(`CHARACTER ${name}: ${r.motions} clips`);
    assert.ok(r.height>1.2&&r.height<1.85,`${name}: proportionate traveler height`);
  }
  fs.writeFileSync(checkpointPath,JSON.stringify({maps:mapResults,characters},null,2));
  await page.evaluate(async()=>{const e=window.mapExplorer;const character=e.selectCharacter('Momo');const map=e.selectMap('Library');await Promise.all([character,map]);});
  assert.equal(await page.evaluate(()=>window.mapExplorer.avatarSlug),'07_neon_cat','Map changes during a load must retain the selected character');
  // Find a clear corridor for actual keyboard walking / running, using scene collision data.
  await page.evaluate(async()=>{await window.mapExplorer.selectMap('Academy');await window.mapExplorer.selectCharacter('Marin');});
  const safe=await page.evaluate(async()=>{
    const {floorAt,blocked}=await import('/map-viewer/navigation.js');const e=window.mapExplorer,w=e.world;
    const yaw=Math.PI*.24,dx=-Math.sin(yaw),dz=-Math.cos(yaw);
    for(let x=-w.width/2+4;x<w.width/2-4;x+=2)for(let z=-w.depth/2+4;z<w.depth/2-4;z+=2){
      let ok=true;const y=floorAt(w.surfaces,x,z);
      if(y===null)continue;
      for(let i=0;i<=8;i+=.25){const xx=x+dx*i,zz=z+dz*i,fy=floorAt(w.surfaces,xx,zz,y);if(fy===null||Math.abs(fy-y)>.1||blocked(w.colliders,xx,zz,y,.3)){ok=false;break;}}
      if(ok)return {x,z,y};
    }return null;
  });
  assert.ok(safe,'A clear walking corridor must exist');
  // Reset through the actual map spawn and leave the same corridor for both speeds.
  await page.evaluate(safe=>{window.mapExplorer.maps.find(m=>m.id==='Academy').spawn=[safe.x,safe.z];document.getElementById('reset-position').click();},safe);
  const start=await page.evaluate(()=>window.mapExplorer.position.toArray());
  await page.keyboard.down('ArrowUp');await page.waitForTimeout(1000);assert.equal(await page.evaluate(()=>window.mapExplorer.motion),'Walk');await page.keyboard.up('ArrowUp');
  const walked=await page.evaluate(()=>window.mapExplorer.position.toArray());
  assert.ok(Math.hypot(walked[0]-start[0],walked[2]-start[2])>.6,'Keyboard must move character');
  await page.locator('#reset-position').click();await page.keyboard.down('Shift');await page.keyboard.down('ArrowUp');await page.waitForTimeout(1000);assert.equal(await page.evaluate(()=>window.mapExplorer.motion),'Run');await page.keyboard.up('ArrowUp');await page.keyboard.up('Shift');
  const ran=await page.evaluate(()=>window.mapExplorer.position.toArray());
  assert.ok(Math.hypot(ran[0]-start[0],ran[2]-start[2])>Math.hypot(walked[0]-start[0],walked[2]-start[2])*1.5,'Running must be faster');
  for(const motion of ['Attack','Defend','Victory','Lose','Idle']){await page.locator(`[data-motion="${motion}"]`).click();assert.equal(await page.evaluate(()=>window.mapExplorer.motion),motion);}
  await page.locator('#reference-button').click();await page.waitForFunction(()=>{const img=document.getElementById('reference-image');return img.complete&&img.naturalWidth>0;},null,{timeout:30000});await page.locator('#reference-dialog .close-dialog').click();
  await page.locator('[data-view="first"]').click();await page.waitForTimeout(350);await page.screenshot({path:path.join(out,'first-person.png')});
  await page.locator('[data-view="follow"]').click();await page.waitForTimeout(300);await page.screenshot({path:path.join(out,'desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
  const joy=await page.locator('#joystick').boundingBox();const mobileStart=await page.evaluate(()=>window.mapExplorer.position.toArray());
  await page.mouse.move(joy.x+joy.width/2,joy.y+joy.height/2);await page.mouse.down();await page.mouse.move(joy.x+joy.width/2,joy.y+5);await page.waitForTimeout(700);await page.mouse.up();
  const mobileEnd=await page.evaluate(()=>window.mapExplorer.position.toArray());assert.ok(Math.hypot(mobileEnd[0]-mobileStart[0],mobileEnd[2]-mobileStart[2])>.25,'Joystick must move character');
  await page.locator('#run-button').click();assert.equal(await page.locator('#run-button').getAttribute('aria-pressed'),'true');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false,'Mobile UI must fit viewport');
  await page.screenshot({path:path.join(out,'mobile.png')});
  await page.reload();await page.waitForFunction(()=>window.mapExplorer && document.getElementById('loading').hidden, null, {timeout:30000});assert.deepEqual(await page.evaluate(()=>window.mapExplorer.selected),{map:'Academy',character:'Marin'});
  const report={timestamp:new Date().toISOString(),reusedMapCharacterChecks:reuse,maps:mapResults,characters,walkingDistance:Math.hypot(walked[0]-start[0],walked[2]-start[2]),runningDistance:Math.hypot(ran[0]-start[0],ran[2]-start[2]),mobileJoystick:true,errors,environmentErrors,failures};
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(report,null,2));
  await browser.close();assert.equal(errors.length,0,errors.join('\n'));assert.equal(failures.length,0,failures.join('\n'));console.log('PASS: 25 maps, 14 characters, keyboard, run, actions, joystick, selectors and reload');
})().catch(async e=>{console.error(e);if(testBrowser)await testBrowser.close();process.exitCode=1;});
