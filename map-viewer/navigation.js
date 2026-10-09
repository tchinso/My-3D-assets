// World coordinates use metres. Collision operates on the character's feet.
export function insideRect(x, z, rect, radius = 0) {
  const a = rect.rot || 0, dx = x - rect.x, dz = z - rect.z;
  const lx = dx * Math.cos(a) - dz * Math.sin(a);
  const lz = dx * Math.sin(a) + dz * Math.cos(a);
  return Math.abs(lx) <= rect.w / 2 + radius && Math.abs(lz) <= rect.d / 2 + radius;
}

export function floorAt(surfaces, x, z, currentY = Infinity, stepHeight = .38) {
  let result = null;
  for (const surface of surfaces) {
    if (surface.y <= currentY + stepHeight && insideRect(x, z, surface) &&
        (result === null || surface.y > result)) result = surface.y;
  }
  return result;
}

export function blocked(colliders, x, z, y, radius = .22, height = 1.4) {
  return colliders.some(rect => {
    if (rect.y + rect.h <= y + .08 || rect.y >= y + height) return false;
    return insideRect(x, z, rect, radius);
  });
}

export function moveWithCollisions(world, position, dx, dz, radius = .22) {
  const maxStep = .12, count = Math.max(1, Math.ceil(Math.hypot(dx, dz) / maxStep));
  for (let i = 0; i < count; i++) {
    for (const [axis, delta] of [['x', dx / count], ['z', dz / count]]) {
      const x = position.x + (axis === 'x' ? delta : 0);
      const z = position.z + (axis === 'z' ? delta : 0);
      if (Math.abs(x) > world.width / 2 - radius || Math.abs(z) > world.depth / 2 - radius) continue;
      const nextFloor = floorAt(world.surfaces, x, z, position.y);
      // Map edges, pools and gaps are impassable without a registered bridge.
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
