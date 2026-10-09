// Outdoor and underground scenes built from the supplied reference artwork.
// Coordinates are in metres; paths, terraces, and stairs provide walkable heights.

const TAU = Math.PI * 2;
const C = {
  bark: '#65432a', barkLight: '#98703c', wood: '#9b6938', plank: '#ba8b4b',
  leaf: '#56852d', leafLight: '#88ae48', moss: '#729541', grass: '#91b93e',
  stone: '#ada78a', stoneDark: '#776f5d', sand: '#dcc781', gold: '#e4b643',
};

function rng(seed = 31) {
  let s = seed >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
}

function mesh(k, geometry, color, { x = 0, y = 0, z = 0, rot = [0, 0, 0], material } = {}) {
  const m = new k.THREE.Mesh(geometry, material || k.material(color, { roughness: .91 }));
  m.position.set(x, y, z);
  m.rotation.set(...rot);
  m.castShadow = true;
  m.receiveShadow = true;
  k.root.add(m);
  return m;
}

function subtractRect(source, cut) {
  const ax = source.x - source.w / 2, bx = source.x + source.w / 2;
  const az = source.z - source.d / 2, bz = source.z + source.d / 2;
  const lx = Math.max(ax, cut.x - cut.w / 2), rx = Math.min(bx, cut.x + cut.w / 2);
  const lz = Math.max(az, cut.z - cut.d / 2), rz = Math.min(bz, cut.z + cut.d / 2);
  if (lx >= rx || lz >= rz) return [source];
  const parts = [];
  const add = (x1, x2, z1, z2) => { if (x2 - x1 > .015 && z2 - z1 > .015) parts.push({ x: (x1 + x2) / 2, z: (z1 + z2) / 2, w: x2 - x1, d: z2 - z1 }); };
  add(ax, lx, az, bz); add(rx, bx, az, bz); add(lx, rx, az, lz); add(lx, rx, rz, bz);
  return parts;
}

function rebuildTerrace(k, t) {
  for (const m of t.meshes) k.root.remove(m);
  const old = new Set(t.surfaces); k.surfaces = k.surfaces.filter(s => !old.has(s));
  t.meshes = []; t.surfaces = [];
  let parts = [{ x: t.x, z: t.z, w: t.w, d: t.d }];
  for (const cut of t.cuts) parts = parts.flatMap(part => subtractRect(part, cut));
  for (const p of parts) {
    t.meshes.push(k.box(p.x, (t.top + t.base) / 2, p.z, p.w, t.top - t.base, p.d, t.bodyColor));
    if (t.color !== t.bodyColor) t.meshes.push(k.box(p.x, t.top - .035, p.z, p.w, .07, p.d, t.color));
    k.surface(p.x, p.z, p.w, p.d, t.top); t.surfaces.push(k.surfaces[k.surfaces.length - 1]);
  }
  // Remove edge outcrops from the physical staircase trench as well.
  for (const detail of t.edgeDetails) {
    if (t.cuts.some(cut => Math.abs(detail.x - cut.x) < cut.w / 2 + .35 && Math.abs(detail.z - cut.z) < cut.d / 2 + .35)) k.root.remove(detail.mesh);
  }
}

function terrace(k, x, top, z, w, d, color, base, bodyColor) {
  const t = { x, z, w, d, top, base, color, bodyColor, cuts: [], meshes: [], surfaces: [], edgeDetails: [] };
  (k.__natureTerraces ||= []).push(t); rebuildTerrace(k, t); return t;
}

function deck(k, x, top, z, w, d, color) { return terrace(k, x, top, z, w, d, color, top - .2, color); }

function beam(k, a, b, radius, color) { k.line([a, b], color, radius); }

function path(k, points, width, color = '#d6c184', y = .025) {
  for (let i = 1; i < points.length; i++) {
    const [x1, z1] = points[i - 1], [x2, z2] = points[i];
    k.box((x1 + x2) / 2, y, (z1 + z2) / 2, width, .04, Math.hypot(x2 - x1, z2 - z1) + width * .35, color,
      { rot: Math.atan2(x2 - x1, z2 - z1), solid: false });
    k.cylinder(x2, y, z2, width * .52, .04, color, { segments: 16 });
  }
}

function stones(k, x, z, width, depth, n = 25, y = .055, seed = 3, color = C.stone) {
  const r = rng(seed);
  for (let i = 0; i < n; i++) {
    const sx = x + (r() - .5) * width, sz = z + (r() - .5) * depth;
    const size = .18 + r() * .25;
    k.sphere(sx, y, sz, .25, color, [size / .25 * 1.1, size / .25 * .16, size / .25 * (.7 + r() * .4)]);
  }
}

function rock(k, x, y, z, size = 1, color = C.stoneDark, collide = false) {
  const m = mesh(k, k.geometry('nature:rock', () => new k.THREE.IcosahedronGeometry(1, 0)), color, { x, y: y + size * .42, z, rot: [.1, x * .37, .17] });
  m.scale.set(size, size * .78, size * .83);
  if (collide) k.collide(x, z, size * 1.3, size * 1.1, { y, h: size * 1.25 });
}

function flowers(k, x, z, width, depth, count = 30, y = 0, seed = 52) {
  const r = rng(seed);
  for (let i = 0; i < count; i++) {
    const px = x + (r() - .5) * width, pz = z + (r() - .5) * depth, h = .13 + r() * .24;
    const stem = k.cylinder(px, y + h / 2, pz, .017, .25, '#557933', { segments: 5 }); stem.scale.y = h / .25;
    k.sphere(px, y + h, pz, .075, i % 5 === 0 ? '#fff0ca' : '#ead960', [1, .65, 1]);
  }
}

function shrub(k, x, y, z, radius = .7, color = C.leaf) {
  for (let i = 0; i < 4; i++) {
    const a = i * TAU / 4;
    k.sphere(x + Math.cos(a) * radius * .35, y + radius * .45, z + Math.sin(a) * radius * .35,
      radius * .65, i % 2 ? color : C.leafLight, [1, .76, 1]);
  }
}

function roots(k, x, y, z, radius, reach, count = 7, height = .7, color = C.bark) {
  for (let i = 0; i < count; i++) {
    const a = i * TAU / count + .19;
    const points = [
      [x + Math.cos(a) * radius * .66, y + height, z + Math.sin(a) * radius * .66],
      [x + Math.cos(a) * radius * 1.25, y + height * .43, z + Math.sin(a) * radius * 1.25],
      [x + Math.cos(a + .12) * reach, y + .05, z + Math.sin(a + .12) * reach],
    ];
    k.line(points, color, radius * .22);
    k.line(points.map(([rx, ry, rz]) => [rx + .05, ry + .08, rz]), C.barkLight, radius * .038);
  }
}

function tree(k, x, y, z, height = 6, radius = .55, canopy = 2.6, { bare = false, collide = true, seed = 1 } = {}) {
  const r = rng(seed);
  k.cylinder(x, y + height * .37, z, radius, height * .74, C.bark, { top: radius * .65, segments: 12 });
  roots(k, x, y, z, radius, radius * 3.3, 6, radius * 1.8);
  for (let i = 0; i < 8; i++) {
    const a = i * TAU / 8;
    k.line([[x + Math.cos(a) * radius, y + .45, z + Math.sin(a) * radius],
      [x + Math.cos(a + .2) * radius * .65, y + height * .65, z + Math.sin(a + .2) * radius * .65]],
    i % 2 ? C.barkLight : '#4b3424', radius * .045);
  }
  for (let i = 0; i < 5; i++) {
    const a = i * TAU / 5 + r(), bx = x + Math.cos(a) * canopy * .7, bz = z + Math.sin(a) * canopy * .7;
    beam(k, [x, y + height * .58, z], [bx, y + height * .84, bz], radius * .24, C.bark);
    if (bare) {
      beam(k, [bx, y + height * .84, bz], [bx + Math.cos(a) * canopy * .4, y + height, bz + Math.sin(a) * canopy * .4], radius * .095, C.bark);
      beam(k, [bx, y + height * .84, bz], [bx + Math.cos(a + .9) * canopy * .3, y + height * 1.01, bz + Math.sin(a + .9) * canopy * .3], radius * .07, C.bark);
    } else {
      k.sphere(bx, y + height * .81, bz, canopy * .68, i % 2 ? C.leaf : C.leafLight, [1, .6, 1]);
      k.sphere(bx, y + height * .96, bz, canopy * .51, C.leaf, [1, .64, 1]);
      for (let j = 0; j < 16; j++) {
        const a2 = j * 2.399, band = (j % 4 - 1.5) / 2.5, rr = Math.sqrt(1 - band * band) * canopy * .7;
        k.sphere(bx + Math.cos(a2) * rr, y + height * .83 + band * canopy * .45, bz + Math.sin(a2) * rr,
          .3, j % 3 ? C.leafLight : '#3d7333', [canopy * .19, canopy * .13, canopy * .2]);
      }
    }
  }
  if (collide) k.collide(x, z, radius * 1.75, radius * 1.75, { y, h: height });
}

function fence(k, x, y, z, length, { rot = 0, height = .82, rope = false, color = C.bark, gap = 0 } = {}) {
  const parts = Math.max(2, Math.ceil(length / 1.3)), dx = Math.cos(rot), dz = -Math.sin(rot);
  for (let i = 0; i <= parts; i++) {
    const t = (i / parts - .5) * length;
    if (gap && Math.abs(t) < gap / 2) continue;
    k.cylinder(x + dx * t, y + height / 2, z + dz * t, .06, height, color, { segments: 7 });
    k.sphere(x + dx * t, y + height, z + dz * t, .075, C.plank);
  }
  for (let i = 0; i < parts; i++) {
    const a = (i / parts - .5) * length, b = ((i + 1) / parts - .5) * length;
    if (gap && (Math.abs(a) < gap / 2 || Math.abs(b) < gap / 2)) continue;
    if (rope) {
      k.line([[x + dx * a, y + height * .9, z + dz * a], [x + dx * (a + b) / 2, y + height * .72, z + dz * (a + b) / 2], [x + dx * b, y + height * .9, z + dz * b]], '#baa879', .028);
    } else {
      for (const h of [.35, .7]) beam(k, [x + dx * a, y + h, z + dz * a], [x + dx * b, y + h, z + dz * b], .037, color);
    }
  }
  if (!rope && !gap) k.collide(x, z, length, .14, { y, h: height, rot });
}

function barrel(k, x, y, z, scale = 1, tipped = false) {
  const m = k.cylinder(x, y + .48 * scale, z, .36 * scale, .92 * scale, '#947545', { top: .31 * scale, segments: 12 });
  if (tipped && m?.rotation) m.rotation.z = Math.PI / 2;
  for (const h of [.12, .79]) k.torus(x, y + h * scale, z, .335 * scale, .025 * scale, '#44474a');
  k.cylinder(x, y + .955 * scale, z, .29 * scale, .03, '#b69562', { segments: 12 });
  for (let i = 0; i < 10; i++) {
    const a = i * TAU / 10;
    beam(k, [x + Math.sin(a) * .345 * scale, y + .17 * scale, z + Math.cos(a) * .345 * scale],
      [x + Math.sin(a) * .32 * scale, y + .84 * scale, z + Math.cos(a) * .32 * scale], .008 * scale, '#604629');
  }
  k.collide(x, z, .65 * scale, .65 * scale, { y, h: scale });
}

function roof(k, x, y, z, width, depth, color, { snow = false, thatch = false } = {}) {
  const rise = width * .32, shape = new k.THREE.Shape();
  shape.moveTo(-width / 2, 0); shape.lineTo(width / 2, 0); shape.lineTo(0, rise); shape.closePath();
  const geo = new k.THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false });
  mesh(k, geo, color, { x, y, z: z - depth / 2 });
  const r = rng(Math.round(width * depth * 9));
  if (thatch) {
    for (let i = 0; i < 28; i++) {
      const pz = z - depth / 2 + i * depth / 27;
      beam(k, [x - width * .51, y + .06, pz], [x, y + rise + .02, pz], .022, i % 2 ? '#654326' : '#c39c58');
      beam(k, [x, y + rise + .02, pz], [x + width * .51, y + .06, pz], .022, i % 2 ? '#c9a565' : '#876237');
    }
  }
  if (snow) {
    for (const side of [-1, 1]) {
      const m = k.box(x + side * width * .245, y + rise * .53 + .1, z, Math.hypot(width / 2, rise) + .23, .26, depth + .3, '#f6f6ed');
      if (m?.rotation) m.rotation.z = side === -1 ? Math.atan2(rise, width / 2) : -Math.atan2(rise, width / 2);
      for (let i = 0; i < 15; i++) {
        const pz = z - depth / 2 + i * depth / 14, h = .17 + r() * .32;
        mesh(k, new k.THREE.ConeGeometry(.044, h, 5), '#cddfe0', { x: x + side * width * .5, y: y - h / 2, z: pz, rot: [Math.PI, 0, 0] });
      }
    }
  }
}

function door(k, x, y, z, width = 1.05, height = 2, color = '#4e3525', rot = 0) {
  k.box(x, y + height / 2, z, width, height, .075, color, { rot });
  const c = Math.cos(rot), s = Math.sin(rot);
  for (let i = 0; i <= 4; i++) {
    const q = (i / 4 - .5) * width;
    k.box(x + c * q, y + height / 2, z - s * q + .045, .015, height * .97, .015, '#2f271e', { rot });
  }
  k.box(x, y + height + .08, z, width + .24, .16, .2, '#b3935d', { rot });
  for (const side of [-1, 1]) k.box(x + c * side * (width / 2 + .08), y + height / 2, z - s * side * (width / 2 + .08), .14, height + .12, .17, '#b3935d', { rot });
  k.sphere(x + c * width * .29, y + .91, z - s * width * .29 + .065, .055, '#c7ac62');
}

function cabin(k, x, y, z, w = 6, d = 4.5, { snow = false, color = '#9b7950', thatch = true, chimney = true } = {}) {
  const h = 2.4;
  k.box(x, y + h / 2, z, w, h, d, color, { solid: true });
  for (let j = 0; j < 7; j++) k.box(x, y + .15 + j * .34, z + d / 2 + .026, w, .025, .035, '#513c2e');
  for (const side of [-1, 1]) {
    k.box(x + side * w * .47, y + h / 2, z + d / 2 + .05, .17, h, .17, '#4e3926');
    const wx = x + side * w * .31;
    k.box(wx, y + 1.48, z + d / 2 + .07, 1.05, 1.04, .08, '#493e2c');
    k.box(wx, y + 1.48, z + d / 2 + .125, .82, .84, .02, '#b9c7a0');
    k.box(wx, y + 1.48, z + d / 2 + .15, .055, .85, .03, '#674a2c');
    k.box(wx, y + 1.48, z + d / 2 + .15, .85, .055, .03, '#674a2c');
    for (const shutterSide of [-1, 1]) k.box(wx + shutterSide * .69, y + 1.48, z + d / 2 + .15, .27, 1.03, .08, snow ? '#8b4d30' : '#624b32');
  }
  door(k, x, y, z + d / 2 + .12, 1.05, 1.91, snow ? '#783d27' : '#503720');
  roof(k, x, y + h, z, w + .65, d + .7, snow ? '#8f6947' : '#94703d', { snow, thatch });
  deck(k, x, y + .17, z + d / 2 + .48, 1.5, .9, snow ? '#aaa79c' : C.plank);
  k.interactions.push({ name: '집 입구', position: [x, y + 1, z + d / 2 + .9], kind: 'inspect', text: snow ? '두꺼운 눈과 고드름이 덮인 나무집입니다.' : '목재의 결, 창문의 덧문과 작은 현관 계단이 보입니다.' });
  if (chimney) {
    const cx = x - w * .38, cz = z - d * .15;
    k.box(cx, y + 2.8, cz, .65, 3.2, .75, '#a34b32');
    for (let j = 0; j < 9; j++) {
      k.box(cx, y + 1.28 + j * .33, cz + .39, .69, .025, .02, '#703321');
      k.box(cx + (j % 2 ? -.17 : .16), y + 1.45 + j * .33, cz + .39, .025, .3, .02, '#713324');
    }
    k.box(cx, y + 4.44, cz, .85, .16, .94, snow ? '#f4f4eb' : '#b97a48');
    k.box(cx, y + 4.53, cz, .38, .03, .47, '#272c2c');
  }
}

function cliff(k, x, z, w, d, top, color = '#aca375', base = -1.3, seed = 11) {
  const r = rng(seed);
  const t = terrace(k, x, top, z, w, d, color, base, '#767155');
  for (const side of [-1, 1]) {
    const segments = Math.ceil(w / .8);
    for (let i = 0; i < segments; i++) {
      const px = x - w / 2 + (i + .5) * w / segments, sz = z + side * (d / 2 - .1);
      const rr = .26 + r() * .35;
      const column = k.cylinder(px, (top + base) / 2, sz, .4, 1, i % 3 ? '#8c805a' : '#b6b18a', { top: .308, segments: 5 }); column.scale.set(rr / .4, top - base + .1, rr / .4);
      t.edgeDetails.push({ x: px, z: sz, mesh: column });
      const before = k.root.children.length; rock(k, px, top - .06, sz, .2 + r() * .26, '#bdbd99');
      t.edgeDetails.push({ x: px, z: sz, mesh: k.root.children[before] });
    }
  }
  for (const side of [-1, 1]) {
    for (let i = 0; i < Math.ceil(d / .9); i++) {
      const pz = z - d / 2 + (i + .5) * d / Math.ceil(d / .9), rr = .28 + r() * .23;
      const column = k.cylinder(x + side * (w / 2 - .1), (top + base) / 2, pz, .4, 1, '#918768', { top: .32, segments: 5 }); column.scale.set(rr / .4, top - base, rr / .4);
      t.edgeDetails.push({ x: x + side * (w / 2 - .1), z: pz, mesh: column });
    }
  }
}

function nest(k, x, y, z, radius = .9, eggs = 3) {
  k.cylinder(x, y + .12, z, radius, .25, '#746b2f', { top: radius * .92, segments: 16 });
  k.torus(x, y + .27, z, radius * .75, radius * .25, '#8a9136');
  for (let i = 0; i < 12; i++) {
    const a = i * TAU / 12;
    k.line([[x + Math.cos(a) * radius, y + .24, z + Math.sin(a) * radius], [x + Math.cos(a + .55) * radius * .8, y + .39, z + Math.sin(a + .55) * radius * .8]], '#b0aa42', .02);
  }
  for (let i = 0; i < eggs; i++) k.sphere(x + (i - (eggs - 1) / 2) * .33, y + .41, z + (i % 2 ? .12 : -.09), .23, '#ebe6c8', [.78, 1.13, .8]);
}

function addWater(k, x, y, z, radius, scale = [1, 1, 1]) {
  const material = new k.THREE.MeshStandardMaterial({ color: '#52bcbc', roughness: .23, metalness: .17, transparent: true, opacity: .8 });
  const m = mesh(k, new k.THREE.CylinderGeometry(radius, radius, .05, 32), '#52bcbc', { x, y, z, material });
  m.scale.set(...scale);
  for (let i = 0; i < 4; i++) {
    const t = k.torus(x, y + .05, z, radius * (.23 + i * .17), .012, '#b5e6d8');
    if (t?.scale) t.scale.set(scale[0], scale[2], 1);
  }
}

function stairsFrom(k, x, z, w, count, rise, run, color, y = 0, heading = 0, { floating = false } = {}) {
  // Each step is centred along the route; callers connect its top to a terrace.
  const sin = Math.sin(heading), cos = Math.cos(heading);
  // Cut each destination terrace around the staircase. The route remains open
  // from its first low tread to the full-height landing, with no cliff overlap.
  if (Math.abs(sin) < .001) {
    const target = y + count * rise, cut = { x, z: z - count * run / 2, w: w + .16, d: count * run + .025 };
    for (const t of k.__natureTerraces || []) {
      if (Math.abs(t.top - target) > .02 || t.top <= y + .02) continue;
      if (Math.abs(t.x - cut.x) < (t.w + cut.w) / 2 && Math.abs(t.z - cut.z) < (t.d + cut.d) / 2) { t.cuts.push(cut); rebuildTerrace(k, t); }
    }
  }
  for (let i = 0; i < count; i++) {
    const stepY = y + (i + 1) * rise, t = (i + .5) * run;
    const px = x - sin * t, pz = z - cos * t;
    const bodyHeight = floating ? rise : (i + 1) * rise;
    k.box(px, stepY - bodyHeight / 2, pz, w, bodyHeight, run + .04, color, { rot: heading });
    k.surface(px, pz, w, run + .045, stepY, { rot: heading });
    k.box(px, stepY + .012, pz + cos * run * .35, w, .022, .035, '#e2d5a2', { rot: heading });
  }
}

function hangingVines(k, x, y, z, width = 2.5, count = 7) {
  for (let i = 0; i < count; i++) {
    const px = x - width / 2 + i * width / (count - 1), h = .8 + Math.sin(i * 1.8) * .5;
    k.line([[px, y, z], [px + .15, y - h * .5, z + .07], [px + .04, y - h, z]], '#607f35', .022);
    for (let j = 0; j < 3; j++) k.sphere(px + (j % 2 ? -.08 : .1), y - h * (j + 1) / 4, z, .12, '#6c9a43', [1, .6, .65]);
  }
}

function bird(k, x, y, z, scale = 1, color = '#d9b652') {
  k.sphere(x, y + .65 * scale, z, .39 * scale, color, [1, 1.25, .9]);
  k.sphere(x, y + 1.14 * scale, z, .28 * scale, color);
  for (const side of [-1, 1]) {
    k.sphere(x + side * .13 * scale, y + 1.21 * scale, z + .21 * scale, .075 * scale, '#403f31', [1, 1, .4]);
    for (let j = 0; j < 6; j++) {
      const f = k.sphere(x + side * (.45 + j * .17) * scale, y + (.9 - j * .042) * scale, z, .27 * scale, j % 2 ? color : '#e4cb73', [1.4, .25, .48]);
      if (f?.rotation) f.rotation.z = side * -.17;
    }
    k.cylinder(x + side * .15 * scale, y + .18 * scale, z, .07 * scale, .35 * scale, color, { segments: 7 });
  }
  const beak = mesh(k, new k.THREE.ConeGeometry(.12 * scale, .25 * scale, 4), '#b99735', { x, y: y + 1.09 * scale, z: z + .32 * scale, rot: [Math.PI / 2, 0, 0] });
  return beak;
}

function masonry(k, x, y, z, width, height, color = '#bcb897', rot = 0, thickness = .38) {
  k.box(x, y + height / 2, z, width, height, thickness, '#716f61', { rot, solid: true });
  const rows = Math.ceil(height / .42), cols = Math.ceil(width / .67);
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const q = (i + .5) * width / cols - width / 2 + (j % 2 ? .12 : -.12);
    const px = x + Math.cos(rot) * q, pz = z - Math.sin(rot) * q;
    k.box(px, y + (j + .5) * height / rows, pz, width / cols - .033, height / rows - .035, thickness + .045,
      (i + j) % 4 === 0 ? '#ccc9a8' : color, { rot });
  }
}

function totem(k, x, y, z, height = 3.1, radius = .42, color = '#9d8054', patterned = true) {
  k.cylinder(x, y + height / 2, z, radius, height, color, { top: radius * .95, segments: 12, solid: true });
  const cy = y + height * .67;
  for (const side of [-1, 1]) {
    k.sphere(x + side * radius * .46, cy + height * .095, z + radius * .87, radius * .21, '#403c2b', [1.4, .65, .5]);
    k.sphere(x + side * radius * .53, cy - height * .13, z + radius * .85, radius * .25, '#a64931', [1.35, .43, .4]);
  }
  k.sphere(x, cy, z + radius, radius * .27, '#b99a64', [.6, 1.75, .8]);
  k.sphere(x, cy - height * .14, z + radius * .88, radius * .36, '#50402b', [1.1, .37, .5]);
  k.box(x, cy - height * .14, z + radius * 1.06, radius * .39, .08, .04, '#dbcaa5');
  if (patterned) {
    for (const f of [.08, .21, .86, .96]) k.torus(x, y + height * f, z, radius, .035, f > .8 ? '#bb5e3b' : '#497d79');
    for (let i = 0; i < 12; i++) {
      const a = i * TAU / 12, b = (i + 1) * TAU / 12;
      k.line([[x + Math.sin(a) * radius * 1.015, y + height * .89, z + Math.cos(a) * radius * 1.015],
        [x + Math.sin((a + b) / 2) * radius * 1.015, y + height * .95, z + Math.cos((a + b) / 2) * radius * 1.015],
        [x + Math.sin(b) * radius * 1.015, y + height * .89, z + Math.cos(b) * radius * 1.015]], '#ebe0b0', .02);
    }
  }
  k.cylinder(x, y + height + .025, z, radius * .95, .05, '#c9b480', { segments: 16 });
  for (const rr of [radius * .4, radius * .8]) k.torus(x, y + height + .055, z, rr, .009, '#a18953');
}

function pine(k, x, y, z, height = 6, snow = true) {
  k.cylinder(x, y + height * .36, z, .15, height * .72, '#6c5540', { segments: 8 });
  for (let i = 0; i < 5; i++) {
    const r = height * (.24 - i * .034), yy = y + height * (.28 + i * .145);
    k.cone(x, yy, z, r, height * .36, '#356748', 10);
    if (snow) k.cone(x, yy + height * .075, z, r * .9, height * .26, '#eef3e8', 10);
  }
  k.collide(x, z, .32, .32, { y, h: height });
}

function patternedStone(k, x, y, z, w, h, d, color = '#bcb99a') {
  k.box(x, y + h / 2, z, w, h, d, color);
  for (let i = 0; i < 3; i++) {
    const t = i * .16, points = [[x - w * .32 + t, y + h * .9, z + d / 2 + .014], [x - w * .32 + t, y + h * .24 + t, z + d / 2 + .014], [x + w * .24 - t, y + h * .24 + t, z + d / 2 + .014], [x + w * .24 - t, y + h * .72 - t, z + d / 2 + .014]];
    k.line(points, '#95906e', .013);
  }
}

export const natureMaps = [
  {
    id: 'EagleTown', name: '독수리 마을', category: '자연', file: 'EagleTown.jpg',
    description: '층층이 이어지는 황금빛 절벽과 거대한 해바라기, 새 둥지의 고원',
    width: 30, depth: 31, spawn: [-6, 12], fog: '#a7d6c8', sky: '#a8d8d6',
    build(k) {
      k.floor(30, 31, '#809d73', { tile: 'sand', y: -1.5 }); k.surfaces.pop();
      cliff(k, -4, 10, 17, 8, 0, '#dbc875', -2, 4);
      cliff(k, -5, 1.5, 17, 8, 1.35, '#e3cf76', -2, 8);
      cliff(k, 1, -6, 17, 7, 2.7, '#e8d47a', -2, 9);
      cliff(k, -4, -11, 12, 6, 4.05, '#e7d577', -2, 12);
      cliff(k, 9, 6, 6, 10, .15, '#d6ca79', -2, 18);
      cliff(k, 7.5, 1.7, 8, 6, 1.35, '#e3cf76', -2, 20);
      stairsFrom(k, -4, 7, 3.4, 9, .15, .39, '#ccb962');
      stairsFrom(k, 3.4, -.8, 3.4, 9, .15, .38, '#cfbd69', 1.35);
      stairsFrom(k, -4, -7.25, 3.8, 9, .15, .35, '#d6c36d', 2.7);
      stairsFrom(k, 7.5, 5.5, 2.8, 8, .15, .4, '#c6b65f', .15);
      // A giant sunflower is the focal point of the top terrace.
      k.cylinder(-4.2, 6.0, -11.2, .3, 3.8, '#6d852e', { segments: 11 });
      const leaf = k.sphere(-3.4, 5.4, -11.0, 1, '#779837', [1.5, .15, .45]);
      if (leaf?.rotation) leaf.rotation.z = -.3;
      const flower = new k.THREE.Group(); flower.position.set(-4.2, 7.5, -11.25); flower.rotation.x = .2;
      const disc = new k.THREE.Mesh(new k.THREE.CylinderGeometry(1.05, 1.08, .32, 32), new k.THREE.MeshStandardMaterial({ color: '#837421', roughness: 1 }));
      disc.rotation.x = Math.PI / 2; flower.add(disc);
      const petalGeometry = new k.THREE.SphereGeometry(1, 8, 6), seedGeometry = new k.THREE.SphereGeometry(.043, 4, 3);
      const petals = [new k.THREE.InstancedMesh(petalGeometry, k.material('#dbc538'), 11), new k.THREE.InstancedMesh(petalGeometry, k.material('#f4df45'), 11)];
      const seeds = [new k.THREE.InstancedMesh(seedGeometry, k.material('#565a24'), 45), new k.THREE.InstancedMesh(seedGeometry, k.material('#c3b344'), 45)];
      const fm = new k.THREE.Matrix4(), fq = new k.THREE.Quaternion();
      for (let i = 0; i < 22; i++) {
        const a = i * TAU / 22; fq.setFromAxisAngle(new k.THREE.Vector3(0, 0, 1), a - Math.PI / 2);
        fm.compose(new k.THREE.Vector3(Math.cos(a) * 1.57, Math.sin(a) * 1.57, -.03), fq, new k.THREE.Vector3(.29, .99, .13)); petals[i % 2].setMatrixAt(Math.floor(i / 2), fm);
      }
      const seedRand = rng(22);
      for (let i = 0; i < 90; i++) {
        const a = seedRand() * TAU, r = Math.sqrt(seedRand()) * .98;
        fm.makeTranslation(Math.cos(a) * r, Math.sin(a) * r, .19); seeds[i % 2].setMatrixAt(Math.floor(i / 2), fm);
      }
      [...petals, ...seeds].forEach(m => { m.castShadow = true; m.receiveShadow = true; m.computeBoundingSphere(); flower.add(m); });
      k.root.add(flower);
      nest(k, -4.2, 4.07, -10.3, 1.8, 0);
      nest(k, 5.1, 2.72, -6.7, 1.15, 3);
      nest(k, -10, 1.38, 1.5, 1.1, 3);
      nest(k, 9.0, 2.72, -8.5, .9, 2);
      tree(k, 6, 2.7, -10.5, 7, .4, 2.2, { bare: true });
      tree(k, 10.4, 2.7, -9.7, 6.6, .4, 2.1, { bare: true });
      tree(k, -6.0, 4.05, -13.2, 8, .8, 2.8, { bare: true });
      addWater(k, 10, .22, 5.8, 2.3, [1, 1, 1.3]);
      shrub(k, 8.9, .15, 9.9, 1.5, '#6f8d29');
      shrub(k, 10.6, .15, 9.8, 1.4, '#4f792a');
      for (const [x, z, y, s] of [[-11, 10, 0, .85], [-9, 7, 0, .55], [-11, -1, 1.35, .8], [2, -3.9, 2.7, .6], [8, -5.3, 2.7, .65], [-8, -10, 4.05, .75]]) rock(k, x, y, z, s, '#b0bba0', true);
      stones(k, -4, 10, 13, 5, 17, .035, 5, '#ebdd9e');
      stones(k, -5, 1.5, 12, 5, 15, 1.4, 8, '#f0df96');
      k.interactions.push({ name: '거대한 해바라기', position: [-4.2, 5, -9], kind: 'inspect', text: '절벽 정상에 뿌리내린 해바라기와 나뭇가지로 엮인 거대한 둥지입니다.' }, { name: '새 둥지', position: [5.1, 3.5, -6.7], kind: 'inspect', text: '둥지 안에 크림빛 알 세 개가 놓여 있습니다.' });
      k.features.push('4단 암벽 테라스', '실제 높이가 있는 돌계단', '거대 해바라기의 꽃잎과 씨앗', '알이 놓인 둥지', '나뭇가지와 고원 연못');
    },
  },
  {
    id: 'Nymphen', name: '님펜 나무 마을', category: '자연', file: 'Nymphen.jpg',
    description: '거대한 나무 위의 집과 넝쿨 다리, 나선 무늬 난간이 있는 숲 마을',
    width: 31, depth: 29, spawn: [1, 11], fog: '#c6e1c5', sky: '#c7e4dc',
    build(k) {
      k.floor(31, 29, '#497b62', { tile: 'grass', y: -1.8 }); k.surfaces.pop();
      cliff(k, 0, 7.1, 11, 14, .25, '#bcaa79', -3, 7);
      cliff(k, -8.1, -.8, 9.3, 10.5, .25, '#b4a57a', -3, 12);
      cliff(k, 8, -2.5, 9.5, 10.5, 2.65, '#c0af80', -3, 21);
      cliff(k, -8, -7.4, 8.8, 6.2, 2.65, '#c6b385', -3, 44);
      cliff(k, 7.7, 5.5, 6.5, 6, .25, '#bcaa79', -3, 48);
      // The two trees carry the little houses and the woven balconies.
      tree(k, -8.3, -2.9, -8.4, 14, 1.85, 4.8, { seed: 24 });
      tree(k, 8.7, -2.9, -8.6, 15, 2, 5.1, { seed: 18 });
      roots(k, -8.3, -.2, -8.4, 2, 5.0, 8, 2.3);
      roots(k, 8.7, -.2, -8.6, 2.1, 5.1, 8, 2.8);
      beam(k, [-8, 7, -8], [0, 9.5, -12.1], .45, '#604127');
      beam(k, [0, 9.5, -12.1], [8.8, 8.5, -8.8], .32, '#604127');
      beam(k, [-1.3, 9.1, -11.7], [-.1, 10.5, -10.4], .13, '#604127');
      beam(k, [2, 9.1, -11.3], [4, 10.2, -11.9], .11, '#604127');
      stairsFrom(k, -10, -1.2, 2, 12, .2, .38, '#b9a57a', .25);
      stairsFrom(k, 8.5, 4.6, 2.7, 12, .2, .38, '#b9a57a', .25);
      // Central living-root bridge has a usable deck and visible bark underneath.
      const bx = -2.6, bz = 3.2;
      deck(k, bx, .29, bz, 7.4, 3.2, '#b8ab7c');
      roots(k, -6.2, -.35, 3.1, .5, 4.1, 3, .3);
      beam(k, [-6.4, -.2, 1.8], [-.4, -.1, 4.1], .3, C.bark);
      beam(k, [-6.4, -.2, 4.4], [-.4, -.1, 2.0], .26, C.barkLight);
      for (let i = 0; i < 6; i++) {
        shrub(k, -5.8 + i, .28, 1.73, .4, '#86a653');
        shrub(k, -5.8 + i, .28, 4.66, .4, '#86a653');
        hangingVines(k, -5.8 + i, .12, 4.64, .6, 3);
      }
      function scrollRail(x, y, z, length, rot = 0, gap = 0) {
        fence(k, x, y, z, length, { rot, height: .92, color: '#57573d', gap });
        const ca = Math.cos(rot), sa = Math.sin(rot);
        for (let i = 0; i < Math.floor(length / .65); i++) {
          const q = (i + .5) * .65 - length / 2;
          if (gap && Math.abs(q) < gap / 2) continue;
          const pts = [];
          for (let j = 0; j < 17; j++) {
            const a = j / 16 * Math.PI * 3, rr = .22 * (1 - j / 19);
            const px = q + Math.cos(a) * rr;
            pts.push([x + ca * px, y + .53 + Math.sin(a) * rr, z - sa * px]);
          }
          k.line(pts, '#5f6343', .018);
        }
      }
      // Leave stair-width openings in the front balcony rails.
      scrollRail(-11.85, 2.67, -4.43, .9);
      scrollRail(-6.6, 2.67, -4.43, 4.1);
      scrollRail(8.1, 2.67, -.02, 5.8, 0, 3.8);
      scrollRail(-11.7, 2.67, -7, 4.8, Math.PI / 2);
      scrollRail(11.9, 2.67, -3.7, 6.5, Math.PI / 2);
      for (const [x, z] of [[-8.0, -7.8], [8.6, -6.2]]) {
        k.box(x, 4.2, z, 3.6, 3, 3, '#86502f', { solid: true });
        door(k, x, 2.65, z + 1.54, 1.4, 2.4, '#6d3e2c');
        roof(k, x, 5.75, z, 4.7, 3.9, '#a45d35');
        for (let j = 0; j < 6; j++) {
          const t = (j + .5) / 6 * 4.6 - 2.3;
          k.sphere(x + t, 5.91 + (1 - Math.abs(t) / 2.3) * .77, z + 1.85, .55, j % 2 ? '#498540' : '#739c49', [1.2, .6, 1]);
        }
        shrub(k, x - 1.7, 2.67, z + 1.3, .52);
        shrub(k, x + 1.65, 2.67, z + 1.25, .55);
        // Carved curls on the timber doors.
        for (const side of [-1, 1]) for (let j = 0; j < 3; j++) {
          const pts = [];
          for (let t = 0; t < 18; t++) { const a = t * .38, r = .2 * (1 - t / 22); pts.push([x + side * .37 + Math.cos(a) * r, 3.2 + j * .56 + Math.sin(a) * r, z + 1.6]); }
          k.line(pts, '#c7a377', .026);
        }
      }
      for (const [x, z] of [[-11.4, -4.6], [-8.3, -4.6], [-5.5, -4.6]]) {
        k.cylinder(x, 1.3, z, .23, 2.7, '#7d8a69', { top: .33, segments: 9 });
        k.cone(x, 2.14, z, .46, .62, '#b4bf9b', 9);
        shrub(k, x, .25, z + .1, .55);
      }
      for (const [x, z, y] of [[-12, 2, .25], [-11, 3, .25], [-6.5, -4.5, 2.65], [11, -.5, 2.65], [5, -4, 2.65]]) shrub(k, x, y, z, .66);
      hangingVines(k, -9, .12, 4.4, 4, 8);
      hangingVines(k, 8, 2.55, 2.45, 6, 11);
      stones(k, 0, 8, 8, 10, 25, .3, 70, '#d1bf91');
      stones(k, -8, 0, 6, 5, 13, .3, 72, '#d2c093');
      stones(k, 8, -3, 6, 6, 16, 2.71, 75, '#d5c394');
      k.interactions.push({ name: '넝쿨 다리', position: [-2.6, 1.2, 3.2], kind: 'inspect', text: '아래쪽에는 굵은 나무 뿌리가, 가장자리에는 꽃과 늘어진 넝쿨이 이어집니다.' }, { name: '나무 위의 집', position: [8.6, 3.8, -4.2], kind: 'inspect', text: '소용돌이를 새긴 문과 작은 잎 지붕, 곡선 난간이 있는 나무집입니다.' });
      k.features.push('거목 두 그루와 공중 가지', '독립된 나무집 테라스', '문에 새겨진 나선 무늬', '실제 높이의 계단', '뿌리 다리와 늘어진 넝쿨');
    },
  },
  {
    id: 'Odanka', name: '오단카 숲', category: '자연', file: 'Odanka.png',
    description: '큰 나무와 통나무집, 시냇물 다리와 울타리 텃밭이 있는 숲',
    width: 32, depth: 30, spawn: [-5, 11], fog: '#c9d6a6', sky: '#ceddab',
    build(k) {
      k.floor(32, 30, '#89af39', { tile: 'grass' });
      path(k, [[-10, 13], [-8, 7], [-4, 2], [2, -2], [3, -8], [0, -12]], 2.05, '#dbcf85');
      path(k, [[-8, 7], [1, 9], [9, 6], [11, 0], [7, -5]], 1.8, '#e0d08b');
      path(k, [[-4, 2], [-8, -3], [-10, -9]], 1.6, '#ddce84');
      cabin(k, -9.7, .08, -10.3, 7.6, 4.8, { thatch: true, chimney: true });
      // The stream bends behind the tree and continues to the lake at the left.
      const river = [[-16, -4], [-10, -4.4], [-5.7, -5.3], [-1.4, -6.2], [.2, -9], [-1, -12], [-2.5, -15]];
      path(k, river, 1.35, '#775b35', .013);
      path(k, river, 1.06, '#57bbbd', .044);
      for (let i = 1; i < river.length; i++) {
        const [x1, z1] = river[i - 1], [x2, z2] = river[i];
        k.collide((x1 + x2) / 2, (z1 + z2) / 2, 1.0, Math.hypot(x2 - x1, z2 - z1), { y: 0, h: .13, rot: Math.atan2(x2 - x1, z2 - z1) });
      }
      for (let i = 1; i < river.length; i++) {
        const [x, z] = river[i];
        k.line([[x - .33, .08, z + .25], [x, .085, z], [x + .3, .08, z - .25]], '#c7eee1', .016);
      }
      addWater(k, -15.3, .043, 7.5, 3.6, [.85, 1, 1.9]);
      k.collide(-15.2, 7.5, 4.4, 12, { y: 0, h: .13 });
      for (let i = 0; i < 7; i++) {
        k.box(-2.4 + i * .38, .21, -6.6, .35, .19, 2.9, i % 2 ? '#bc9654' : '#a37a3d', { rot: .17 });
        k.surface(-2.4 + i * .38, -6.6, .4, 2.9, .31, { rot: .17 });
      }
      beam(k, [-2.8, .13, -8.15], [.4, .13, -7.65], .08, '#735532');
      beam(k, [-2.8, .13, -5.3], [.4, .13, -4.8], .08, '#735532');
      tree(k, 6, 0, -6.4, 11.8, 2.15, 5.9, { seed: 108 });
      roots(k, 6, .03, -6.4, 2.2, 4.35, 8, 2);
      // Dense woods frame the rear of the clearing.
      for (const [x, z, h, r] of [[12, -11, 9, .55], [15, -12, 9.6, .65], [11, -14, 10, .58], [0, -14, 9, .48]]) tree(k, x, 0, z, h, r, 2.8, { seed: x + 32 });
      tree(k, -9.7, 0, 3.6, 4.4, .25, 1.55, { seed: 16 });
      for (const [x, z] of [[14, -3], [14, 3], [11, 12], [1, 13], [-1, -1]]) shrub(k, x, 0, z, 1.25, '#498039');
      // Raised rows of earth, crop seedlings, fence rails, and an open gate.
      k.box(-.8, .04, 6.5, 7.3, .08, 4.7, '#897044');
      for (let i = 0; i < 6; i++) {
        const z = 4.6 + i * .73;
        k.box(-.8, .15, z, 6.8, .22, .47, '#be9860');
        for (let j = 0; j < 10; j++) {
          const x = -3.6 + j * .6;
          k.sphere(x, .3, z, .065, '#739142', [1, 1.7, .5]);
        }
      }
      fence(k, -.8, 0, 4.1, 7.5);
      fence(k, -.8, 0, 8.95, 7.5, { gap: 1.9 });
      fence(k, -4.55, 0, 6.5, 4.85, { rot: Math.PI / 2 });
      fence(k, 2.95, 0, 6.5, 4.85, { rot: Math.PI / 2 });
      // The nearby stump has concentric growth rings and spreading old roots.
      k.cylinder(6.8, .65, 7.7, 1.05, 1.3, '#76502d', { top: .88, segments: 11, solid: true });
      k.cylinder(6.8, 1.31, 7.7, .88, .045, '#c9a265', { segments: 24 });
      for (const rr of [.2, .4, .62, .81]) k.torus(6.8, 1.343, 7.7, rr, .012, '#997745');
      roots(k, 6.8, 0, 7.7, .7, 1.4, 5, .45);
      k.interactions.push({ name: '나무 그루터기', position: [6.8, 1.4, 7.7], kind: 'seat', text: '연륜이 남은 커다란 그루터기에 잠시 앉습니다.' });
      // Carved guardian post behind the great tree.
      k.cylinder(11.2, 1.4, -6.5, .38, 2.8, '#947c45', { segments: 8, solid: true });
      for (const yy of [.65, 1.25, 1.95]) {
        k.torus(11.2, yy, -6.5, .38, .065, '#5c4a29');
        k.sphere(11.2, yy + .26, -6.11, .19, '#6d572d', [1, .32, .18]);
      }
      for (const side of [-1, 1]) k.sphere(11.2 + side * .14, 2.48, -6.11, .065, '#312f20');
      k.box(-11.7, .78, 6.3, .08, 1.55, .08, '#6a4c2d');
      k.box(-11.7, 1.34, 6.3, 1.1, .63, .11, '#987441', { rot: -.15 });
      k.text('ODANKA', -11.7, 1.35, 6.37, { width: .98, height: .46, background: '#967243', color: '#392d1e', rot: -.15 });
      for (const [x, z, s] of [[-7, 1, .92], [2.9, 2.9, .92], [3.7, 3.1, .65], [-11.4, 9, .64], [-8.9, 6.6, .45]]) rock(k, x, 0, z, s, '#797c65', true);
      for (let i = 0; i < 22; i++) {
        const x = -13.5 + Math.sin(i * 1.3) * .4, z = 4.2 + i * .23;
        beam(k, [x, .02, z], [x + Math.sin(i) * .15, .7 + (i % 4) * .13, z], .023, '#6d8c39');
      }
      stones(k, -5, 9, 5, 8, 25, .035, 39, '#ddd4a0');
      stones(k, 8, 5, 5, 8, 23, .035, 43, '#ddd4a0');
      flowers(k, -7, -1, 5, 3, 25, 0, 9);
      flowers(k, 11, 8, 5, 4, 23, 0, 11);
      flowers(k, -7, -12, 3, 2, 15, 0, 13);
      k.interactions.push({ name: '텃밭', position: [-.8, .8, 8.9], kind: 'inspect', text: '울타리 사이로 여섯 줄의 밭이랑과 작은 새싹들이 보입니다.' }, { name: '시냇물 다리', position: [-1.2, 1, -6.5], kind: 'inspect', text: '각기 다른 폭의 나무판이 맑은 시냇물을 가로지릅니다.' });
      k.features.push('거목의 굵은 뿌리와 수피', '곡선 시냇물과 판자 다리', '통나무집과 벽돌 굴뚝', '밭이랑과 열린 울타리', '그루터기 나이테', '갈대와 조각 기둥');
    },
  },
  {
    id: 'PrimitiveTown', name: '고대 토템 마을', category: '자연', file: 'PrimitiveTown.png',
    description: '석조 신전과 문양 토템, 초록빛 계단식 테라스의 오래된 마을',
    width: 29, depth: 35, spawn: [-6, 14], fog: '#d1ddab', sky: '#cddab4',
    build(k) {
      k.floor(29, 35, '#a8aa7c', { tile: 'sand', y: -.5 });
      cliff(k, 0, 10.4, 24, 10, 0, '#98c13f', -1.2, 31);
      cliff(k, 0, 1.5, 23, 9.5, 1.2, '#9dca40', -1.2, 34);
      cliff(k, 1, -8.5, 21, 10.8, 2.4, '#a7d449', -1.2, 37);
      // Dressed retaining walls provide the layered stone architecture.
      masonry(k, -8.95, -.9, 15.3, 1.5, .9, '#bcb99b');
      masonry(k, 3.55, -.9, 15.3, 15.5, .9, '#bcb99b');
      masonry(k, -8.8, 0, 6.2, 1.4, 1.2, '#c3bda0');
      masonry(k, 3.6, 0, 6.2, 15.8, 1.2, '#c3bda0');
      masonry(k, -6.05, 1.2, -3, 5.9, 1.2, '#c9c3a3');
      masonry(k, 5.85, 1.2, -3, 10.3, 1.2, '#c9c3a3');
      stairsFrom(k, -6.2, 15.5, 3.4, 4, .1, .42, '#c4c0a0', -.4);
      stairsFrom(k, -6.2, 7.25, 3.2, 6, .2, .42, '#c9c5a6');
      stairsFrom(k, -1.2, -1.15, 3.2, 6, .2, .42, '#cec8aa', 1.2);
      // Monumental carved face at the middle level.
      const tx = -1.3, tz = -.2;
      k.cylinder(tx, 1.36, tz, 1.35, .32, '#a79e7b', { top: 1.4, segments: 12 });
      k.cylinder(tx, 1.65, tz, 1.13, .33, '#b8a781', { segments: 12 });
      totem(k, tx, 1.8, tz, 4.0, .86, '#a79468');
      for (const side of [-1, 1]) {
        const pts = [];
        for (let i = 0; i < 24; i++) {
          const a = i * .22, r = .51 * (1 - i / 33);
          pts.push([tx + side * (1.12 + Math.sin(a) * r), 5.0 + Math.cos(a) * r, tz + .06]);
        }
        k.line(pts, '#bcb88a', .075);
        beam(k, [tx + side * .78, 3.5, tz], [tx + side * 1.13, 3.1, tz + .12], .12, '#a75937');
      }
      // Round stone shrine to the left; three arched recesses are carved into it.
      const sx = -9, sz = -7;
      k.cylinder(sx, 3.53, sz, 2.5, 2.26, '#bdb99d', { segments: 24, solid: true });
      k.cylinder(sx, 4.79, sz, 2.68, .27, '#d1caae', { segments: 24 });
      for (let j = 0; j < 5; j++) k.torus(sx, 2.7 + j * .4, sz, 2.5, .014, '#817e68');
      for (const a of [-.7, 0, .7]) {
        const px = sx + Math.sin(a) * 2.54, pz = sz + Math.cos(a) * 2.54;
        k.box(px, 3.37, pz, .87, 1.4, .03, '#4e5843', { rot: a });
        k.sphere(px, 4.06, pz, .46, '#4e5843', [1, .9, .09]);
      }
      deck(k, -6.3, 4.93, -7.3, 1.7, .85, '#d1caae');
      stairsFrom(k, -6.15, -3.95, 1.85, 10, .253, .32, '#d2cab0', 2.4);
      k.surface(sx, sz, 3.8, 3.8, 4.93);
      // Rear temple uses patterned blocks, a real portico, and a stepped foundation.
      deck(k, 2, 2.7, -12.2, 9.1, 5.3, '#cec9a9');
      patternedStone(k, 2, 2.7, -12.7, 8, .62, 4.8, '#b7b398');
      k.box(2, 4.4, -13.4, 7.9, 2.8, 2.7, '#b9b69b', { solid: true });
      k.box(2, 5.84, -12.7, 9.5, .5, 5.2, '#cfccb0');
      for (const side of [-1, 1]) {
        patternedStone(k, 2 + side * 2.5, 3.32, -10.8, 1.3, 2.35, 1.3);
        k.box(2 + side * 2.5, 4.17, -10.12, 1.34, .38, .025, '#baa77c');
        k.box(2 + side * 2.5, 5.22, -10.12, 1.34, .28, .025, '#81a291');
      }
      k.box(2, 4.44, -12.01, 1.35, 2.2, .1, '#536050');
      deck(k, 2, 3.32, -10.75, 6.3, 2.1, '#c6c2a5');
      stairsFrom(k, 2, -8.6, 4.6, 4, .23, .4, '#d6cfb1', 2.4);
      // Small stone hut and hanging woven doorway at the right.
      masonry(k, 8.2, 1.2, 3.2, 3.2, 2.3, '#bcb695');
      masonry(k, 9.9, 1.2, 1.7, 3, 2.3, '#bcb695', Math.PI / 2);
      k.box(8.2, 3.62, 1.7, 4.1, .3, 3.8, '#8f5e3c');
      roof(k, 8.2, 3.65, 1.7, 4.1, 3.8, '#b69a61');
      for (let i = 0; i < 11; i++) {
        const x = 6.4 + i * .34;
        k.line([[x, 3.67, 3.66], [x + .17, 4.0, 3.66], [x + .34, 3.67, 3.66]], i % 2 ? '#538f79' : '#ddd3a1', .035);
      }
      k.box(8.2, 2.35, 3.4, 1.35, 2.1, .08, '#8c432e');
      for (let i = 0; i < 14; i++) k.box(7.59 + i * .09, 2.32, 3.47, .033, 2.08, .014, i % 3 ? '#b57044' : '#657e48');
      // A second portal shrine is recessed into the top grass level.
      masonry(k, 8.5, 2.4, -6.2, 2.2, 2.2, '#c9c6a7');
      k.box(8.5, 3.42, -5.97, 1.19, 1.95, .04, '#663d29');
      for (let i = 0; i < 13; i++) beam(k, [7.95 + i * .088, 2.42, -5.94], [8.06 + i * .088, 4.3, -5.94], .025, i % 2 ? '#d29353' : '#629765');
      k.sphere(8.5, 4.57, -6.2, 1.15, '#c3bea0', [1, .44, .35]);
      for (const [x, z, y, h, col] of [[-9.2, 12, 0, 2.8, '#a49b6e'], [-3.8, 12, 0, 3.2, '#ad8c59'], [8.3, -.5, 1.2, 2.2, '#a57b4f'], [9.3, -.8, 1.2, 2, '#6b9b90'], [-3.8, -6, 2.4, 2.3, '#8eab93'], [2.9, -5.7, 2.4, 2.5, '#a46f4b']]) totem(k, x, y, z, h, .35, col);
      // Small lower columns and masks echo the original village entrance.
      for (const [x, z] of [[-8.6, 14.6], [-4, 14.6], [5.2, 9.2]]) {
        totem(k, x, -.15, z, 1.5, .34, '#a9966b', false);
        k.sphere(x, .88, z + .31, .25, '#604d32', [1, .3, .45]);
      }
      for (const [x, z, y] of [[-12, -2, 1.2], [11.7, -7.8, 2.4], [-11.5, 10, 0]]) tree(k, x, y, z, 8.5, .8, 2.8, { seed: Math.abs(x * 4) });
      for (let i = 0; i < 20; i++) { const x = -9 + i; rock(k, x, 1.2, 5.9, .16 + i % 3 * .05, '#a6ae90'); }
      shrub(k, -10.6, 2.4, -10.5, .9);
      shrub(k, 10.7, 2.4, -10, 1.0);
      flowers(k, 5, 0, 4, 4, 15, 1.2, 44);
      k.interactions.push({ name: '중앙 토템', position: [-1.3, 3.4, 1.15], kind: 'inspect', text: '붉은 볼과 긴 코, 소용돌이 장식, 정교한 삼각 띠가 새겨진 수호 토템입니다.' }, { name: '고대 신전', position: [2, 4.3, -9.5], kind: 'inspect', text: '회색 녹색 띠와 기하학 무늬가 남은 석조 기둥입니다.' });
      k.features.push('3단 풀밭 석축', '새겨진 얼굴과 채색 토템', '패턴을 새긴 신전 기둥', '원형 석조 사당', '짜임 무늬의 지붕과 문', '높이에 맞춘 모든 계단');
    },
  },
  {
    id: 'SnowyTown', name: '눈 내린 마을', category: '자연', file: 'SnowyTown.png',
    description: '눈 덮인 목조집과 벽돌 굴뚝, 전나무 숲과 굽은 돌길의 겨울 마을',
    width: 31, depth: 36, spawn: [1, 13], fog: '#d9e7eb', sky: '#dfecef',
    build(k) {
      k.floor(31, 36, '#e5e9df', { tile: 'snow' });
      path(k, [[0, 17], [0, 11], [-3, 6], [-4, 0], [-2, -5], [-6, -11], [-6, -17]], 3.3, '#707975');
      path(k, [[-4, 0], [2, -.5], [6, -4], [9, -8]], 2.35, '#7a827d');
      path(k, [[-3, 6], [5, 5.5], [9, 9]], 2.25, '#75807a');
      path(k, [[0, 11], [-6, 11], [-8, 12]], 2, '#78807b');
      const r = rng(64);
      // Individually visible rounded cobbles and snowy roadside banks.
      for (let i = 0; i < 140; i++) {
        const t = i / 139, z = 16 - t * 31;
        const cx = z > 6 ? -1 : z > -3 ? -4 : -4 + Math.sin(t * 8) * 1.3;
        k.sphere(cx + (r() - .5) * 2.8, .063, z, .21 + r() * .13, i % 3 ? '#90978e' : '#b2b6aa', [1, .22, .82]);
      }
      cabin(k, -8.2, .12, 10, 4.9, 3.7, { snow: true, thatch: false });
      cabin(k, 6.1, .15, 4.7, 7.2, 4.1, { snow: true, thatch: false });
      cabin(k, -8.5, .15, -2.5, 6.1, 4, { snow: true, thatch: false });
      cabin(k, 8.5, .95, -9.6, 5.3, 4, { snow: true, thatch: false, color: '#668979', chimney: false });
      deck(k, 8.5, .95, -7.4, 3.6, 1.6, '#abb4a7');
      stairsFrom(k, 8.5, -5.5, 2.3, 5, .19, .34, '#a0aba3');
      k.box(6.4, 2.67, -7.25, 1.2, .58, .17, '#456c65');
      k.text('SNOW', 6.4, 2.7, -7.14, { width: 1.0, height: .38, background: '#456c65', color: '#dfecdc' });
      // Mansion at the top-left, with green trim and warm window panes.
      k.box(-6.5, 3.1, -15, 9.4, 6.2, 4.7, '#bec7b4', { solid: true });
      k.box(-6.5, 1.0, -12.6, 9.4, .6, .1, '#6d9180');
      k.box(-6.5, 3.5, -12.6, 9.4, .6, .1, '#6d9180');
      roof(k, -6.5, 6.2, -15, 10, 5.3, '#8a9e90', { snow: true });
      for (const yy of [2.1, 4.7]) for (const xx of [-9.4, -3.6]) {
        k.box(xx, yy, -12.56, 1.2, 1.55, .1, '#866746');
        k.box(xx, yy, -12.49, .9, 1.28, .035, '#d8bd78');
        k.box(xx, yy, -12.46, .05, 1.3, .04, '#6b7160');
        k.box(xx, yy, -12.46, .92, .065, .04, '#6b7160');
        for (const side of [-1, 1]) k.box(xx + side * .73, yy, -12.52, .3, 1.55, .06, '#9c6c49');
        k.box(xx, yy + .84, -12.46, 1.44, .17, .32, '#eff2e6');
      }
      door(k, -6.5, .8, -12.54, 1.6, 2.5, '#78523b');
      deck(k, -6.5, .8, -11.75, 3, 1.0, '#b2b8aa');
      stairsFrom(k, -6.5, -10.1, 2.5, 4, .2, .38, '#a4aea4');
      // Snow-covered conifers behind the houses and around the frozen pond.
      for (const [x, z, h] of [[2, -16, 7.8], [5, -16, 7.1], [8, -16, 6.8], [11, -15, 7.2], [14, -15, 6.6], [13, -11, 6.5], [14, -6, 6.7], [13, -.5, 5.5], [14, 7, 6.4], [11, 11, 5.4], [-14, -12, 6.7], [-14, 0, 5.8]]) pine(k, x, 0, z, h);
      addWater(k, 10.5, .035, -.1, 2.0, [1.15, 1, .78]);
      k.cylinder(10.5, .095, -.1, 1.99, .045, '#b9deea', { segments: 32 });
      for (let i = 0; i < 10; i++) { const a = i * TAU / 10; k.sphere(10.5 + Math.cos(a) * 2.1, .14, -.1 + Math.sin(a) * 1.7, .42, '#f4f5e9', [1, .53, .8]); }
      // Statue and pedestal at the central intersection.
      k.cylinder(-4.2, .3, 3.3, .94, .6, '#9d9e8b', { segments: 12, solid: true });
      k.cylinder(-4.2, .7, 3.3, .66, .24, '#bbc0ab', { segments: 12 });
      k.cone(-4.2, 1.34, 3.3, .46, 1.14, '#a7b0a0', 12);
      k.sphere(-4.2, 2.04, 3.3, .23, '#b6c0b0');
      beam(k, [-4.43, 1.6, 3.3], [-4.87, 2.27, 3.3], .095, '#b6c0b0');
      beam(k, [-3.95, 1.6, 3.3], [-3.7, 1.12, 3.54], .075, '#b6c0b0');
      k.sphere(-4.2, 2.24, 3.3, .24, '#f7f7ed', [1, .35, 1]);
      for (const [x, z] of [[-1, 9], [-1.3, -.5], [-10, 6], [6, -3], [-3, -8], [10, 8]]) {
        k.cylinder(x, 1.5, z, .045, 3, '#735546', { segments: 8 });
        k.box(x, 2.9, z, .33, .39, .33, '#ddd6a7');
        k.cone(x, 3.2, z, .32, .3, '#80715d', 4);
        k.sphere(x, 3.3, z, .22, '#f1f3e5', [1, .35, 1]);
      }
      fence(k, -7.6, 0, 15.2, 12, { color: '#8a5445', height: .68 });
      fence(k, 7.5, 0, 15.2, 11, { color: '#8a5445', height: .68 });
      for (let i = 0; i < 17; i++) {
        const x = -13 + (i % 5) * 6.4, z = -12 + Math.floor(i / 5) * 8;
        k.sphere(x, .12, z, .8 + r() * .5, '#f3f4e9', [1.3, .18, .85]);
      }
      k.interactions.push({ name: '눈 덮인 동상', position: [-4.2, 1.6, 3.3], kind: 'inspect', text: '작은 석상과 받침대 위에 얇은 눈이 쌓여 있습니다.' }, { name: '얼어붙은 연못', position: [10.5, .6, 1.8], kind: 'inspect', text: '푸른 얼음 주위로 전나무와 눈 덩어리가 둘러싸여 있습니다.' });
      k.features.push('눈 지붕과 개별 고드름', '붉은 벽돌 굴뚝', '전나무의 층별 적설', '골목을 잇는 돌길', '녹색 별장과 계단', '석상과 얼어붙은 연못');
    },
  },
  {
    id: 'Mine', name: '절벽 광산', category: '던전', file: 'Mine.jpg',
    description: '깊은 협곡 사이의 판자 다리와 광차, 갱도와 광석 작업장',
    width: 30, depth: 31, spawn: [-5.5, 11], fog: '#8c9799', sky: '#5d686d',
    build(k) {
      k.box(0, -4.1, 0, 30, .2, 31, '#a4b0ae');
      cliff(k, -5, 9.5, 15, 10.8, 0, '#b8965b', -3.9, 73);
      cliff(k, -6, -3.7, 13, 8.4, 2.2, '#bca068', -4, 77);
      cliff(k, 8.6, -1.9, 8.4, 9.5, 2.2, '#999388', -4, 79);
      cliff(k, 3, -10.4, 8.2, 6.8, 4.0, '#c2a36a', -4, 80);
      stairsFrom(k, -10, 4.7, 1.9, 11, .2, .43, '#92744b');
      // High narrow ladder-like stair to the back extraction shelf.
      stairsFrom(k, 1.2, -5.6, 1.6, 9, .2, .29, '#b0a289', 2.2, 0, { floating: true });
      for (const side of [-1, 1]) beam(k, [1.2 + side * .69, 2.24, -5.55], [1.2 + side * .69, 4.2, -8.4], .055, '#cabdad');
      // Main horizontal bridge crossing the chasm at the upper level.
      for (let i = 0; i < 11; i++) {
        const x = -.1 + i * .45;
        k.box(x, 2.09, -2.0, .42, .18, 2.2, i % 2 ? '#ae844e' : '#c29a5c', { rot: (i % 3 - 1) * .018 });
        k.surface(x, -2, .47, 2.2, 2.2);
      }
      for (const side of [-1, 1]) {
        k.line([[-.35, 2.08, -2 + side * 1.05], [2.05, 1.9, -2 + side * 1.05], [4.7, 2.08, -2 + side * 1.05]], '#735632', .08);
        fence(k, 2.1, 2.2, -2 + side * 1.17, 5.3, { rope: true, height: .82 });
      }
      // The lower bridge climbs gently to the right ledge, plank by plank.
      for (let i = 0; i < 16; i++) {
        const t = (i + .5) / 16, x = 2.05 + t * 6.65, z = 9.6 - t * 7.6, y = t * 2.2;
        const heading = Math.atan2(-6.65, 7.6);
        k.box(x, y - .1, z, 2.15, .19, .56, i % 2 ? '#c09a5f' : '#aa824a', { rot: heading });
        k.surface(x, z, 2.15, .69, y, { rot: heading });
      }
      for (const side of [-1, 1]) {
        const pts = [];
        for (let i = 0; i <= 4; i++) {
          const t = i / 4, x = 2.05 + t * 6.65 + side * .81, z = 9.6 - t * 7.6 + side * .69, y = t * 2.2;
          k.cylinder(x, y + .4, z, .07, .8, '#8d6b3f', { segments: 6 });
          pts.push([x, y + .75 - (i % 2 ? .13 : 0), z]);
        }
        k.line(pts, '#b9a985', .036);
      }
      // Craggy cave walls wrap around the working terraces.
      const rr = rng(24);
      for (let i = 0; i < 26; i++) {
        const x = -14.5 + i * 1.12, z = -14.3 + Math.sin(i * 1.13) * .8, h = 8 + rr() * 3;
        k.cylinder(x, h / 2 - 2, z, .7 + rr() * .36, h, i % 3 ? '#4c514c' : '#687068', { top: .25, segments: 5, solid: true });
      }
      for (let i = 0; i < 14; i++) {
        const z = -12 + i * 1.8;
        k.cylinder(-14.3, 3.1, z, .78, 9.5, i % 2 ? '#555b52' : '#777566', { top: .34, segments: 5, solid: true });
      }
      function mineEntrance(x, y, z, stone = false) {
        k.box(x, y + 1.45, z, 2, 2.9, .13, '#171f1e');
        for (const side of [-1, 1]) {
          k.box(x + side * 1.14, y + 1.5, z + .08, .22, 3, .35, '#95794c');
          beam(k, [x + side * 1.22, y, z + .14], [x + side * .8, y + 2.95, z + .14], .09, '#c5a878');
        }
        k.box(x, y + 3.06, z + .08, 2.7, .3, .4, '#bc9865');
        if (stone) {
          for (let j = 0; j < 7; j++) for (const side of [-1, 1]) rock(k, x + side * (1.46 + (j % 2) * .2), y + j * .48, z, .38, j % 2 ? '#bc9a64' : '#a18354');
          for (let j = 0; j < 5; j++) rock(k, x - 1.45 + j * .7, y + 3.3, z, .4, '#c5a16e');
        } else roof(k, x, y + 3.16, z, 3.1, 1.45, '#b58a43', { thatch: true });
        for (let i = 0; i < 4; i++) k.box(x, y + .065 + i * .11, z + .52 + i * .25, 1.8, .14, .3, '#a09781');
        k.interactions.push({ name: '광산 갱도', position: [x, y + 1.1, z + 1.1], kind: 'inspect', text: '목재 지지대와 어두운 갱도 입구, 낡은 광차 선로가 보입니다.' });
      }
      mineEntrance(-6.7, 2.2, -6.4);
      mineEntrance(3, 4, -12.0);
      mineEntrance(9.1, 2.2, -4.7, true);
      // Tracks lead to the upper entrances; each rail has visible sleepers.
      function tracks(x, y, z, length, rot = 0) {
        const c = Math.cos(rot), s = Math.sin(rot);
        for (const side of [-1, 1]) beam(k, [x + c * side * .39 + s * length / 2, y + .065, z - s * side * .39 + c * length / 2], [x + c * side * .39 - s * length / 2, y + .065, z - s * side * .39 - c * length / 2], .043, '#4b4840');
        for (let i = 0; i <= Math.ceil(length / .45); i++) {
          const t = (i / Math.ceil(length / .45) - .5) * length;
          k.box(x + s * t, y + .02, z + c * t, 1.3, .08, .16, '#6e5134', { rot });
        }
      }
      tracks(-6.7, 2.22, -4.5, 3.2);
      tracks(9.1, 2.22, -2.7, 3.5);
      tracks(-10.8, 2.22, -4.3, 3.4, -.68);
      function cart(x, y, z, rot = 0) {
        const g = new k.THREE.Group();
        const before = k.root.children.length;
        k.box(x, y + .39, z, 1.5, .13, 1, '#575b57');
        k.box(x, y + .72, z - .5, 1.55, .6, .09, '#8b928b');
        k.box(x, y + .72, z + .5, 1.55, .6, .09, '#6e7771');
        k.box(x - .74, y + .72, z, .09, .6, 1.07, '#8a928b');
        k.box(x + .74, y + .72, z, .09, .6, 1.07, '#747d75');
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          const wheel = k.cylinder(x + sx * .72, y + .23, z + sz * .32, .21, .12, '#343b36', { segments: 10 });
          wheel.rotation.z = Math.PI / 2;
        }
        for (let i = 0; i < 7; i++) rock(k, x + (i % 3 - 1) * .32, y + .58, z + (i % 2 ? .19 : -.19), .22, '#717b76');
        if (rot) {
          const children = k.root.children.slice(before);
          for (const child of children) { child.position.x -= x; child.position.z -= z; g.add(child); }
          g.position.set(x, 0, z); g.rotation.y = rot; k.root.add(g);
        }
        k.collide(x, z, 1.6, 1.1, { y, h: 1.1, rot });
      }
      cart(-3.7, 2.2, -5.3, -.25);
      cart(11.3, 2.2, -1.8);
      // Lower miners' workshop with a wooden awning and two metal flues.
      k.box(-8.2, 1.19, 9.7, 4.7, 2.38, 3.6, '#76532f', { solid: true });
      roof(k, -8.2, 2.4, 9.7, 5.3, 4.2, '#b18c43', { thatch: true });
      k.box(-8.2, 1.1, 11.55, 2.9, 1.8, .03, '#baa97a');
      k.text('MINE', -8.2, 1.6, 11.62, { width: 1.8, height: .47, background: '#baa97a', color: '#544734' });
      for (const [x, z, h] of [[-11.3, 9, 4.8], [-5.9, 9.0, 5.3]]) {
        k.cylinder(x, .51, z, .45, 1.02, '#797f77', { segments: 12 });
        k.cylinder(x, 1.02 + h / 2, z, .17, h, '#afb8b2', { segments: 12 });
        k.cone(x, 1.02 + h + .21, z, .35, .45, '#b9c0b8', 12);
        k.torus(x, 1.08, z, .26, .06, '#656e65');
      }
      barrel(k, -4.6, 0, 8.5, 1.15);
      barrel(k, -3.6, 0, 8.3, .86);
      k.box(-10.1, .42, 12.7, .9, .84, .9, '#967644', { solid: true });
      beam(k, [-10.55, .1, 13.16], [-9.66, .84, 13.16], .05, '#c2a473');
      beam(k, [-9.66, .1, 13.16], [-10.55, .84, 13.16], .05, '#c2a473');
      for (const [x, z, y] of [[-1.7, 12.4, 0], [-11.8, -5, 2.2], [5.7, -10.2, 4], [11.8, 1.2, 2.2]]) {
        for (let i = 0; i < 18; i++) { const a = i * 2.4, rad = .25 + i % 4 * .22; rock(k, x + Math.cos(a) * rad, y + (i < 6 ? .26 : 0), z + Math.sin(a) * rad, .18 + i % 3 * .05, i % 2 ? '#737f79' : '#9aa39b'); }
      }
      fence(k, -5.8, 2.2, .15, 10.7, { rope: true });
      fence(k, -5, 0, 4.11, 6.2, { rope: true });
      k.interactions.push({ name: '광차', position: [-3.7, 3.0, -5.3], kind: 'inspect', text: '철제 광차 안에는 부서진 회색 광석이 가득 실려 있습니다.' }, { name: '광부 작업장', position: [-8.2, 1.1, 12.5], kind: 'inspect', text: '판자 지붕, 금속 연통, 나무 상자와 광부용 통이 있는 작업장입니다.' });
      k.features.push('4개 절벽 작업대', '로프와 개별 판자의 협곡 다리', '오를 수 있는 사다리 계단', '광차와 침목 선로', '3개 갱도 입구', '연통 작업장과 광석 더미');
    },
  },
  {
    id: 'SpiralStair', name: '거목 나선 계단', category: '던전', file: 'SpiralStair.jpg',
    description: '나무 안을 두 바퀴 넘게 감아 오르는 계단과 정상의 황금 새 조각',
    width: 19, depth: 19, spawn: [0, 5.6], fog: '#b9bc90', sky: '#777b58',
    build(k) {
      k.floor(19, 19, '#827f57', { tile: 'stone' });
      k.cylinder(0, -.13, 0, 7.4, .26, '#a9a575', { segments: 40 });
      k.cylinder(0, 3.05, 0, 1.35, 6.1, '#75613b', { top: 1.02, segments: 16, solid: true });
      roots(k, 0, 0, 0, 1.25, 2.35, 10, .75, '#796139');
      for (let i = 0; i < 13; i++) {
        const a = i * TAU / 13;
        k.line([[Math.cos(a) * 1.31, .3, Math.sin(a) * 1.31], [Math.cos(a + .13) * 1.15, 3.1, Math.sin(a + .13) * 1.15], [Math.cos(a + .02) * 1.04, 6.1, Math.sin(a + .02) * 1.04]], i % 2 ? '#a28755' : '#4c432b', .031);
      }
      // One reusable annular tread geometry forms a continuous 2.2-turn route.
      const count = 120, rise = 6.6 / count, sweep = TAU * 2.2 / count, inner = 2.25, outer = 4.2;
      const vertices = [], indices = [], half = sweep * .54;
      for (const y of [-.14, 0]) for (const a of [-half, half]) for (const radius of [inner, outer]) vertices.push(Math.cos(a) * radius, y, Math.sin(a) * radius);
      indices.push(4, 5, 7, 4, 7, 6, 0, 2, 3, 0, 3, 1, 0, 1, 5, 0, 5, 4, 2, 6, 7, 2, 7, 3, 0, 4, 6, 0, 6, 2, 1, 3, 7, 1, 7, 5);
      const tread = new k.THREE.BufferGeometry(); tread.setAttribute('position', new k.THREE.Float32BufferAttribute(vertices, 3)); tread.setIndex(indices); tread.computeVertexNormals();
      const treads = [new k.THREE.InstancedMesh(tread, k.material('#b9a17a'), count / 2), new k.THREE.InstancedMesh(tread, k.material('#c4ad84'), count / 2)];
      const matrix = new k.THREE.Matrix4(), q = new k.THREE.Quaternion(), up = new k.THREE.Vector3(0, 1, 0);
      for (let i = 0; i < count; i++) {
        const a = Math.PI / 2 + (i + .5) * sweep, y = (i + 1) * rise;
        q.setFromAxisAngle(up, -a); matrix.compose(new k.THREE.Vector3(0, y, 0), q, new k.THREE.Vector3(1, 1, 1)); treads[i % 2].setMatrixAt(Math.floor(i / 2), matrix);
        const radius = (inner + outer) / 2, x = Math.cos(a) * radius, z = Math.sin(a) * radius;
        k.surface(x, z, outer - inner + .06, radius * sweep * 1.2, y, { rot: -a });
        // Dark radial joints make the individual treads legible at close range.
        if (i % 2 === 0) beam(k, [Math.cos(a - half) * inner, y + .005, Math.sin(a - half) * inner], [Math.cos(a - half) * outer, y + .005, Math.sin(a - half) * outer], .011, '#6c5941');
      }
      treads.forEach(m => { m.castShadow = true; m.receiveShadow = true; m.computeBoundingSphere(); k.root.add(m); });
      // Cutaway wooden shaft preserves the reference's hollow-tree interior.
      for (let i = 0; i < 24; i++) {
        const a = Math.PI + (i + .5) * Math.PI / 24, rr = 7.7;
        k.box(Math.cos(a) * rr, 4.8, Math.sin(a) * rr, .95, 9.6, .27, i % 3 ? '#9c9365' : '#b1a779', { rot: Math.PI / 2 - a, solid: true });
        beam(k, [Math.cos(a) * (rr - .17), .12, Math.sin(a) * (rr - .17)], [Math.cos(a + .015) * (rr - .17), 9.5, Math.sin(a + .015) * (rr - .17)], .015, '#786d4b');
      }
      for (const a of [Math.PI * 1.14, Math.PI * 1.5, Math.PI * 1.87]) {
        const x = Math.cos(a) * 7.45, z = Math.sin(a) * 7.45;
        door(k, x, 0, z, .92, 1.7, '#605a3d', Math.PI / 2 - a);
      }
      for (const a of [Math.PI * 1.2, Math.PI * 1.76]) {
        const x = Math.cos(a) * 7.4, z = Math.sin(a) * 7.4;
        k.box(x, 5.1, z, .67, 1.47, .05, '#68674b', { rot: Math.PI / 2 - a });
        for (let i = 0; i < 4; i++) k.box(x + Math.sin(a) * (i - 1.5) * .13, 5.1, z - Math.cos(a) * (i - 1.5) * .13, .022, 1.4, .07, '#aaa477', { rot: Math.PI / 2 - a });
      }
      k.cylinder(0, 6.44, 0, 6.5, .32, '#c4b37f', { segments: 48 });
      k.surface(0, 0, 10.4, 6.1, 6.6); k.surface(0, 0, 6.1, 10.4, 6.6);
      k.torus(0, 6.623, 0, 4.05, .055, '#907849');
      k.torus(0, 6.625, 0, 2.4, .065, '#6c6845');
      k.torus(0, 6.625, 0, 1.32, .065, '#5e6147');
      for (let i = 0; i < 24; i++) {
        const a = i * TAU / 24;
        beam(k, [Math.cos(a) * 2.46, 6.634, Math.sin(a) * 2.46], [Math.cos(a) * 3.99, 6.634, Math.sin(a) * 3.99], .022, '#e2d19c');
        if (i % 2 === 0) {
          const m = k.box(Math.cos(a) * 3.18, 6.62, Math.sin(a) * 3.18, 1.2, .026, .63, '#b78c56', { rot: -a });
          m.castShadow = false;
        }
      }
      k.cylinder(0, 6.79, 0, .8, .38, '#b5a772', { segments: 16 });
      k.cylinder(0, 7.07, 0, .58, .18, '#d8c38a', { segments: 16 });
      bird(k, 0, 7.17, 0, 1.35, '#d5b654');
      k.collide(0, 0, 1.7, 1.7, { y: 6.6, h: 2.6 });
      deck(k, -3.15, 7.5, -5.8, 2.8, 1.5, '#c1b082');
      stairsFrom(k, -3.15, -3.5, 2.0, 5, .18, .36, '#cbb98a', 6.6);
      door(k, -3.15, 7.5, -6.62, 1.0, 1.85, '#7c7350');
      const r = rng(203);
      for (let i = 0; i < 50; i++) {
        const a = r() * TAU, rr = 4.5 + r() * 2.3;
        k.sphere(Math.cos(a) * rr, .045, Math.sin(a) * rr, .17 + r() * .15, i % 2 ? '#beb995' : '#a3a685', [1.2, .17, .72]);
      }
      for (const [x, z] of [[-5, -3], [-6, 2], [5, -3], [4.5, 4]]) {
        shrub(k, x, 0, z, .58, '#718242');
        for (let j = 0; j < 4; j++) {
          k.cylinder(x + j * .15, .13, z + j * .08, .026, .23, '#ddd1a0', { segments: 5 });
          k.sphere(x + j * .15, .27, z + j * .08, .1, '#ac7951', [1, .5, 1]);
        }
      }
      hangingVines(k, -6.0, 4.6, -4.0, 1.3, 5);
      hangingVines(k, 5.4, 4.0, -4.7, 1.7, 6);
      k.interactions.push({ name: '황금 새 조각', position: [0, 8, 1.8], kind: 'inspect', text: '둥근 바닥 무늬 중앙에 날개를 펼친 황금빛 새가 놓여 있습니다.' }, { name: '나선 계단', position: [0, 1, 4], kind: 'inspect', text: '120개의 나무 계단을 따라 거목 안쪽을 두 바퀴 넘게 올라갈 수 있습니다.' });
      k.features.push('120개 실제 나선 계단', '2.2회전 연속 이동 경로', '거목 수피와 바닥 뿌리', '정상 원형 단상과 황금 새', '세 개의 아래층 문', '창살과 넝쿨, 버섯');
    },
  },
  {
    id: 'Underground', name: '지하 석조 통로', category: '던전', file: 'Underground.png',
    description: '꺾인 석벽과 닫힌 나무문, 통과 잡동사니가 놓인 긴 지하 통로',
    width: 38, depth: 18, spawn: [0, 5], fog: '#738582', sky: '#253230',
    build(k) {
      const outline = [[-18, -5.5], [-6, -5.5], [-6, 0], [6, 0], [6, -4.2], [18, -4.2], [18, 5.8], [6, 5.8], [6, 6.6], [-6, 6.6], [-6, 5.5], [-18, 5.5]];
      const shape = new k.THREE.Shape(); outline.forEach(([x, z], i) => i ? shape.lineTo(x, -z) : shape.moveTo(x, -z)); shape.closePath();
      const ground = mesh(k, new k.THREE.ShapeGeometry(shape), '#858974', { rot: [-Math.PI / 2, 0, 0], material: k.material('#ffffff', { map: k.pattern('stone', '#94967b', 36, 14) }) });
      ground.castShadow = false;
      k.surface(-12, 0, 12, 11, 0); k.surface(0, 3.3, 14, 6.6, 0); k.surface(12, .8, 12, 10, 0);
      masonry(k, -12, 0, -5.5, 12, 4.3, '#718782');
      masonry(k, -6, 0, -2.7, 5.6, 3.3, '#738883', Math.PI / 2);
      masonry(k, -3.9, 0, 0, 4.1, 3.3, '#798e85');
      masonry(k, 3.9, 0, 0, 4.1, 3.3, '#748b81');
      masonry(k, 6, 0, -2.1, 4.2, 3.3, '#718781', Math.PI / 2);
      masonry(k, 12, 0, -4.2, 12, 3.3, '#788b80');
      masonry(k, -18, 0, 0, 11, 4.3, '#758984', Math.PI / 2);
      masonry(k, 18, 0, .8, 10, 3.3, '#748980', Math.PI / 2);
      // Low front walls preserve a readable cutaway while keeping the corridors bounded.
      masonry(k, 0, 0, 6.65, 12, .65, '#879589');
      masonry(k, -12, 0, 5.55, 12, .65, '#89968c');
      masonry(k, 12, 0, 5.85, 12, .65, '#89968c');
      // Steps rise to the bare upper landing; game teleport symbols are omitted.
      deck(k, -15.3, 3.2, -4.15, 4.3, 2.7, '#7f8e82');
      stairsFrom(k, -15.3, 4.6, 3.2, 16, .2, .48, '#6a7770');
      for (let i = 0; i < 4; i++) k.box(-15.3, 3.21, -3.3 - i * .52, 4.23, .025, .025, '#46544b');
      door(k, -8.65, 0, -5.25, 1.25, 2.2, '#6e6c50');
      door(k, 10.2, 0, -3.96, 1.28, 2.2, '#706a4d');
      door(k, 16.2, 0, -3.96, 1.2, 2.2, '#776e53');
      // Centre stone arch has individual voussoirs over a closed half gate.
      for (const side of [-1, 1]) {
        k.box(side * 1.17, 1.05, -.035, .38, 2.1, .54, '#99a899', { solid: true });
        for (let i = 0; i < 5; i++) k.box(side * 1.17, .15 + i * .42, .254, .4, .025, .018, '#65736b');
      }
      for (let i = 0; i < 9; i++) {
        const a = i / 8 * Math.PI;
        const m = k.box(Math.cos(a) * 1.13, 2.06 + Math.sin(a) * .94, 0, .37, .45, .57, i % 2 ? '#9baa99' : '#819587');
        m.rotation.z = a - Math.PI / 2;
      }
      k.box(0, 1.27, -.16, 1.8, 2.45, .035, '#182825');
      k.box(0, .73, .02, 1.77, .98, .12, '#7f7958', { solid: true });
      for (let i = 0; i < 8; i++) k.box(-.78 + i * .22, .73, .095, .025, .95, .028, '#453f2c');
      k.box(0, 1.0, .11, 1.77, .045, .025, '#ada078');
      k.box(0, .49, .11, 1.77, .045, .025, '#ada078');
      k.box(.33, .79, .14, .065, .23, .08, '#312f23');
      // Barrel hoops, staves, a toppled cask, and the small work table.
      barrel(k, -11.3, 0, -4.4, 1.08);
      barrel(k, -10.3, 0, -4.4, .95);
      barrel(k, -6.55, 0, -.65, .78);
      barrel(k, 5.25, 0, 1.0, .88);
      const cask = k.cylinder(17.0, .39, 3.8, .37, .95, '#8b805f', { top: .34, segments: 12 }); cask.rotation.z = Math.PI / 2;
      for (const xx of [16.67, 17.33]) k.torus(xx, .39, 3.8, .36, .03, '#47534b', [0, Math.PI / 2, 0]);
      k.collide(17, 3.8, 1.0, .72, { y: 0, h: .8 });
      k.box(-12.5, .8, -1.4, 1.3, .12, .8, '#6a6950');
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) k.box(-12.5 + sx * .5, .37, -1.4 + sz * .28, .09, .74, .09, '#67634a');
      k.box(-12.5, .45, -.98, 1.1, .64, .05, '#68634a');
      k.collide(-12.5, -1.4, 1.3, .8, { y: 0, h: .86 });
      k.sphere(-12.8, 1.06, -1.35, .17, '#c5cbbb', [.8, 1.3, .8]);
      k.cylinder(-12.8, 1.29, -1.35, .058, .17, '#c5cbbb', { segments: 7 });
      k.torus(-12.35, .89, -1.35, .18, .028, '#b2a281');
      k.torus(-12.34, .92, -1.35, .13, .028, '#b2a281');
      // Dark cracks in the wall and scattered rubble near their bases.
      for (const [x, z] of [[-9.8, -5.22], [-4.1, .24], [4.9, .24], [8.8, -3.91], [17.7, -3.91]]) {
        k.line([[x, 2.3, z], [x + .12, 1.75, z], [x - .07, 1.18, z], [x + .16, .41, z]], '#334a3e', .032);
        for (let i = 0; i < 9; i++) rock(k, x + Math.sin(i * 4) * .3, 0, z + .24 + Math.cos(i * 3) * .25, .095 + (i % 3) * .055, i % 2 ? '#727f6d' : '#536659');
      }
      const r = rng(89);
      for (let i = 0; i < 100; i++) {
        const x = -17 + r() * 34, z = 1 + r() * 4.4;
        k.sphere(x, .032, z, [.24, .3, .36][i % 3], i % 2 ? '#a2a58c' : '#bdbea2', [1.3, .095, .8]);
      }
      k.interactions.push({ name: '닫힌 석조 아치문', position: [0, 1.2, 1.15], kind: 'inspect', text: '아치 돌 사이에는 검은 통로와 낡은 나무 반문이 놓여 있습니다.' }, { name: '작업대', position: [-12.5, 1.0, -.4], kind: 'inspect', text: '흰 물병과 둥글게 감은 밧줄, 먼지 낀 나무 작업대입니다.' }, { name: '나무문', position: [10.2, 1.1, -2.8], kind: 'inspect', text: '문틀과 세로 널판, 작은 금속 손잡이가 달린 오래된 문입니다.' });
      k.features.push('꺾인 3개 석조 통로', '낱개 벽돌과 바닥 포석', '16단 계단과 위쪽 착지점', '반문이 있는 돌 아치', '나무문 3개와 장식 문틀', '오크통, 균열과 잔해, 작업대');
    },
  },
];
