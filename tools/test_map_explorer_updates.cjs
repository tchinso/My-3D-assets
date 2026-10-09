/* Focused regression checks for renderer caching, jump input and collision fixes.
 * Existing, unchanged 14-character GLB validation is deliberately reused. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const base=process.env.MAP_VIEWER_URL || 'http://127.0.0.1:8000/map-viewer/';
const out=path.resolve('previews/maps/performance');fs.mkdirSync(out,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--ignore-gpu-blocklist']});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
    const errors=[],environmentErrors=[];
    const collect=text=>(/AdGuard Userscript|AdsBypasser|Web%20of%20Trust/.test(text)?environmentErrors:errors).push(text);
    page.on('pageerror',e=>collect(e.message));page.on('console',m=>{if(m.type()==='error')collect(m.text());});
    await page.goto(base+'?map=Academy&character=Marin');
    await page.waitForFunction(()=>window.mapExplorer&&document.getElementById('loading').hidden,null,{timeout:60000});
    const ids=await page.evaluate(()=>mapExplorer.maps.map(m=>m.id)),maps=[],shadows=[];
    for(const id of ids){
      await page.evaluate(id=>mapExplorer.selectMap(id),id);await page.waitForTimeout(160);
      const result=await page.evaluate(async()=>{
        const {blocked}=await import('/map-viewer/navigation.js');const e=mapExplorer,p=e.position;
        return {id:e.selected.map,position:p.toArray(),embedded:blocked(e.world.colliders,p.x,p.z,p.y,.22,1.5),calls:e.renderer.info.render.calls,triangles:e.renderer.info.render.triangles};
      });
      assert.ok(result.position.every(Number.isFinite),`${id}: finite spawn`);assert.equal(result.embedded,false,`${id}: spawn outside solids`);assert.ok(result.calls>0,`${id}: renders`);maps.push(result);
      if(['Academy','in-Academy','Port','BoilerRoom','SnowyTown'].includes(id)){
        const comparison=await page.evaluate(()=>mapExplorer.compareShadows());
        assert.ok(comparison.meanChannelDifference<.35 && comparison.changedPixelFraction<.01,`${id}: cached shadow preserves appearance ${JSON.stringify(comparison)}`);
        shadows.push({id,...comparison});
      }
    }
    await page.evaluate(()=>mapExplorer.selectMap('Academy'));await page.waitForTimeout(200);
    const before=await page.evaluate(()=>mapExplorer.position.y);
    await page.keyboard.down('Space');await page.waitForTimeout(290);
    const apex=await page.evaluate(()=>mapExplorer.position.y);assert.ok(apex>before+.45,'Space raises the character');
    await page.waitForTimeout(900);const held=await page.evaluate(()=>mapExplorer.position.y);assert.ok(Math.abs(held-before)<.03,'Holding jump does not repeat it');await page.keyboard.up('Space');
    await page.keyboard.down('ArrowDown');await page.waitForTimeout(550);await page.keyboard.up('ArrowDown');
    const walked=await page.evaluate(()=>mapExplorer.position.toArray());assert.ok(Math.hypot(walked[0]+4,walked[2]-6)>.4,'Movement still works');
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#capture').click()]);
    const capturePath=path.join(out,'capture.png');await download.saveAs(capturePath);assert.ok(fs.statSync(capturePath).size>20000,'Capture works without a preserved drawing buffer');
    await page.screenshot({path:path.join(out,'desktop.png')});
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(180);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile layout fits');
    assert.equal(await page.locator('#action-buttons button:visible').count(),7,'All native action buttons remain visible');
    const mobileBefore=await page.evaluate(()=>mapExplorer.position.y),jump=await page.locator('#jump-button').boundingBox();
    assert.ok(jump&&jump.x>=0&&jump.x+jump.width<=390&&jump.y+jump.height<844,'Mobile jump button is reachable');
    await page.mouse.move(jump.x+jump.width/2,jump.y+jump.height/2);await page.mouse.down();await page.waitForTimeout(280);
    const mobileApex=await page.evaluate(()=>mapExplorer.position.y);assert.ok(mobileApex>mobileBefore+.45,'Touch jump raises character');await page.mouse.up();await page.waitForTimeout(600);
    await page.screenshot({path:path.join(out,'mobile.png')});
    const collisionCoverage=await page.evaluate(async()=>{
      const {WorldKit}=await import('/map-viewer/world-kit.js');const {prepareNavigation,blocked,floorAt,createPhysicsState,stepCharacter}=await import('/map-viewer/navigation.js');
      const checks=[['Academy',[-4,2.2,-6.7],[0,-.12],[-4,35]],['Academy',[39,0,37.1],[0,-.12],[39,35]],['CapitalCity',[-11,0,8.5],[0,-.12],[-11,6]],['Deran',[-2,1.5,-12.7],[0,-.12],[-2,-16]]];
      return checks.map(([id,start,delta])=>{const k=new WorldKit(mapExplorer.maps.find(m=>m.id===id));k.descriptor.build(k);prepareNavigation(k);const p={x:start[0],y:floorAt(k.surfaces,start[0],start[2],start[1])??start[1],z:start[2]},s=createPhysicsState();for(let i=0;i<90;i++)stepCharacter(k,p,s,...delta,1/60);const clear=!blocked(k.colliders,p.x,p.z,p.y,.22,1.5);const travel=Math.hypot(p.x-start[0],p.z-start[2]);k.dispose();return {id,clear,travel,position:[p.x,p.y,p.z]};});
    });
    for(const c of collisionCoverage){assert.equal(c.clear,true,`${c.id}: no penetration`);assert.ok(c.travel<1.5,`${c.id}: building stops approach`);}
    assert.deepEqual(errors,[],'No application / shader errors');
    const result={timestamp:new Date().toISOString(),reusedUnchangedCharacterValidation:true,maps,shadows,keyboardJump:{floor:before,apex,held},mobileJump:{floor:mobileBefore,apex:mobileApex},collisionCoverage,errors,environmentErrors};
    fs.writeFileSync(path.join(out,'regression.json'),JSON.stringify(result,null,2));
    console.log(`PASS: ${maps.length} maps, ${shadows.length} cached-shadow comparisons, keyboard/touch jump, solid buildings, capture, 7 mobile actions`);
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
