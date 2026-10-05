// Khronos glTF Validator is bundled with its Apache-2.0 license for offline use.
const fs = require('fs');
const path = require('path');
const validator = require('./vendor/gltf-validator');
const root = path.resolve(__dirname, '..');
(async () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'characters/manifest.json'), 'utf8'));
  const reports = [];
  for (const entry of manifest) {
    const bytes = fs.readFileSync(path.join(root, entry.glb));
    const report = await validator.validateBytes(new Uint8Array(bytes), {uri:entry.glb, maxIssues:0, writeTimestamp:false});
    reports.push({id:entry.id,slug:entry.slug,...report});
    const issues = report.issues;
    const codes = [...new Set(issues.messages.filter(m=>m.severity<=1).map(m=>m.code))];
    console.log(`${entry.slug}: ${issues.numErrors} errors, ${issues.numWarnings} warnings ${codes.join(', ')}`);
  }
  fs.mkdirSync(path.join(root,'previews'),{recursive:true});
  fs.writeFileSync(path.join(root,'previews/gltf_validation.json'),JSON.stringify({validator:validator.version(),reports},null,2));
  process.exitCode = reports.some(r=>r.issues.numErrors>0)?1:0;
})().catch(e=>{console.error(e);process.exitCode=1;});
