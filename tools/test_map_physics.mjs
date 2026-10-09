import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { insideRect, floorAt, blocked, prepareNavigation, createPhysicsState, stepCharacter } from '../map-viewer/navigation.js';

const floor = { x: 0, z: 0, w: 30, d: 30, y: 0 };
const makeWorld = (colliders = [], surfaces = [floor]) => prepareNavigation({ width: 30, depth: 30, colliders, surfaces });
const advance = (world, p, state, frames, { dx = 0, dz = 0, jump = false, dt = 1 / 60 } = {}) => {
  let peak = p.y;
  for (let i = 0; i < frames; i++) {
    stepCharacter(world, p, state, dx, dz, dt, { jump }); peak = Math.max(peak, p.y);
    assert.equal(blocked(world.colliders, p.x, p.z, p.y), false, 'No completed frame may leave the capsule embedded');
  }
  return peak;
};

// Compare indexed queries with an independent linear reference over many
// rotated rectangles, including exact cell boundaries and circular pillars.
let seed = 18791;
const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
const rectangles = Array.from({ length: 1200 }, (_, i) => ({
  x: (random() - .5) * 150, z: (random() - .5) * 150,
  w: .1 + random() * 4, d: .1 + random() * 4, rot: random() * Math.PI * 2,
  y: random() * 5, h: .2 + random() * 5, ...(i % 17 ? {} : { shape: 'circle' }),
}));
const surfaces = rectangles.map(({ x, z, w, d, rot, y }) => ({ x, z, w, d, rot, y }));
prepareNavigation({ colliders: rectangles, surfaces });
function referenceBlocked(x, z, y, radius = .22, height = 1.4) {
  return rectangles.some(rect => {
    if (rect.y + rect.h <= y + .08 || rect.y >= y + height) return false;
    const dx = x - rect.x, dz = z - rect.z;
    if (rect.shape === 'circle') return dx * dx + dz * dz <= (Math.abs(rect.w) / 2 + radius) ** 2 + 1e-7;
    const lx = dx * Math.cos(rect.rot) - dz * Math.sin(rect.rot), lz = dx * Math.sin(rect.rot) + dz * Math.cos(rect.rot);
    const ox = Math.max(0, Math.abs(lx) - rect.w / 2), oz = Math.max(0, Math.abs(lz) - rect.d / 2);
    return ox * ox + oz * oz <= radius * radius + 1e-7;
  });
}
const queries = [];
for (let i = 0; i < 1500; i++) {
  const x = i % 7 ? (random() - .5) * 155 : Math.floor(random() * 50 - 25) * 3;
  const z = i % 11 ? (random() - .5) * 155 : Math.floor(random() * 50 - 25) * 3;
  const y = random() * 6;
  let expected = null;
  for (const rect of surfaces) if (rect.y <= y + .38 && insideRect(x, z, rect) && (expected === null || rect.y > expected)) expected = rect.y;
  assert.equal(floorAt(surfaces, x, z, y), expected, 'Spatial floor index must match the linear reference');
  assert.equal(blocked(rectangles, x, z, y), referenceBlocked(x, z, y), 'Spatial collider index must include all rotated/circle candidates');
  queries.push([x, z, y]);
}
const circle = [{ x: 0, z: 0, w: 2, d: 2, y: 0, h: 3, shape: 'circle' }];
assert.equal(blocked(circle, 1, 1, 0), false, 'Round columns have clear square corners');
assert.equal(blocked(circle, 1.1, 0, 0), true);
assert.equal(blocked([{ ...circle[0], shape: undefined }], 1.2, 1.2, 0), false, 'Capsule/box corners use true circle distance');

// A jump rises and lands consistently, holding the button never auto-repeats.
const empty = makeWorld();
const p = { x: 0, y: 0, z: 0 }, state = createPhysicsState();
const peak = advance(empty, p, state, 90, { jump: true });
assert.ok(peak > .75 && peak < .92, `Jump peak ${peak}`);
assert.equal(p.y, 0); assert.equal(state.grounded, true);
advance(empty, p, state, 1, { jump: false });
advance(empty, p, state, 1, { jump: true }); assert.ok(p.y > .05, 'Releasing then pressing permits a new jump');

// Upward motion stops below a real ceiling, including long frame intervals.
const ceilingWorld = makeWorld([{ x: 0, z: 0, w: 8, d: 8, y: 1.7, h: .15 }]);
const low = { x: 0, y: 0, z: 0 }, lowState = createPhysicsState();
const lowPeak = advance(ceilingWorld, low, lowState, 30, { dt: .05, jump: true });
assert.ok(lowPeak <= .20001 && lowPeak > .1); assert.equal(low.y, 0);

// Horizontal movement cannot tunnel through thin or rotated building walls,
// even while airborne or during a large requested displacement.
const wallWorld = makeWorld([{ x: 0, z: 0, w: .025, d: 15, y: 0, h: 5 }]);
const runner = { x: -2, y: 0, z: 0 }, runnerState = createPhysicsState();
stepCharacter(wallWorld, runner, runnerState, 8, 0, .1, { jump: true });
assert.ok(runner.x < -.22, `Thin-wall crossing: ${runner.x}`);
advance(wallWorld, runner, runnerState, 30, { dx: .2 }); assert.ok(runner.x < -.22);
const rotatedWorld = makeWorld([{ x: 0, z: 0, w: 6, d: .03, rot: Math.PI / 4, y: 0, h: 5 }]);
const angled = { x: -Math.SQRT2, y: 0, z: -Math.SQRT2 }, angledState = createPhysicsState();
stepCharacter(rotatedWorld, angled, angledState, Math.SQRT2 * 2, Math.SQRT2 * 2, .1);
assert.ok((angled.x + angled.z) / Math.SQRT2 < -.21, 'Rotated wall remains solid');

// Falling capsules land on solid tops instead of penetrating large bodies.
const crateWorld = makeWorld([{ x: 0, z: 0, w: 3, d: 3, y: 0, h: 1.2 }]);
const falling = { x: 0, y: 10, z: 0 }, fallingState = createPhysicsState(); fallingState.velocityY = -30;
advance(crateWorld, falling, fallingState, 12, { dt: .1 });
assert.equal(falling.y, 1.2); assert.equal(fallingState.grounded, true);

// Airborne motion never adopts a nearby upper floor as a stair step.
const ledgeWorld = makeWorld([], [floor, { x: 0, z: 0, w: 2, d: 2, y: .8 }]);
const airborne = { x: -1.2, y: .5, z: 0 }, airborneState = createPhysicsState();
airborneState.velocityY = 1; airborneState.grounded = false;
stepCharacter(ledgeWorld, airborne, airborneState, .4, 0, 1 / 60);
assert.ok(airborne.y < .6, 'Jumping past a platform cannot snap upward to it');

// Ground stairs can ascend/descend; deliberate jumping can bridge a floor gap.
const stairWorld = makeWorld([], [floor, ...Array.from({ length: 8 }, (_, i) => ({ x: 0, z: 2.6 - i * .4, w: 2, d: .42, y: (i + 1) * .2 }))]);
const stairs = { x: 0, y: 0, z: 3 }, stairState = createPhysicsState();
advance(stairWorld, stairs, stairState, 55, { dz: -.06 }); assert.ok(stairs.y >= 1.4);
advance(stairWorld, stairs, stairState, 57, { dz: .06 }); assert.equal(stairs.y, 0);
const stepWorld = makeWorld([{ x: 1, z: 0, w: 2, d: 2, y: 0, h: .36 }], [floor, { x: 1, z: 0, w: 2, d: 2, y: .36 }]);
const edge = { x: -.8, y: 0, z: 0 }, edgeState = createPhysicsState();
advance(stepWorld, edge, edgeState, 40, { dx: .04 });
assert.ok(edge.x > .7 && edge.y === .36, 'Capsule toe support permits a legal raised step before its side blocks movement');
const gapWorld = makeWorld([], [{ x: -2, z: 0, w: 3, d: 8, y: 0 }, { x: 2, z: 0, w: 3, d: 8, y: 0 }]);
const jumper = { x: -.65, y: 0, z: 0 }, gapState = createPhysicsState();
stepCharacter(gapWorld, jumper, gapState, .04, 0, 1 / 60, { jump: true });
advance(gapWorld, jumper, gapState, 59, { dx: .04 });
assert.ok(jumper.x > 1 && gapState.grounded && jumper.y === 0, 'A jump can cross a registered floor gap');

// Logical water volumes remain impassable, while elevated bridges still work.
const water = { x: 0, z: 0, w: 2, d: 8, y: -3, h: 3.3, support: false };
const waterWorld = makeWorld([water]);
const bank = { x: -1.4, y: 0, z: 0 }, bankState = createPhysicsState();
advance(waterWorld, bank, bankState, 50, { dx: .06, jump: true }); assert.ok(bank.x < -1.2);
const bridgeWorld = makeWorld([water], [floor, { x: 0, z: 0, w: 5, d: 2, y: .8 }]);
const crossing = { x: -1.4, y: .8, z: 0 }, crossingState = createPhysicsState();
advance(bridgeWorld, crossing, crossingState, 45, { dx: .06 }); assert.ok(crossing.x > 1.2 && crossing.y === .8);

// Embedded starts recover to a nearby free point; changed maps rebuild indexes.
const embeddedWorld = makeWorld([{ x: 0, z: 0, w: 2, d: 2, y: 0, h: 3, rot: .43 }]);
const embedded = { x: 0, y: 0, z: 0 }; stepCharacter(embeddedWorld, embedded, createPhysicsState(), 0, 0, 1 / 60);
assert.equal(blocked(embeddedWorld.colliders, embedded.x, embedded.z, embedded.y), false);
assert.ok(Math.hypot(embedded.x, embedded.z) < 1.5, 'Recovery uses the nearest boundary');
rectangles[0].x = 200; rectangles[0].z = 200; prepareNavigation({ colliders: rectangles, surfaces });
assert.equal(blocked(rectangles, 200, 200, rectangles[0].y), true, 'Explicit preparation refreshes modified bounds');

// Report deterministic-query timing without a hardware-dependent test threshold.
for (let i = 0; i < 3000; i++) blocked(rectangles, ...queries[i % queries.length]);
const start = performance.now(); for (let i = 0; i < 30000; i++) blocked(rectangles, ...queries[i % queries.length]);
const indexedMs = performance.now() - start;
const slowStart = performance.now(); for (let i = 0; i < 30000; i++) referenceBlocked(...queries[i % queries.length]);
const referenceMs = performance.now() - slowStart;
console.log(`PASS: indexed/linear equivalence, circular bounds, jumps, ceilings, walls, falls, stairs, gaps, water, recovery (${indexedMs.toFixed(1)} ms indexed / ${referenceMs.toFixed(1)} ms linear; jump peak ${peak.toFixed(3)} m)`);
