// Navigation uses metres and a vertical character capsule. Static scene bounds
// are indexed once; repeated movement and camera queries use local candidates.
const CELL_SIZE = 3;
const FOOT_SKIN = .015;
const EPSILON = 1e-7;
const EMPTY = Object.freeze([]);
const indexes = new WeakMap();
const transforms = new WeakMap();

function compile(rect) {
  const rot = rect.rot || 0, c = Math.cos(rot), s = Math.sin(rot);
  const hw = Math.abs(rect.w) / 2, hd = Math.abs(rect.d) / 2;
  const ex = rect.shape === 'circle' ? hw : Math.abs(c) * hw + Math.abs(s) * hd;
  const ez = rect.shape === 'circle' ? hw : Math.abs(s) * hw + Math.abs(c) * hd;
  return { rect, x: rect.x, z: rect.z, w: rect.w, d: rect.d, rot, c, s, hw, hd,
    minX: rect.x - ex, maxX: rect.x + ex, minZ: rect.z - ez, maxZ: rect.z + ez, stamp: 0 };
}

function transform(rect) {
  let t = transforms.get(rect);
  if (!t || t.x !== rect.x || t.z !== rect.z || t.w !== rect.w || t.d !== rect.d || t.rot !== (rect.rot || 0)) {
    t = compile(rect); transforms.set(rect, t);
  }
  return t;
}

function buildIndex(rectangles) {
  const entries = rectangles.map(compile), cells = new Map(), broad = [];
  const index = { length: rectangles.length, entries, cells, broad, stamp: 0 };
  if (entries.length <= 16) { indexes.set(rectangles, index); return index; }
  for (const entry of entries) {
    const minX = Math.floor(entry.minX / CELL_SIZE), maxX = Math.floor(entry.maxX / CELL_SIZE);
    const minZ = Math.floor(entry.minZ / CELL_SIZE), maxZ = Math.floor(entry.maxZ / CELL_SIZE);
    if ((maxX - minX + 1) * (maxZ - minZ + 1) > 4096) { broad.push(entry); continue; }
    for (let x = minX; x <= maxX; x++) {
      let column = cells.get(x); if (!column) { column = new Map(); cells.set(x, column); }
      for (let z = minZ; z <= maxZ; z++) {
        let bucket = column.get(z); if (!bucket) { bucket = []; column.set(z, bucket); }
        bucket.push(entry);
      }
    }
  }
  indexes.set(rectangles, index); return index;
}

function getIndex(rectangles) {
  const index = indexes.get(rectangles);
  return index && index.length === rectangles.length ? index : buildIndex(rectangles);
}

function candidates(rectangles, x, z, radius = 0) {
  const index = getIndex(rectangles);
  if (index.entries.length <= 16) return index.entries;
  const minX = Math.floor((x - radius) / CELL_SIZE), maxX = Math.floor((x + radius) / CELL_SIZE);
  const minZ = Math.floor((z - radius) / CELL_SIZE), maxZ = Math.floor((z + radius) / CELL_SIZE);
  if (minX === maxX && minZ === maxZ && !index.broad.length) return index.cells.get(minX)?.get(minZ) || EMPTY;
  const result = [], stamp = ++index.stamp;
  for (const entry of index.broad) { entry.stamp = stamp; result.push(entry); }
  for (let ix = minX; ix <= maxX; ix++) {
    const column = index.cells.get(ix); if (!column) continue;
    for (let iz = minZ; iz <= maxZ; iz++) {
      const bucket = column.get(iz); if (!bucket) continue;
      for (const entry of bucket) if (entry.stamp !== stamp) { entry.stamp = stamp; result.push(entry); }
    }
  }
  return result;
}

function pointInside(x, z, t, radius = 0) {
  const dx = x - t.x, dz = z - t.z;
  return Math.abs(dx * t.c - dz * t.s) <= t.hw + radius + EPSILON &&
    Math.abs(dx * t.s + dz * t.c) <= t.hd + radius + EPSILON;
}

function circleOverlaps(x, z, t, radius) {
  if (x + radius < t.minX || x - radius > t.maxX || z + radius < t.minZ || z - radius > t.maxZ) return false;
  const dx = x - t.x, dz = z - t.z;
  if (t.rect.shape === 'circle') return dx * dx + dz * dz <= (t.hw + radius) ** 2 + EPSILON;
  const lx = dx * t.c - dz * t.s, lz = dx * t.s + dz * t.c;
  const ox = Math.max(0, Math.abs(lx) - t.hw), oz = Math.max(0, Math.abs(lz) - t.hd);
  return ox * ox + oz * oz <= radius * radius + EPSILON;
}

function verticalOverlap(rect, y, height, skin, headSkin = skin) {
  return rect.y + rect.h > y + skin && rect.y < y + height - headSkin;
}

function bodyBlocked(colliders, x, z, y, radius, height, skin = FOOT_SKIN, headSkin = skin) {
  for (const t of candidates(colliders, x, z, radius)) {
    if (verticalOverlap(t.rect, y, height, skin, headSkin) && circleOverlaps(x, z, t, radius)) return true;
  }
  return false;
}

function surfaceAt(surfaces, x, z, currentY, stepHeight, radius = 0) {
  let result = null;
  for (const t of candidates(surfaces, x, z, radius)) {
    const y = t.rect.y;
    if (y > currentY + stepHeight + EPSILON || (result !== null && y <= result)) continue;
    if (radius ? circleOverlaps(x, z, t, radius) : pointInside(x, z, t)) result = y;
  }
  return result;
}

function supportAt(world, x, z, y, stepHeight, radius) {
  let result = surfaceAt(world.surfaces, x, z, y, stepHeight, radius);
  // Solid tops catch falls even if no decorative top surface was registered.
  for (const t of candidates(world.colliders, x, z, radius)) {
    if (t.rect.support === false) continue;
    const top = t.rect.y + t.rect.h;
    if (top > y + stepHeight + EPSILON || (result !== null && top <= result)) continue;
    if (circleOverlaps(x, z, t, radius)) result = top;
  }
  return result;
}

function forbiddenVolume(world, x, z, y, radius) {
  for (const t of candidates(world.colliders, x, z, radius)) {
    if (t.rect.support !== false || !circleOverlaps(x, z, t, radius)) continue;
    const floor = surfaceAt(world.surfaces, x, z, y, .025, radius * .6);
    if (floor === null || floor < t.rect.y + t.rect.h - FOOT_SKIN) return true;
  }
  return false;
}

export function prepareNavigation(world) {
  buildIndex(world.surfaces); buildIndex(world.colliders);
  if (world.cameraColliders) buildIndex(world.cameraColliders);
  return world;
}

export function insideRect(x, z, rect, radius = 0) { return pointInside(x, z, transform(rect), radius); }

export function floorAt(surfaces, x, z, currentY = Infinity, stepHeight = .38) {
  return surfaceAt(surfaces, x, z, currentY, stepHeight);
}

export function blocked(colliders, x, z, y, radius = .22, height = 1.4) {
  return bodyBlocked(colliders, x, z, y, radius, height, .08, 0);
}

// Compatibility for the original navigation API and existing movement checks.
export function moveWithCollisions(world, position, dx, dz, radius = .22) {
  const count = Math.max(1, Math.ceil(Math.hypot(dx, dz) / .08));
  const sx = dx / count, sz = dz / count;
  for (let i = 0; i < count; i++) {
    for (let axis = 0; axis < 2; axis++) {
      const x = position.x + (axis === 0 ? sx : 0), z = position.z + (axis === 1 ? sz : 0);
      if (Math.abs(x) > world.width / 2 - radius || Math.abs(z) > world.depth / 2 - radius) continue;
      const nextFloor = floorAt(world.surfaces, x, z, position.y);
      if (nextFloor === null) continue;
      const collisionY = Math.max(position.y, nextFloor);
      if (!blocked(world.colliders, x, z, collisionY, radius)) {
        position.x = x; position.z = z;
        if (nextFloor > position.y) position.y = nextFloor;
      }
    }
  }
  return position;
}

export function createPhysicsState() {
  return { velocityY: 0, grounded: true, jumpHeld: false, lastSafe: null, world: null };
}

function recoverEmbedded(world, p, state, radius, height) {
  if (!bodyBlocked(world.colliders, p.x, p.z, p.y, radius, height)) return;
  const previous = state.lastSafe;
  if (previous && !bodyBlocked(world.colliders, previous.x, previous.z, previous.y, radius, height)) {
    p.x = previous.x; p.y = previous.y; p.z = previous.z; state.velocityY = 0; return;
  }
  for (let attempt = 0; attempt < 8; attempt++) {
    let changed = false;
    for (const t of candidates(world.colliders, p.x, p.z, radius)) {
      if (!verticalOverlap(t.rect, p.y, height, FOOT_SKIN) || !circleOverlaps(p.x, p.z, t, radius)) continue;
      const dx = p.x - t.x, dz = p.z - t.z;
      let mx, mz;
      if (t.rect.shape === 'circle') {
        const distance = Math.hypot(dx, dz), push = t.hw + radius - distance + .002;
        mx = distance > EPSILON ? dx / distance * push : push; mz = distance > EPSILON ? dz / distance * push : 0;
      } else {
        const lx = dx * t.c - dz * t.s, lz = dx * t.s + dz * t.c;
        const nearX = Math.max(-t.hw, Math.min(t.hw, lx)), nearZ = Math.max(-t.hd, Math.min(t.hd, lz));
        let localX = lx - nearX, localZ = lz - nearZ;
        const distance = Math.hypot(localX, localZ);
        if (distance > EPSILON) { const push = (radius - distance + .002) / distance; localX *= push; localZ *= push; }
        else if (t.hw + radius - Math.abs(lx) < t.hd + radius - Math.abs(lz)) { localX = (lx >= 0 ? 1 : -1) * (t.hw + radius - Math.abs(lx) + .002); localZ = 0; }
        else { localX = 0; localZ = (lz >= 0 ? 1 : -1) * (t.hd + radius - Math.abs(lz) + .002); }
        mx = t.c * localX + t.s * localZ; mz = -t.s * localX + t.c * localZ;
      }
      p.x = Math.max(-world.width / 2 + radius, Math.min(world.width / 2 - radius, p.x + mx));
      p.z = Math.max(-world.depth / 2 + radius, Math.min(world.depth / 2 - radius, p.z + mz));
      changed = true;
    }
    if (!changed || !bodyBlocked(world.colliders, p.x, p.z, p.y, radius, height)) break;
  }
  state.velocityY = 0;
}

function sweepVertical(world, p, nextY, radius, height) {
  if (nextY > p.y) {
    let ceiling = Infinity;
    const oldHead = p.y + height, nextHead = nextY + height;
    for (const t of candidates(world.colliders, p.x, p.z, radius)) {
      const bottom = t.rect.y;
      if (bottom >= oldHead - FOOT_SKIN && bottom <= nextHead + FOOT_SKIN && circleOverlaps(p.x, p.z, t, radius)) ceiling = Math.min(ceiling, bottom);
    }
    return ceiling < Infinity ? { y: ceiling - height - .002, ceiling: true, landed: false } : { y: nextY, ceiling: false, landed: false };
  }
  const floor = supportAt(world, p.x, p.z, p.y, FOOT_SKIN, radius * .6);
  if (floor !== null && floor >= nextY - FOOT_SKIN) return { y: floor, ceiling: false, landed: true };
  return { y: nextY, ceiling: false, landed: false };
}

/**
 * Advance one character frame. dx/dz are intended displacement in world space;
 * jump is the current button/key state (holding it cannot repeatedly jump).
 * position and physics are mutable; physics is returned for convenience.
 */
export function stepCharacter(world, position, physics, dx, dz, dt, {
  jump = false, radius = .22, height = 1.5, stepHeight = .38, gravity = 18, jumpSpeed = 5.6,
} = {}) {
  if (!Number.isFinite(dt) || dt < 0) return physics;
  dt = Math.min(dt, .1);
  if (physics.world !== world) { physics.world = world; physics.lastSafe = null; }
  recoverEmbedded(world, position, physics, radius, height);
  // Ground support reaches the same toe boundary as horizontal collision.
  // Otherwise a raised slab blocks the capsule before its support is visible.
  const footRadius = radius;
  let support = supportAt(world, position.x, position.z, position.y, .025, footRadius);
  if (physics.velocityY <= 0 && support !== null && Math.abs(position.y - support) <= .05) {
    position.y = support; physics.grounded = true; physics.velocityY = 0;
  } else if (support === null || position.y - support > .05) physics.grounded = false;
  if (jump && !physics.jumpHeld && physics.grounded) { physics.velocityY = jumpSpeed; physics.grounded = false; }
  physics.jumpHeld = !!jump;
  const verticalTravel = Math.abs(physics.velocityY) * dt + gravity * dt * dt / 2;
  const count = Math.max(1, Math.ceil(Math.max(Math.hypot(dx, dz) / .08, verticalTravel / .08, dt / .012)));
  const sx = dx / count, sz = dz / count, time = dt / count;
  for (let i = 0; i < count; i++) {
    for (let axis = 0; axis < 2; axis++) {
      const x = position.x + (axis === 0 ? sx : 0), z = position.z + (axis === 1 ? sz : 0);
      if (Math.abs(x) > world.width / 2 - radius || Math.abs(z) > world.depth / 2 - radius) continue;
      let nextY = position.y;
      if (physics.grounded) {
        const nextFloor = supportAt(world, x, z, position.y, stepHeight, footRadius);
        if (nextFloor === null) continue;
        if (nextFloor > nextY) nextY = nextFloor;
        if (nextY - position.y > stepHeight + EPSILON) continue;
      }
      if (forbiddenVolume(world, x, z, nextY, radius)) continue;
      if (bodyBlocked(world.colliders, x, z, nextY, radius, height)) continue;
      if (nextY > position.y) {
        const oldX = position.x, oldZ = position.z; position.x = x; position.z = z;
        const rise = sweepVertical(world, position, nextY, radius, height);
        position.x = oldX; position.z = oldZ;
        if (rise.ceiling) continue;
      }
      position.x = x; position.z = z; position.y = nextY;
    }
    if (physics.grounded) {
      support = supportAt(world, position.x, position.z, position.y, .025, footRadius);
      if (support !== null && position.y - support <= stepHeight + EPSILON) { position.y = support; physics.velocityY = 0; }
      else { physics.grounded = false; physics.velocityY = 0; }
    }
    if (!physics.grounded) {
      physics.velocityY = Math.max(-22, physics.velocityY - gravity * time);
      const vertical = sweepVertical(world, position, position.y + physics.velocityY * time, radius, height);
      position.y = vertical.y;
      if (vertical.ceiling) physics.velocityY = 0;
      if (vertical.landed) { physics.velocityY = 0; physics.grounded = true; }
    }
  }
  if (!bodyBlocked(world.colliders, position.x, position.z, position.y, radius, height)) {
    const safe = physics.lastSafe ||= { x: 0, y: 0, z: 0 };
    safe.x = position.x; safe.y = position.y; safe.z = position.z;
  }
  return physics;
}
