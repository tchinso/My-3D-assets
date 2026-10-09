/* Repeatable local rendering benchmark; does not change scene detail or settings. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const tag = process.argv[2] || 'current';
const base = process.env.MAP_VIEWER_URL || 'http://127.0.0.1:8000/map-viewer/';
const output = path.resolve('previews/maps/performance');
fs.mkdirSync(output, {recursive:true});
(async()=>{
  const browser = await chromium.launch({headless:true, executablePath:process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', args:['--enable-webgl','--ignore-gpu-blocklist']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Profiler.enable');
    const errors=[];
    page.on('pageerror',e=>{if(!/AdGuard Userscript|AdsBypasser|Web%20of%20Trust/.test(e.message))errors.push(e.message);});
    await page.goto(base+'?map=Academy&character=Marin');
    await page.waitForFunction(()=>window.mapExplorer && document.getElementById('loading').hidden,null,{timeout:60000});
    const results=[];
    for(const map of ['Academy','NormalTown','Port','in-Academy','Odanka']) {
      await page.evaluate(id=>window.mapExplorer.selectMap(id),map);
      await page.waitForTimeout(1000);
      await cdp.send('Profiler.start');
      const timing=await page.evaluate(()=>new Promise(resolve=>{
        const gaps=[],samples=[],start=performance.now();let previous=start;
        const sample=now=>{
          if(now-previous>0)gaps.push(now-previous);previous=now;
          const r=window.mapExplorer.renderer;
          samples.push({calls:r.info.render.calls,triangles:r.info.render.triangles});
          if(now-start<3500){requestAnimationFrame(sample);return;}
          gaps.sort((a,b)=>a-b);
          const percentile=q=>gaps[Math.min(gaps.length-1,Math.floor(gaps.length*q))];
          const mean=a=>a.reduce((sum,v)=>sum+v,0)/a.length;
          const canvas=r.domElement;
          resolve({frames:gaps.length,fps:gaps.length*1000/(now-start),medianMs:percentile(.5),p95Ms:percentile(.95),calls:mean(samples.map(s=>s.calls)),triangles:mean(samples.map(s=>s.triangles)),drawingBuffer:[canvas.width,canvas.height],geometryBuffers:r.info.memory.geometries});
        };requestAnimationFrame(sample);
      }));
      const {profile}=await cdp.send('Profiler.stop');
      const nodes=new Map(profile.nodes.map(n=>[n.id,n.callFrame]));
      const counts=new Map();
      for(const id of profile.samples || []){const n=nodes.get(id),key=`${n.functionName||'(anonymous)'} ${n.url.split('/').pop()}:${n.lineNumber+1}`;counts.set(key,(counts.get(key)||0)+1);}
      const hot=Array.from(counts,([functionName,samples])=>({functionName,samples})).sort((a,b)=>b.samples-a.samples).slice(0,14);
      const result={map,...timing,hot};results.push(result);
      console.log(`${map}: ${timing.fps.toFixed(1)} fps, p95 ${timing.p95Ms.toFixed(1)} ms, ${Math.round(timing.calls)} calls, ${Math.round(timing.triangles)} triangles`);
    }
    let gpu;
    try {const browserCdp=await browser.newBrowserCDPSession();const info=await browserCdp.send('SystemInfo.getInfo');gpu=info.gpu.devices;}catch {gpu='unavailable';}
    fs.writeFileSync(path.join(output,`${tag}.json`),JSON.stringify({tag,timestamp:new Date().toISOString(),viewport:[1440,1000],gpu,results,errors},null,2));
    if(errors.length)throw new Error(errors.join('\n'));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
