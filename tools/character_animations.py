"""Procedural, portable glTF character animations (NumPy is the only dependency).

``add_animations(doc, append_accessor, character_id, attack_style='magic')``
replaces ``doc['animations']`` with Idle, Walk, Run, Attack, Defend, Victory and
Lose. The callback
must append the supplied NumPy array to the GLB buffer and return its accessor
index: ``append_accessor(array, gltf_type, component_type=5126)``. Floats are
little-endian float32; animation time accessors need their usual min/max values.

``add_donor_animations`` can then replace Idle/Walk/Victory with explicitly
mapped native donor tracks, preserving synchronized body and cloth motion.

The body skin is selected from skinned mesh vertex counts, so duplicate weapon
skeletons are excluded. Named Bip001 joints and their skeleton root are used;
custom HairAccessory nodes below the same skeleton are also supported. Rotations
are relative to the actual rest hierarchy and use anatomical world axes. Walk
uses two-bone leg IK, toe-off and counter-swinging arms. All clips are in place.
Idle/Walk/Run have identical first/last keys; Attack/Defend/Victory return to the
rest pose. Lose settles into and holds a defeated pose until its final key.

No filesystem access or mutation occurs on import. Source visibility/expression
tracks are discarded and no scale, morph, material or visibility is animated.
This provides stylized gestures, not motion capture or physics. Soft garments
follow their skin, and accessory sway is procedural rather than simulated.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Callable

import numpy as np


_IDENTITY = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
_EPS = 1e-10


def _unit(v, fallback=None):
    v = np.asarray(v, dtype=np.float64)
    norm = np.linalg.norm(v)
    if norm > _EPS:
        return v / norm
    return np.asarray(fallback if fallback is not None else [1, 0, 0], dtype=np.float64)


def _qnorm(q):
    q = np.asarray(q, dtype=np.float64)
    norm = np.linalg.norm(q)
    return q / norm if norm > _EPS else _IDENTITY.copy()


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def _qinv(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])


def _qrot(q, v):
    xyz = q[:3]
    return v + 2.0 * np.cross(xyz, np.cross(xyz, v) + q[3] * v)


def _axisq(axis, degrees):
    half = math.radians(float(degrees)) * 0.5
    return np.r_[_unit(axis) * math.sin(half), math.cos(half)]


def _alignq(a, b):
    a, b = _unit(a), _unit(b)
    dot = float(np.clip(np.dot(a, b), -1, 1))
    if dot < -0.999999:
        orthogonal = np.array([1., 0., 0.]) if abs(a[0]) < .8 else np.array([0., 1., 0.])
        return np.r_[_unit(np.cross(a, orthogonal)), 0.]
    return _qnorm(np.r_[np.cross(a, b), 1 + dot])


def _qmatrix(q):
    x, y, z, w = q
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ])


def _matrixq(m):
    # Largest diagonal method remains stable close to half-turn rest rotations.
    values = np.array([1+m[0, 0]-m[1, 1]-m[2, 2],
                       1-m[0, 0]+m[1, 1]-m[2, 2],
                       1-m[0, 0]-m[1, 1]+m[2, 2],
                       1+np.trace(m)])
    largest = int(np.argmax(values))
    value = .5 * math.sqrt(max(0., values[largest]))
    factor = .25 / max(value, _EPS)
    if largest == 0:
        q = [value, (m[0, 1]+m[1, 0])*factor, (m[0, 2]+m[2, 0])*factor, (m[2, 1]-m[1, 2])*factor]
    elif largest == 1:
        q = [(m[0, 1]+m[1, 0])*factor, value, (m[1, 2]+m[2, 1])*factor, (m[0, 2]-m[2, 0])*factor]
    elif largest == 2:
        q = [(m[0, 2]+m[2, 0])*factor, (m[1, 2]+m[2, 1])*factor, value, (m[1, 0]-m[0, 1])*factor]
    else:
        q = [(m[2, 1]-m[1, 2])*factor, (m[0, 2]-m[2, 0])*factor, (m[1, 0]-m[0, 1])*factor, value]
    return _qnorm(q)


def _trs(node):
    if 'matrix' not in node:
        return (np.asarray(node.get('translation', [0, 0, 0]), dtype=float),
                _qnorm(node.get('rotation', _IDENTITY)),
                np.asarray(node.get('scale', [1, 1, 1]), dtype=float))
    matrix = np.asarray(node['matrix'], dtype=float).reshape(4, 4).T
    scale = np.linalg.norm(matrix[:3, :3], axis=0)
    rotation = matrix[:3, :3] / np.maximum(scale, _EPS)
    if np.linalg.det(rotation) < 0:
        scale[0] *= -1
        rotation[:, 0] *= -1
    return matrix[:3, 3].copy(), _matrixq(rotation), scale


def _body_skin(doc):
    scores = defaultdict(int)
    accessors = doc.get('accessors', [])
    for node in doc['nodes']:
        if 'skin' not in node or 'mesh' not in node:
            continue
        for primitive in doc['meshes'][node['mesh']].get('primitives', []):
            attrs = primitive.get('attributes', {})
            if 'JOINTS_0' in attrs and 'WEIGHTS_0' in attrs:
                position = attrs.get('POSITION')
                scores[node['skin']] += int(accessors[position]['count']) if position is not None else 1
    skins = doc.get('skins', [])
    if not skins:
        raise ValueError('Character animations require a skinned Bip001 skeleton.')
    return max(range(len(skins)), key=lambda i: (scores[i], len(skins[i].get('joints', []))))


class _Rig:
    def __init__(self, doc):
        self.doc = doc
        self.nodes = doc['nodes']
        count = len(self.nodes)
        self.parent = np.full(count, -1, dtype=int)
        for i, node in enumerate(self.nodes):
            for child in node.get('children', []):
                self.parent[child] = i
        self.order = []

        def visit(i):
            self.order.append(i)
            for child in self.nodes[i].get('children', []):
                visit(child)

        for i in range(count):
            if self.parent[i] < 0:
                visit(i)
        if len(self.order) != count:
            raise ValueError('Character node hierarchy must be an acyclic tree.')
        depths = np.zeros(count, dtype=int)
        for i in self.order:
            if self.parent[i] >= 0:
                depths[i] = depths[self.parent[i]]+1
        self.levels = [np.flatnonzero(depths == depth) for depth in range(int(depths.max())+1)]
        self.t, self.q, self.s = map(np.stack, zip(*(_trs(n) for n in self.nodes)))
        self.skin = _body_skin(doc)
        joints = set(doc['skins'][self.skin].get('joints', []))
        candidates = set(joints)
        for joint in list(joints):
            ancestor = int(self.parent[joint])
            while ancestor >= 0:
                if self.nodes[ancestor].get('name') == 'Bip001':
                    candidates.add(ancestor)
                ancestor = int(self.parent[ancestor])
        self.bones = {}
        for i in sorted(candidates):
            name = self.nodes[i].get('name', '')
            if name.startswith('Bip001'):
                # Exact names in the main skin take precedence over any suffix.
                self.bones.setdefault(name, i)
        self.root = self.bones.get('Bip001', self.bones.get('Bip001 Pelvis'))
        # Some detailed costumes weight hands to the forearm or use a separate
        # skin for hair. Keep unweighted anatomical end-effectors in this same
        # Bip001 branch, while excluding other/weapon skeleton roots.
        def anatomical_descendants(i):
            if self.nodes[i].get('name', '').startswith('Bip001_Weapon'):
                return
            name = self.nodes[i].get('name', '')
            if name == 'Bip001' or name.startswith('Bip001 '):
                candidates.add(i)
                self.bones.setdefault(name, i)
            for child in self.nodes[i].get('children', []):
                anatomical_descendants(child)
        if self.root is not None:
            anatomical_descendants(self.root)
        self.accessories = []
        for i, node in enumerate(self.nodes):
            if 'hairaccessory' not in node.get('name', '').lower():
                continue
            ancestor = i
            while ancestor >= 0 and ancestor not in candidates:
                ancestor = int(self.parent[ancestor])
            if ancestor >= 0:
                self.accessories.append(i)
        self.rest_world, self.rest_world_q = self.world(self.q, self.t)
        self.pos = self.rest_world[:, :3, 3]
        pelvis = self.bones.get('Bip001 Pelvis', self.root)
        head = self.bones.get('Bip001 Head')
        if pelvis is None or head is None:
            raise ValueError('The main skin needs Bip001 Pelvis and Bip001 Head.')
        self.up = _unit(self.pos[head] - self.pos[pelvis], [0, 1, 0])
        left = self.bones.get('Bip001 L Thigh')
        right = self.bones.get('Bip001 R Thigh')
        # The positive lateral/pitch axis runs from the character's right side
        # to its left side. Together with up this produces the face-forward
        # axis on the right-handed BlueArchive/glTF skeleton (+Z in its usual
        # scene). Bone names describe anatomy, rather than viewer screen sides.
        side = self.pos[left] - self.pos[right] if left is not None and right is not None else np.array([1, 0, 0])
        self.right = _unit(side-self.up*np.dot(side, self.up), [1, 0, 0])
        self.forward = _unit(np.cross(self.right, self.up), [0, 0, 1])
        # A small forward pelvis lean can tilt the anatomical up vector; keep
        # the principal scene-up axis if it is within 12 degrees of anatomy.
        principal = np.zeros(3)
        axis = int(np.argmax(np.abs(self.up)))
        principal[axis] = np.sign(self.up[axis])
        if np.dot(principal, self.up) > math.cos(math.radians(12)):
            self.up = principal
            self.right = _unit(self.right-self.up*np.dot(self.right, self.up))
            self.forward = _unit(np.cross(self.right, self.up))
        feet = [self.bones[n] for n in ('Bip001 L Foot', 'Bip001 R Foot') if n in self.bones]
        floor = min((np.dot(self.pos[i], self.up) for i in feet), default=np.dot(self.pos[pelvis], self.up)-.5)
        self.height = max(.1, (np.dot(self.pos[head], self.up)-floor)*1.16)

    def world(self, rotations, translations):
        # IK evaluates this hierarchy repeatedly. Batch siblings at each tree
        # depth so seven clips remain practical for rigs with many cloth bones.
        x, y, z, w = rotations.T
        basis = np.stack((
            1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
            2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
            2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y),
        ), axis=1).reshape(-1, 3, 3)
        local = np.broadcast_to(np.eye(4), (len(self.nodes), 4, 4)).copy()
        local[:, :3, :3] = basis*self.s[:, None, :]
        local[:, :3, 3] = translations
        matrices = np.empty_like(local)
        quaternions = np.empty_like(rotations)
        roots = self.levels[0]
        matrices[roots], quaternions[roots] = local[roots], rotations[roots]
        for level in self.levels[1:]:
            parents = self.parent[level]
            matrices[level] = matrices[parents] @ local[level]
            a, b = quaternions[parents], rotations[level]
            values = np.empty_like(a)
            values[:, :3] = a[:, 3, None]*b[:, :3]+b[:, 3, None]*a[:, :3]+np.cross(a[:, :3], b[:, :3])
            values[:, 3] = a[:, 3]*b[:, 3]-np.sum(a[:, :3]*b[:, :3], axis=1)
            quaternions[level] = values/np.maximum(np.linalg.norm(values, axis=1, keepdims=True), _EPS)
        return matrices, quaternions

    def pose(self, changes, displacement=None):
        rotations = self.q.copy()
        translations = self.t.copy()
        if displacement is not None and self.root is not None:
            parent = self.parent[self.root]
            inverse_basis = np.linalg.inv(self.rest_world[parent, :3, :3]) if parent >= 0 else np.eye(3)
            translations[self.root] += inverse_basis @ displacement
        # Convert world-axis deltas to local rotations using the *animated*
        # parent's world orientation, preserving the full imported rest pose.
        world_q = np.empty_like(rotations)
        for i in self.order:
            parent = self.parent[i]
            parent_q = world_q[parent] if parent >= 0 else _IDENTITY
            if i in changes:
                delta = _IDENTITY.copy()
                for axis, degrees in changes[i]:
                    delta = _qmul(_axisq(axis, degrees), delta)
                rotations[i] = _qnorm(_qmul(_qmul(_qmul(_qinv(parent_q), delta), parent_q), self.q[i]))
            world_q[i] = _qnorm(_qmul(parent_q, rotations[i]))
        return rotations, translations

    def leg_ik(self, rotations, translations, side, phase):
        thigh = self.bones.get(f'Bip001 {side} Thigh')
        calf = self.bones.get(f'Bip001 {side} Calf')
        foot = self.bones.get(f'Bip001 {side} Foot')
        if None in (thigh, calf, foot):
            return
        world, world_q = self.world(rotations, translations)
        hip = world[thigh, :3, 3]
        foot_rest = self.pos[foot]
        stride = self.height * .072
        swing = max(0., -math.sin(phase))
        toe_off = 18 * max(0., -math.sin(phase*2))**2 if math.sin(phase) >= 0 else 0.
        pitch = toe_off - 9*swing
        # Pivot late-stance heel lift around the toe, keeping the toe on its
        # rest floor instead of pitching the entire sole through the ground.
        toe = self.bones.get(f'Bip001 {side} Toe0')
        roll = np.zeros(3)
        if toe is not None and toe_off > 0:
            offset = self.pos[toe]-foot_rest
            roll = offset-_qrot(_axisq(self.right, pitch), offset)
            # Rounded SD footwear extends beyond the anatomical toe pivot.
            # A tiny clearance margin prevents its thicker sole clipping the
            # floor while leaving the intended planted-toe roll visible.
            roll += self.up * (self.height*.003*toe_off/18)
        target = (foot_rest + self.forward * (stride * math.cos(phase))
                  + self.up * (self.height * .036 * swing**1.6) + roll)
        self.leg_target(rotations, translations, side, target, pitch)

    def leg_target(self, rotations, translations, side, target, pitch=0.):
        """Two-bone IK for a world-space ankle target, preserving foot twist."""
        thigh = self.bones.get(f'Bip001 {side} Thigh')
        calf = self.bones.get(f'Bip001 {side} Calf')
        foot = self.bones.get(f'Bip001 {side} Foot')
        if None in (thigh, calf, foot):
            return
        world, world_q = self.world(rotations, translations)
        hip = world[thigh, :3, 3]
        length1 = np.linalg.norm(self.pos[calf]-self.pos[thigh])
        length2 = np.linalg.norm(self.pos[foot]-self.pos[calf])
        direction = target-hip
        distance = np.clip(np.linalg.norm(direction), abs(length1-length2)+1e-5, (length1+length2)*.997)
        aim = _unit(direction, -self.up)
        cosine = np.clip((length1**2+distance**2-length2**2)/(2*length1*distance), -1, 1)
        bend = _unit(self.forward-aim*np.dot(self.forward, aim), self.forward)
        knee = hip + length1 * (aim*cosine + bend*math.sqrt(max(0., 1-cosine*cosine)))
        for joint, child, desired in ((thigh, calf, knee-hip), (calf, foot, target-knee)):
            world, world_q = self.world(rotations, translations)
            original = world[child, :3, 3]-world[joint, :3, 3]
            target_q = _qmul(_alignq(original, desired), world_q[joint])
            parent = self.parent[joint]
            rotations[joint] = _qnorm(_qmul(_qinv(world_q[parent]), target_q)) if parent >= 0 else _qnorm(target_q)
        world, world_q = self.world(rotations, translations)
        # Late stance toe-off and a small raised toe during swing. Positive
        # rotation about anatomical right points the toes toward the floor.
        desired_q = _qmul(_axisq(self.right, pitch), self.rest_world_q[foot])
        rotations[foot] = _qnorm(_qmul(_qinv(world_q[self.parent[foot]]), desired_q))

    def run_leg_ik(self, rotations, translations, side, cycle, *, stride_scale=1., lift_scale=1.):
        """A running stride with 36% stance, heel recovery and an aerial phase.

        Feet travel further than in Walk, fold up behind the hips and drive the
        knees forward. The opposite legs' short contact windows never overlap.
        This is a separate pose trajectory; no walking keys are time-scaled.
        """
        foot = self.bones.get(f'Bip001 {side} Foot')
        if foot is None:
            return
        cycle %= 1.
        duty = .36
        stride = self.height*.145*stride_scale
        if cycle < duty:
            stance = cycle/duty
            travel = stride*(1-2*stance)
            lift = 0.
            pitch = 29*max(0., (stance-.55)/.45)**2
            toe = self.bones.get(f'Bip001 {side} Toe0')
            roll = np.zeros(3)
            if toe is not None and pitch > 0:
                offset = self.pos[toe]-self.pos[foot]
                roll = offset-_qrot(_axisq(self.right, pitch), offset)
                roll += self.up*(self.height*.003*pitch/29)
        else:
            swing = (cycle-duty)/(1-duty)
            travel, lift, pitch = _motion_path(swing, [
                (0, [-stride, 0, 29]),
                (.22, [-stride*.80, self.height*.085*lift_scale, 35]),
                (.52, [stride*.20, self.height*.110*lift_scale, -13]),
                (.78, [stride*.91, self.height*.048*lift_scale, -16]),
                (1, [stride, 0, 0]),
            ])
            roll = np.zeros(3)
            toe = self.bones.get(f'Bip001 {side} Toe0')
            if toe is not None and swing < .22:
                # Carry the late-stance toe pivot into the first swing key;
                # removing it at toe-off would teleport the ankle downward.
                offset = self.pos[toe]-self.pos[foot]
                weight = 1-swing/.22
                weight = weight*weight*(3-2*weight)
                roll = (offset-_qrot(_axisq(self.right, 29), offset)
                        +self.up*(self.height*.003))*weight
        target = self.pos[foot]+self.forward*travel+self.up*lift+roll
        self.leg_target(rotations, translations, side, target, pitch)

    def palm_offset(self, side='R'):
        """Rest-world offset from wrist to grip, halfway toward the knuckles."""
        hand = self.bones.get(f'Bip001 {side} Hand')
        if hand is None:
            return np.zeros(3)
        fingers = [self.bones[f'Bip001 {side} {part}'] for part in ('Finger1', 'Finger2')
                   if f'Bip001 {side} {part}' in self.bones]
        if fingers:
            return .5*(self.pos[fingers].mean(axis=0)-self.pos[hand])
        return _qrot(self.rest_world_q[hand], np.array([self.height*.04, 0, 0]))

    def arm_target(self, rotations, translations, side, wrist_target, elbow_pole, hand_world_q):
        """Solve shoulder/elbow/wrist position and absolute hand orientation.

        The forearm also receives the weapon's twist, so the wrist does not
        carry an otherwise disconnected full revolution by itself.
        """
        upper = self.bones.get(f'Bip001 {side} UpperArm')
        fore = self.bones.get(f'Bip001 {side} Forearm')
        hand = self.bones.get(f'Bip001 {side} Hand')
        if None in (upper, fore, hand):
            return
        world, world_q = self.world(rotations, translations)
        shoulder = world[upper, :3, 3]
        length1 = np.linalg.norm(self.pos[fore]-self.pos[upper])
        length2 = np.linalg.norm(self.pos[hand]-self.pos[fore])
        direction = wrist_target-shoulder
        aim = _unit(direction, self.forward)
        distance = np.clip(np.linalg.norm(direction), abs(length1-length2)+1e-6, (length1+length2)*.985)
        wrist_target = shoulder+aim*distance
        cosine = np.clip((length1**2+distance**2-length2**2)/(2*length1*distance), -1, 1)
        pole = elbow_pole-shoulder
        bend = _unit(pole-aim*np.dot(pole, aim), -self.up)
        elbow = shoulder+length1*(aim*cosine+bend*math.sqrt(max(0., 1-cosine*cosine)))
        upper_q = _qmul(_alignq(world[fore, :3, 3]-shoulder, elbow-shoulder), world_q[upper])
        parent = self.parent[upper]
        rotations[upper] = _qnorm(_qmul(_qinv(world_q[parent]), upper_q)) if parent >= 0 else _qnorm(upper_q)
        world, world_q = self.world(rotations, translations)
        desired_fore = _qmul(_qmul(hand_world_q, _qinv(self.rest_world_q[hand])), self.rest_world_q[fore])
        local_segment = self.t[hand]*self.s[fore]
        fore_q = _qmul(_alignq(_qrot(desired_fore, local_segment), wrist_target-elbow), desired_fore)
        rotations[fore] = _qnorm(_qmul(_qinv(world_q[self.parent[fore]]), fore_q))
        world, world_q = self.world(rotations, translations)
        rotations[hand] = _qnorm(_qmul(_qinv(world_q[self.parent[hand]]), hand_world_q))

    def finger_grip(self, rotations, translations, side, grip, shaft_axis, strength, *, closed_fist=False):
        """Curl measured finger segments toward the grip without joint scaling."""
        tracks = set()
        for finger in range(5):
            base = self.bones.get(f'Bip001 {side} Finger{finger}')
            distal = self.bones.get(f'Bip001 {side} Finger{finger}1')
            if base is None or distal is None:
                continue
            proximal_limit = (65 if finger == 0 else 100) if closed_fist else (43 if finger == 0 else 65)
            distal_limit = (45 if finger == 0 else 90) if closed_fist else (26 if finger == 0 else 48)
            for joint, child, limit in ((base, distal, proximal_limit), (distal, None, distal_limit)):
                tracks.add(joint)
                world, world_q = self.world(rotations, translations)
                point = world[joint, :3, 3]
                original = (world[child, :3, 3]-point if child is not None
                            else _qrot(world_q[joint], np.array([1., 0., 0.])))
                # The thumb crosses the curled fingers in a fist; targeting
                # an infinite grip line would leave it extended upward.
                closest = (grip+self.forward*(self.height*.045) if closed_fist and finger == 0 else
                           grip+shaft_axis*np.dot(point-grip, shaft_axis))
                desired = closest-point
                if np.linalg.norm(desired) < 1e-5:
                    continue
                curl = _alignq(original, desired)
                angle = math.degrees(2*math.acos(float(np.clip(abs(curl[3]), 0, 1))))
                fraction = strength*min(1., limit/max(angle, 1e-5))
                target_q = _qmul(_slerp(_IDENTITY, curl, fraction), world_q[joint])
                parent = self.parent[joint]
                rotations[joint] = _qnorm(_qmul(_qinv(world_q[parent]), target_q)) if parent >= 0 else _qnorm(target_q)
        return tracks


def _envelope(u, start=.08, peak=.45, end=.92):
    if u <= start or u >= end:
        return 0.
    value = (u-start)/(peak-start) if u < peak else (end-u)/(end-peak)
    return value*value*(3-2*value)


def _character_number(character_id):
    if isinstance(character_id, (int, np.integer)):
        return int(character_id)
    digits = re.findall(r'\d+', str(character_id))
    return int(digits[-1]) if digits else sum(map(ord, str(character_id)))


def _motion_path(u, keys):
    """Smooth deterministic key poses, including explicit holds and recovery."""
    if u <= keys[0][0]:
        return np.asarray(keys[0][1], dtype=float)
    for (begin, first), (end, last) in zip(keys, keys[1:]):
        if u <= end:
            weight = float(np.clip((u-begin)/(end-begin), 0, 1))
            weight = weight*weight*(3-2*weight)
            return np.asarray(first, dtype=float)*(1-weight)+np.asarray(last, dtype=float)*weight
    return np.asarray(keys[-1][1], dtype=float)


def _weapon_rotation(rig, shaft, face_normal):
    """World rotation from an upright (+Y), front-facing (+Z) prop bind.

    Props must be rigidly attached to the hand, with their grip at palm_offset.
    This is independent of the imported hand's arbitrary bone-local axes.
    """
    shaft = _unit(shaft, rig.up)
    normal = _unit(face_normal-shaft*np.dot(face_normal, shaft), rig.forward)
    lateral = _unit(np.cross(shaft, normal), rig.right)
    normal = _unit(np.cross(lateral, shaft), normal)
    desired = np.column_stack((lateral, shaft, normal))
    bind = np.column_stack((rig.right, rig.up, rig.forward))
    return _matrixq(desired @ bind.T)


def _fist_rotation(rig, side):
    """Aim measured knuckles forward with the thumb side facing upward."""
    hand = rig.bones.get(f'Bip001 {side} Hand')
    if hand is None:
        return _IDENTITY.copy()
    fingers = [rig.bones[f'Bip001 {side} Finger{i}'] for i in (1, 2, 3, 4)
               if f'Bip001 {side} Finger{i}' in rig.bones]
    knuckles = _unit(rig.pos[fingers].mean(axis=0)-rig.pos[hand], -rig.right if side == 'R' else rig.right) if fingers else _unit(rig.palm_offset(side))
    index = rig.bones.get(f'Bip001 {side} Finger1')
    pinky = fingers[-1] if len(fingers) >= 2 else None
    spread = rig.pos[index]-rig.pos[pinky] if index is not None and pinky is not None else rig.up
    thumb_side = _unit(spread-knuckles*np.dot(spread, knuckles), rig.up)
    bind = np.column_stack((_unit(np.cross(knuckles, thumb_side)), knuckles, thumb_side))
    desired = np.column_stack((_unit(np.cross(rig.forward, rig.up)), rig.forward, rig.up))
    return _matrixq(desired @ bind.T)


_ATTACK_ACTIONS = {
    1: 'Ribbon rapier: measured fencing lunge and recovery',
    2: 'Crescent scythe: two-handed overhead reaping cut with inner edge leading',
    3: 'Azure wave: wide lateral trace followed by a flowing palm release',
    4: 'Tidal arc: overhead summoning circle and descending charm release',
    5: 'Rose pulse: two compact forward casts with a guarded free hand',
    6: 'Clover bloom: rising wand spiral and a small outward seed flick',
    7: 'Cat pounce: lead paw jab followed by a rear paw cross',
    8: 'Clockwork doll: alternating angular hand strikes with a ticking head',
    9: 'Peony fan: cross-body fan slice and outward wrist flourish',
    10: 'Snow crystal: gather with both hands, raise, then release symmetrically',
    11: 'Trailblazer daggers: left diagonal cut, right return cut and crossed recovery',
    12: 'Fox-star baton: buoyant wind-up, zigzag star trace and forward bell flick',
    13: 'Flower witch: staff traces a summoning arc while the free hand writes a spell',
    14: 'Rose blessing: cradle the bouquet, extend its flowers and sink into a gentle curtsy',
}
_ATTACK_DURATIONS = {1: 1.55, 2: 1.95, 3: 1.75, 4: 2.10, 5: 1.60,
                     6: 1.85, 7: 1.50, 8: 1.80, 9: 1.85, 10: 2.20,
                     11: 1.90, 12: 2.05, 13: 2.45, 14: 2.55}


_REFERENCE_STYLES = {11: 'daggers', 12: 'fox_baton', 13: 'witch_staff', 14: 'bouquet'}
_REFERENCE_ACTIONS = {
    11: {
        'Idle': 'Alert trailblazer: balanced low blades, a small scouting glance and breathing',
        'Walk': 'Light adventurer steps with outward low blades, a forward lean and scouting head turns',
        'Run': 'Quick trailblazer sprint with both blades kept outside the body and compact knee drive',
        'Victory': 'Confident dagger salute, a quick left-hand flourish and a satisfied nod',
    },
    12: {
        'Idle': 'Cheerful fox: a swaying hip pose, shoulder-high star baton and playful head tilt',
        'Walk': 'Buoyant fox steps with lifted toes, a swinging star baton and a jaunty free hand',
        'Run': 'Bouncy fox dash with a high baton carry and a pumping free arm',
        'Victory': 'Two fox-ear hand beats, a side-to-side baton cheer and a little celebratory hop',
    },
    13: {
        'Idle': 'Thoughtful flower witch: upright staff, free hand over the spell book and a quiet glance',
        'Walk': 'Measured witch steps with an upright staff, restrained foot lift and gentle cape sway',
        'Run': 'Purposeful witch dash with a stable upright staff and a free hand protecting the hat',
        'Victory': 'A theatrical hat-tip, an outward spell-hand flourish and a courteous bow',
    },
    14: {
        'Idle': 'Poised rose princess: bouquet close to the heart, a gentle head tilt and breathing',
        'Walk': 'Small graceful barefoot steps with the bouquet held to the heart and the gown gathered aside',
        'Run': 'Careful princess hurry with shortened strides, bouquet protected and the gown lifted aside',
        'Victory': 'A deep royal curtsy, a gracious bouquet presentation and a warm head tilt',
    },
}


def _reference_walk_leg(rig, rotations, translations, side, phase, number):
    """Costume-aware stride lengths and toe clearance for the four new designs."""
    foot = rig.bones.get(f'Bip001 {side} Foot')
    if foot is None:
        return
    stride, lift, toe_angle, width = {
        11: (.062, .030, 16, .008),
        12: (.072, .052, 20, .014),
        13: (.042, .022, 10, .004),
        14: (.033, .018, 7, .002),
    }[number]
    swing = max(0., -math.sin(phase))
    toe_off = toe_angle*max(0., -math.sin(phase*2))**2 if math.sin(phase) >= 0 else 0.
    pitch = toe_off-(10 if number == 12 else 6)*swing
    target = (rig.pos[foot]+rig.forward*rig.height*stride*math.cos(phase)
              +rig.up*rig.height*lift*swing**1.6
              +rig.right*rig.height*width*swing*(1 if side == 'L' else -1))
    toe = rig.bones.get(f'Bip001 {side} Toe0')
    if toe is not None and toe_off > 0:
        offset = rig.pos[toe]-rig.pos[foot]
        target += offset-_qrot(_axisq(rig.right, pitch), offset)
        target += rig.up*rig.height*.003*toe_off/max(toe_angle, 1)
    rig.leg_target(rotations, translations, side, target, pitch)


def _reference_character_pose(rig, u, clip_name, number):
    """Independent whole-body performances with rigid palm-bound props.

    Every prop binds upright along anatomical up with its decorated face along
    forward. Both of Quinn's hands carry daggers; the other props use the right
    hand. All arm trajectories use measured shoulder/elbow/palm IK. Garment
    bones remain on the same imported skeleton and receive restrained sway.
    """
    right, up, forward, height = rig.right, rig.up, rig.forward, rig.height
    loop = clip_name in ('Idle', 'Walk', 'Run')
    if clip_name == 'Lose':
        progress = min(u/.80, 1.)
        activity = progress*progress*(3-2*progress)
    elif loop:
        activity = 1.
    else:
        enter, leave = min(u/.12, 1.), min((1-u)/.18, 1.)
        activity = min(enter*enter*(3-2*enter), leave*leave*(3-2*leave))
    phase = 2*math.pi*u
    changes, tracks = defaultdict(list), set()

    def rotate(name, axis, degrees):
        index = rig.bones.get(name) if isinstance(name, str) else name
        if index is not None:
            changes[index].append((axis, float(degrees)*activity))
            tracks.add(index)

    # Grip coordinates are lateral/up/forward offsets from the shoulder midpoint.
    # Shaft vectors use the same anatomical basis, independent of bone-local axes.
    grip_r, grip_l = {
        11: ([-.18, -.19, .075], [.18, -.19, .075]),
        12: ([-.18, -.045, .12], [.13, -.20, .08]),
        13: ([-.205, -.145, .11], [.085, -.10, .15]),
        14: ([-.045, -.115, .16], [.16, -.22, .07]),
    }[number]
    grip_r, grip_l = np.array(grip_r), np.array(grip_l)
    shaft_r = np.array([-.22, -.91, .35]) if number == 11 else np.array([0., 1., 0.])
    shaft_l = np.array([.22, -.91, .35]) if number == 11 else np.array([0., 1., 0.])
    normal_r = normal_l = np.array([0., 0., 1.])
    # twist, pitch, roll, head pitch, head yaw, head roll, drop, forward travel
    body = np.zeros(8)
    foot_step, foot_width = 0., 0.
    if clip_name == 'Idle':
        breath = math.sin(phase)
        body[1] = .9*breath
        body[6] = -.002*breath
        if number == 11:
            body[4] = 5*math.sin(phase)
            grip_r[2] += .004*breath
            grip_l[2] -= .003*breath
        elif number == 12:
            body[2], body[5] = 2.3*breath, -4+2*math.sin(phase+.5)
            grip_r[1] += .008*math.sin(phase+.35)
            shaft_r = np.array([-.20+.08*breath, .98, .05])
        elif number == 13:
            body[4], body[5] = 2.2*math.sin(phase), 1.2*math.sin(phase+.4)
            grip_l[1] += .004*breath
        else:
            body[3], body[5] = -1.2*breath, 3+1.2*math.sin(phase)
            grip_r[1] += .003*breath
    elif clip_name in ('Walk', 'Run'):
        running = clip_name == 'Run'
        swing, sway = math.cos(phase), math.sin(phase)
        if number == 11:
            body[:] = [3.8*swing, 5.5 if running else 2.2, 2.0*sway,
                       -3 if running else -1, 3.2*swing, -.8*sway,
                       .022-.015*(1-math.cos(phase*2)) if running else .016-.005*(1-math.cos(phase*2)), 0]
            grip_r[2] += (.048 if running else .026)*swing
            grip_l[2] -= (.048 if running else .026)*swing
            shaft_r = np.array([-.28, -.90, .30])
            shaft_l = np.array([.28, -.90, .30])
        elif number == 12:
            body[:] = [5*swing, 6 if running else 1.5, 4*sway, -3,
                       2*swing, -4+3*sway, .012-.012*(1-math.cos(phase*2)), 0]
            grip_r[1] += .018*math.sin(phase*2)
            grip_r[2] += .034*swing
            grip_l = np.array([.16, -.14 if running else -.18, .11-(.070 if running else .035)*swing])
            shaft_r = np.array([-.28+.12*sway, .96, .13*swing])
        elif number == 13:
            body[:] = [1.8*swing, 6 if running else 1.2, 1.4*sway,
                       -3 if running else 0, 1.2*swing, -1.2*sway,
                       .020-.013*(1-math.cos(phase*2)) if running else .014-.003*(1-math.cos(phase*2)), 0]
            grip_r[2] += .010*swing
            grip_l = np.array([.16, .26, .015]) if running else grip_l+np.array([0, .003*sway, .006*swing])
            shaft_r = np.array([-.055, .998, .018*swing])
        else:
            body[:] = [1.2*swing, 3 if running else -.8, 1.1*sway,
                       -1.5, .8*swing, 3+1.2*sway,
                       .019-.011*(1-math.cos(phase*2)) if running else .012-.0025*(1-math.cos(phase*2)), 0]
            grip_r[1] += .003*math.cos(phase*2)
            grip_l[1] += .045 if running else .018
            grip_l[0] += .020
            shaft_r = np.array([-.08, .992, .10])
    elif clip_name == 'Attack':
        if number == 11:
            grip_r = _motion_path(u, [(0, [-.18, -.18, .09]), (.23, [-.21, -.045, .10]),
                                      (.42, [-.22, -.03, .16]), (.61, [.05, -.16, .23]),
                                      (.69, [.05, -.16, .23]), (.83, [-.16, -.10, .13]), (1, [-.18, -.18, .09])])
            grip_l = _motion_path(u, [(0, [.18, -.18, .09]), (.23, [.20, -.035, .10]),
                                      (.40, [-.035, -.145, .24]), (.45, [-.035, -.145, .24]),
                                      (.60, [.16, -.08, .11]), (.78, [.11, -.12, .12]), (1, [.18, -.18, .09])])
            shaft_r = _motion_path(u, [(0, [-.2, -.9, .3]), (.23, [-.6, .75, .28]),
                                       (.42, [-.7, .65, .35]), (.61, [.60, -.45, .65]), (1, [-.2, -.9, .3])])
            shaft_l = _motion_path(u, [(0, [.2, -.9, .3]), (.23, [.6, .75, .28]),
                                       (.40, [-.65, -.35, .67]), (.60, [.25, .90, .36]), (1, [.2, -.9, .3])])
            body = _motion_path(u, [(0, [0]*8), (.23, [-15, -3, -2, -3, 6, 0, .026, -.005]),
                                   (.40, [-24, 8, -4, -2, 12, 0, .026, .022]),
                                   (.61, [23, 10, 3, -2, -12, 0, .025, .028]), (1, [0]*8)])
            foot_step, foot_width = .042, .019
        elif number == 12:
            grip_r = _motion_path(u, [(0, [-.18, -.045, .12]), (.22, [-.22, .08, .10]),
                                      (.37, [-.02, .14, .14]), (.48, [-.18, .03, .21]),
                                      (.62, [-.04, -.02, .26]), (.70, [-.04, -.02, .26]), (1, [-.18, -.045, .12])])
            grip_l = _motion_path(u, [(0, [.13, -.18, .08]), (.22, [.15, .01, .08]),
                                      (.42, [.18, .035, .12]), (.62, [.14, -.02, .20]), (1, [.13, -.18, .08])])
            shaft_r = _motion_path(u, [(0, [0, 1, 0]), (.22, [-.65, .76, 0]),
                                       (.37, [.80, .60, .10]), (.48, [-.70, .65, .28]),
                                       (.62, [0, .30, .96]), (.70, [0, .30, .96]), (1, [0, 1, 0])])
            body = _motion_path(u, [(0, [0]*8), (.22, [-12, -4, -5, -4, 7, -7, .008, 0]),
                                   (.42, [8, -3, 5, -4, -5, 5, -.012, .012]),
                                   (.62, [11, 7, -2, -2, -5, -5, .025, .020]), (1, [0]*8)])
            foot_step, foot_width = .026, .016
        elif number == 13:
            grip_r = _motion_path(u, [(0, [-.205, -.145, .11]), (.23, [-.22, -.07, .10]),
                                      (.40, [-.18, -.035, .20]), (.60, [-.16, -.105, .25]),
                                      (.72, [-.16, -.105, .25]), (1, [-.205, -.145, .11])])
            grip_l = _motion_path(u, [(0, [.085, -.10, .15]), (.23, [.13, -.03, .15]),
                                      (.40, [.055, .08, .20]), (.53, [.18, .025, .22]),
                                      (.68, [.10, -.03, .27]), (.76, [.10, -.03, .27]), (1, [.085, -.10, .15])])
            shaft_r = _motion_path(u, [(0, [0, 1, 0]), (.23, [-.28, .95, -.12]),
                                       (.40, [.23, .93, .27]), (.60, [-.12, .84, .53]), (1, [0, 1, 0])])
            body = _motion_path(u, [(0, [0]*8), (.23, [-13, -5, -2, -5, 7, -3, .008, 0]),
                                   (.40, [-3, -3, 2, -4, 2, 2, .006, .005]),
                                   (.68, [14, 6, 0, -3, -8, 0, .018, .016]), (1, [0]*8)])
            foot_step, foot_width = .018, .009
        else:
            grip_r = _motion_path(u, [(0, [-.045, -.115, .16]), (.27, [-.025, -.07, .15]),
                                      (.48, [-.015, -.075, .24]), (.64, [-.02, -.095, .25]),
                                      (.74, [-.025, -.10, .23]), (1, [-.045, -.115, .16])])
            grip_l = _motion_path(u, [(0, [.16, -.22, .07]), (.27, [.025, -.13, .14]),
                                      (.48, [.075, -.11, .23]), (.64, [.11, -.14, .21]),
                                      (.78, [.16, -.20, .10]), (1, [.16, -.22, .07])])
            shaft_r = _motion_path(u, [(0, [0, 1, 0]), (.27, [-.08, .99, .12]),
                                       (.48, [0, .82, .57]), (.64, [0, .82, .57]), (1, [0, 1, 0])])
            body = _motion_path(u, [(0, [0]*8), (.27, [-4, -4, 2, -5, 3, 5, .006, 0]),
                                   (.48, [4, 2, -1, -1, -2, 3, .015, .006]),
                                   (.68, [2, 11, 2, 5, -1, 5, .049, 0]), (1, [0]*8)])
            foot_step, foot_width = .014, -.005
    elif clip_name == 'Victory':
        if number == 11:
            grip_r = _motion_path(u, [(0, [-.18, -.19, .075]), (.25, [-.19, -.015, .16]),
                                      (.41, [-.16, .015, .17]), (.65, [-.16, .015, .17]), (1, [-.18, -.19, .075])])
            grip_l = _motion_path(u, [(0, [.18, -.19, .075]), (.25, [.20, -.17, .06]),
                                      (.43, [.22, -.095, .14]), (.60, [.19, -.13, .08]), (1, [.18, -.19, .075])])
            shaft_r = _motion_path(u, [(0, [-.2, -.9, .3]), (.25, [0, 1, .08]),
                                       (.65, [.12, .98, .12]), (1, [-.2, -.9, .3])])
            shaft_l = _motion_path(u, [(0, [.2, -.9, .3]), (.25, [.3, -.9, .3]),
                                       (.43, [.85, .50, .15]), (.60, [.3, -.9, .3]), (1, [.2, -.9, .3])])
            body = _motion_path(u, [(0, [0]*8), (.25, [-8, -1, -2, -5, 4, -3, .01, 0]),
                                   (.49, [-8, -1, -2, 7, 4, -3, .01, 0]),
                                   (.65, [-8, -1, -2, -3, 4, -3, .01, 0]), (1, [0]*8)])
            foot_step = .012
        elif number == 12:
            cheer = _envelope(u, .08, .37, .91)
            beat = math.sin(6*math.pi*u)*cheer
            grip_r = np.array([-.18+.040*beat, .09, .12])
            grip_l = _motion_path(u, [(0, [.13, -.20, .08]), (.24, [.15, .27, .03]),
                                      (.40, [.18, .20, .07]), (.54, [.15, .27, .03]),
                                      (.70, [.18, .20, .07]), (1, [.13, -.20, .08])])
            shaft_r = np.array([.45*beat, .92, .12])
            body = np.array([4*beat, -4*cheer, 7*beat, -5*cheer, -2*beat, -7*beat,
                             -.017*max(0., math.sin(4*math.pi*u))*cheer, 0])
            foot_width = .010
        elif number == 13:
            grip_l = _motion_path(u, [(0, [.085, -.10, .15]), (.23, [.17, .30, .025]),
                                      (.36, [.17, .30, .025]), (.51, [.23, .01, .18]),
                                      (.64, [.23, .01, .18]), (.77, [.08, -.09, .16]), (1, [.085, -.10, .15])])
            grip_r = _motion_path(u, [(0, [-.205, -.145, .11]), (.23, [-.22, -.12, .10]),
                                      (.64, [-.23, -.145, .10]), (1, [-.205, -.145, .11])])
            shaft_r = np.array([-.07, .997, 0.])
            body = _motion_path(u, [(0, [0]*8), (.23, [-8, -4, -3, -6, 4, -5, .008, 0]),
                                   (.51, [8, 0, 2, -3, -4, 2, .006, 0]),
                                   (.77, [3, 17, 0, 8, -2, 0, .025, 0]), (1, [0]*8)])
        else:
            grip_r = _motion_path(u, [(0, [-.045, -.115, .16]), (.22, [-.04, -.10, .16]),
                                      (.48, [-.04, -.13, .18]), (.68, [-.025, -.08, .23]),
                                      (.80, [-.025, -.08, .23]), (1, [-.045, -.115, .16])])
            grip_l = _motion_path(u, [(0, [.16, -.22, .07]), (.22, [.20, -.19, .05]),
                                      (.48, [.23, -.18, .06]), (.68, [.19, -.18, .07]), (1, [.16, -.22, .07])])
            shaft_r = _motion_path(u, [(0, [0, 1, 0]), (.48, [-.10, .99, .05]),
                                       (.68, [0, .91, .42]), (.80, [0, .91, .42]), (1, [0, 1, 0])])
            body = _motion_path(u, [(0, [0]*8), (.22, [-5, 4, 3, 0, 3, 4, .020, 0]),
                                   (.48, [-5, 17, 3, 8, 3, 5, .067, -.003]),
                                   (.68, [4, -3, 1, -4, -2, 7, .010, 0]), (1, [0]*8)])
            foot_step, foot_width = -.016, -.005
    elif clip_name in ('Defend', 'Lose'):
        losing = clip_name == 'Lose'
        # Defend's 22%-78% hold matches the advertised clip contract exactly.
        if not losing:
            enter, leave = min(u/.22, 1.), min((1-u)/.22, 1.)
            activity = min(enter*enter*(3-2*enter), leave*leave*(3-2*leave))
        body = np.array([-5 if number % 2 else 5, 20 if losing else 7, 0,
                         23 if losing else -3, 0, -4 if losing else 0,
                         .064 if losing and number in (13, 14) else .082 if losing else .030, 0])
        if number == 11:
            grip_r, grip_l = np.array([-.07, -.02, .18]), np.array([.07, -.04, .19])
            shaft_r, shaft_l = np.array([.55, .82, .15]), np.array([-.55, .82, .15])
            if losing:
                grip_r, grip_l = np.array([-.18, -.20, .14]), np.array([.18, -.20, .14])
                shaft_r, shaft_l = np.array([-.35, -.40, .84]), np.array([.35, -.40, .84])
        elif number == 12:
            grip_r, grip_l = np.array([-.07, .015, .17]), np.array([.085, .015, .16])
            shaft_r = np.array([-.30, .94, .15])
            if losing:
                grip_r, grip_l = np.array([-.15, -.20, .13]), np.array([.08, .005, .14])
                shaft_r = np.array([-.25, .76, .60])
        elif number == 13:
            grip_r, grip_l = np.array([-.17, -.065, .20]), np.array([.065, -.035, .17])
            shaft_r = np.array([-.25, .955, .16])
            if losing:
                grip_r, grip_l = np.array([-.215, -.17, .12]), np.array([.10, -.07, .16])
                shaft_r = np.array([-.09, .995, .025])
        else:
            grip_r, grip_l = np.array([-.03, -.035, .17]), np.array([.035, -.085, .16])
            shaft_r = np.array([0, .99, .14])
            if losing:
                grip_r, grip_l = np.array([-.035, -.145, .19]), np.array([.04, -.17, .18])
                shaft_r = np.array([0, .94, .35])
        foot_step, foot_width = (.026 if losing else .008), .007

    twist, pitch, roll, head_pitch, head_yaw, head_roll, drop, advance = body
    rotate('Bip001 Pelvis', up, twist*.4)
    rotate('Bip001 Pelvis', forward, roll*.65)
    rotate('Bip001 Spine', up, twist*.6)
    rotate('Bip001 Spine', right, pitch*.68)
    rotate('Bip001 Spine1', right, pitch*.32)
    rotate('Bip001 Spine1', forward, roll*.35)
    rotate('Bip001 Head', right, head_pitch)
    rotate('Bip001 Head', up, head_yaw-twist*.4)
    rotate('Bip001 Head', forward, head_roll)
    secondary_phase = (phase if loop else 2*math.pi*.22 if clip_name == 'Defend'
                       else 2*math.pi*min(u, .80))
    for i, node in enumerate(rig.accessories):
        sway = (3.2 if number == 12 else 2.1 if number == 11 else 1.3) if clip_name in ('Walk', 'Run') else .8
        rotate(node, right, sway*math.sin(secondary_phase+i*.7))
        rotate(node, forward, sway*.55*math.sin(secondary_phase+i*1.1))
    displacement = height*activity*(-up*drop+forward*advance)
    rotations, translations = rig.pose(changes, displacement)
    world, _ = rig.world(rotations, translations)
    shoulders = [rig.bones[f'Bip001 {s} UpperArm'] for s in ('L', 'R') if f'Bip001 {s} UpperArm' in rig.bones]
    anchor = world[shoulders, :3, 3].mean(axis=0) if shoulders else rig.pos[rig.bones['Bip001 Spine']]
    for side, relative, shaft_values, normal_values in (('R', grip_r, shaft_r, normal_r), ('L', grip_l, shaft_l, normal_l)):
        hand = rig.bones.get(f'Bip001 {side} Hand')
        if hand is None:
            continue
        sign = 1 if side == 'L' else -1
        has_prop = side == 'R' or number == 11
        shaft = _unit(right*shaft_values[0]+up*shaft_values[1]+forward*shaft_values[2], up)
        normal = _unit(right*normal_values[0]+up*normal_values[1]+forward*normal_values[2], forward)
        desired = _weapon_rotation(rig, shaft, normal) if has_prop else _axisq(forward, -sign*18)
        delta = _slerp(_IDENTITY, desired, activity)
        offset = rig.palm_offset(side)
        rest_grip = rig.pos[hand]+offset
        goal = anchor+height*(right*relative[0]+up*relative[1]+forward*relative[2])
        goal = rest_grip+(goal-rest_grip)*activity
        if clip_name == 'Run':
            # Running elbows follow the shoulder, rather than the wide wrist
            # carry. The outward pole used by other gestures would flare the
            # short SD upper arms sideways even when the palms are low.
            shoulder = world[rig.bones[f'Bip001 {side} UpperArm'], :3, 3]
            pole = shoulder+height*(right*sign*.015-up*.20-forward*.055)
        else:
            pole = anchor+height*(right*sign*.29-up*.19+forward*.055)
        elbow = rig.bones.get(f'Bip001 {side} Forearm')
        if elbow is not None:
            pole = rig.pos[elbow]+(pole-rig.pos[elbow])*activity
        rig.arm_target(rotations, translations, side, goal-_qrot(delta, offset), pole,
                       _qmul(delta, rig.rest_world_q[hand]))
        if has_prop:
            world, _ = rig.world(rotations, translations)
            actual = world[hand, :3, 3]+_qrot(delta, offset)
            tracks.update(rig.finger_grip(rotations, translations, side, actual,
                                         _qrot(delta, up), .86*activity))
        elif number == 12 and clip_name == 'Victory':
            # The fox salute leaves index and little finger raised while the
            # thumb, middle and ring fingers curl, matching her playful cue.
            world, _ = rig.world(rotations, translations)
            actual = world[hand, :3, 3]+_qrot(delta, offset)
            tracks.update(rig.finger_grip(rotations, translations, side,
                                         actual-forward*height*.045, up, .95*activity,
                                         closed_fist=True))
            for finger in (1, 4):
                for suffix in ('', '1'):
                    index = rig.bones.get(f'Bip001 {side} Finger{finger}{suffix}')
                    if index is not None:
                        rotations[index] = rig.q[index]
                        tracks.add(index)
        for part in ('UpperArm', 'Forearm', 'Hand'):
            index = rig.bones.get(f'Bip001 {side} {part}')
            if index is not None:
                tracks.add(index)
    for side, sign in (('L', 1), ('R', -1)):
        foot = rig.bones.get(f'Bip001 {side} Foot')
        if foot is not None:
            if clip_name == 'Walk':
                _reference_walk_leg(rig, rotations, translations, side, phase+(math.pi if side == 'R' else 0), number)
            elif clip_name == 'Run':
                # The gown's short careful run retains an aerial phase while
                # reducing the usual stride; other designs use the full sprint.
                if number == 14:
                    rig.run_leg_ik(rotations, translations, side, u+(.5 if side == 'R' else 0),
                                   stride_scale=.60, lift_scale=.64)
                else:
                    rig.run_leg_ik(rotations, translations, side, u+(.5 if side == 'R' else 0))
            else:
                target = rig.pos[foot]+height*activity*(right*sign*foot_width
                                                       +forward*(foot_step if side == 'L' else -foot_step*.55))
                rig.leg_target(rotations, translations, side, target)
        for part in ('Thigh', 'Calf', 'Foot'):
            index = rig.bones.get(f'Bip001 {side} {part}')
            if index is not None:
                tracks.add(index)
    if not loop and (u <= _EPS or (clip_name != 'Lose' and u >= 1-_EPS)):
        rotations, translations = rig.q.copy(), rig.t.copy()
    return rotations, translations, tracks


def _attack_personality(number, kind):
    """Independent hand/torso paths for characters sharing the same charm prop."""
    upright = [(0, [0, 1, 0]), (1, [0, 1, 0])]
    front = [(0, [0, 0, 1]), (1, [0, 0, 1])]
    recipe = {}
    if kind == 'charm' and number == 3:
        recipe = dict(
            grip=[(0, [-.12, -.13, .08]), (.26, [-.25, -.025, .065]),
                  (.44, [-.16, -.055, .21]), (.62, [.09, -.065, .23]),
                  (.79, [.02, -.12, .13]), (1, [-.12, -.13, .08])],
            shaft=[(0, [0, 1, 0]), (.26, [-.55, .82, .15]),
                   (.62, [.60, .55, .58]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.26, [.18, -.09, -.02]),
                  (.48, [.21, -.035, .12]), (.67, [.05, -.10, .22]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.26, [-18, -3, -.012]),
                   (.62, [20, 6, .018]), (1, [0, 0, 0])], step=.04)
    elif kind == 'charm' and number == 4:
        recipe = dict(
            grip=[(0, [-.12, -.14, .08]), (.24, [-.17, .07, .08]),
                  (.40, [-.08, .19, .08]), (.60, [-.11, .015, .25]),
                  (.73, [-.11, -.045, .23]), (1, [-.12, -.14, .08])],
            shaft=[(0, [0, 1, 0]), (.40, [-.30, .94, 0]),
                   (.60, [0, .33, .94]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.28, [.035, -.105, .14]),
                  (.44, [.10, -.015, .16]), (.65, [.15, -.09, .22]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.40, [-6, -11, 0]),
                   (.65, [7, 8, 0]), (1, [0, 0, 0])], step=.025)
    elif kind == 'charm' and number == 5:
        recipe = dict(
            grip=[(0, [-.12, -.13, .08]), (.24, [-.11, -.07, .12]),
                  (.43, [-.07, -.065, .27]), (.53, [-.11, -.07, .13]),
                  (.67, [-.07, -.065, .27]), (.77, [-.11, -.07, .13]), (1, [-.12, -.13, .08])],
            shaft=[(0, [0, 1, 0]), (.24, [0, .96, .28]),
                   (.43, [0, .22, .98]), (.53, [0, .92, .40]),
                   (.67, [0, .22, .98]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.24, [.06, -.09, .16]),
                  (.67, [.08, -.045, .16]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.24, [-9, -3, 0]),
                   (.43, [8, 7, .006]), (.53, [-4, 0, 0]),
                   (.67, [8, 7, .006]), (1, [0, 0, 0])], step=.035)
    elif kind == 'wand':
        recipe = dict(
            grip=[(0, [-.12, -.15, .08]), (.23, [-.20, .005, .07]),
                  (.38, [-.08, .12, .09]), (.53, [.025, .015, .22]),
                  (.70, [-.09, -.03, .22]), (1, [-.12, -.15, .08])],
            shaft=[(0, [0, 1, 0]), (.23, [-.65, .76, 0]),
                   (.38, [.48, .88, .04]), (.53, [.30, .40, .86]),
                   (.70, [-.18, .53, .83]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.28, [.19, -.06, .03]),
                  (.53, [.11, -.045, .19]), (.73, [.15, -.12, .11]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.23, [-12, -6, -.009]),
                   (.53, [13, 5, .009]), (.70, [-4, 3, 0]), (1, [0, 0, 0])], step=.035)
    elif kind == 'punch' and number == 7:
        recipe = dict(
            grip=[(0, [-.11, -.035, .11]), (.22, [-.13, -.025, .075]),
                  (.35, [-.20, -.015, -.015]), (.51, [.015, -.035, .295]),
                  (.56, [.015, -.035, .295]), (.75, [-.11, -.035, .11]), (1, [-.11, -.035, .11])],
            shaft=upright,
            left=[(0, [.12, .02, .11]), (.16, [.11, .025, .13]),
                  (.28, [.025, .015, .285]), (.35, [.025, .015, .285]),
                  (.48, [.11, .025, .11]), (.65, [.14, .02, .12]), (1, [.12, .02, .11])],
            torso=[(0, [0, 0, 0]), (.28, [-16, 6, -.004]),
                   (.35, [-25, -4, -.010]), (.51, [26, 10, .013]),
                   (.75, [-6, 0, 0]), (1, [0, 0, 0])], step=.055)
    elif kind == 'charm' and number == 8:
        recipe = dict(
            grip=[(0, [-.12, -.14, .08]), (.22, [-.16, -.06, .10]),
                  (.38, [-.16, -.06, .10]), (.51, [-.14, .035, .23]),
                  (.62, [-.14, .035, .23]), (.73, [-.08, -.10, .14]), (1, [-.12, -.14, .08])],
            shaft=[(0, [0, 1, 0]), (.22, [-.60, .80, 0]),
                   (.38, [-.60, .80, 0]), (.51, [0, .70, .71]),
                   (.62, [0, .70, .71]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.22, [.15, -.025, .21]),
                  (.38, [.15, -.025, .21]), (.51, [.15, -.13, .10]),
                  (.62, [.15, -.13, .10]), (.75, [.025, -.025, .18]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.22, [-12, -3, -.006]),
                   (.38, [-12, -3, -.006]), (.51, [12, 7, .006]),
                   (.62, [12, 7, .006]), (1, [0, 0, 0])], step=.025)
    elif kind == 'charm' and number == 10:
        recipe = dict(
            grip=[(0, [-.12, -.14, .08]), (.24, [-.035, -.10, .15]),
                  (.41, [-.075, .12, .12]), (.57, [-.16, .035, .23]),
                  (.72, [-.19, -.035, .24]), (1, [-.12, -.14, .08])],
            shaft=[(0, [0, 1, 0]), (.41, [-.35, .94, 0]),
                   (.72, [-.38, .40, .83]), (1, [0, 1, 0])],
            left=[(0, [.13, -.15, .08]), (.24, [.035, -.10, .15]),
                  (.41, [.075, .12, .12]), (.57, [.16, .035, .23]),
                  (.72, [.19, -.035, .24]), (1, [.13, -.15, .08])],
            torso=[(0, [0, 0, 0]), (.24, [0, 7, 0]),
                   (.41, [0, -9, 0]), (.72, [0, 8, 0]), (1, [0, 0, 0])], step=.025)
    if recipe:
        recipe.setdefault('normal', front)
    return recipe


def _weapon_attack_pose(rig, u, kind, number=0):
    """Weapon-led IK attack: guard, wind-up, impact/hold, then recovery."""
    enter = float(np.clip(u/.12, 0, 1))
    leave = float(np.clip((1-u)/.20, 0, 1))
    activity = min(enter*enter*(3-2*enter), leave*leave*(3-2*leave))
    right, up, forward, height = rig.right, rig.up, rig.forward, rig.height
    changes = defaultdict(list)
    tracks = set()

    def rotate(name, axis, degrees):
        node = rig.bones.get(name)
        if node is not None:
            changes[node].append((axis, float(degrees)*activity))
            tracks.add(node)

    if kind == 'scythe':
        # The modeled blade extends along -bind lateral. Rotating its plane to
        # the sagittal plane makes that extension point forward. Positive shaft
        # pitch then drives the concave (-shaft) edge downward through the cut,
        # instead of presenting the decorated convex spine to the target.
        grip_path = [(0, [-.12, -.09, .10]), (.28, [-.12, .025, .045]),
                     (.37, [-.12, .025, .045]), (.58, [-.10, -.105, .14]),
                     (.65, [-.10, -.105, .14]), (.91, [-.12, -.09, .10]), (1, [-.12, -.09, .10])]
        shaft_path = [(t, [0, math.cos(math.radians(pitch)), math.sin(math.radians(pitch))])
                      for t, pitch in [(0, 8), (.28, -36), (.37, -36),
                                       (.58, 72), (.65, 72), (.91, 8), (1, 8)]]
        normal_path = [(0, [1, 0, 0]), (1, [1, 0, 0])]
        twist = float(_motion_path(u, [(0, 0), (.30, -12), (.37, -12), (.58, 13), (.65, 13), (1, 0)]))
        lean = float(_motion_path(u, [(0, 0), (.30, -7), (.58, 14), (.65, 14), (1, 0)]))
        shift = float(_motion_path(u, [(0, 0), (.30, -.004), (.58, .006), (1, 0)]))
        step = .045
    elif kind == 'fan':
        grip_path = [(0, [-.13, -.12, .08]), (.28, [.035, -.025, .15]),
                     (.37, [.06, -.010, .17]), (.57, [-.25, -.10, .20]),
                     (.64, [-.25, -.10, .20]), (.80, [-.17, -.03, .13]),
                     (.92, [-.13, -.12, .08]), (1, [-.13, -.12, .08])]
        shaft_path = [(0, [0, 1, 0]), (.28, [-.35, .94, 0]),
                      (.37, [.30, .95, 0]), (.57, [-.84, .54, 0]),
                      (.64, [-.84, .54, 0]), (.80, [.35, .94, 0]),
                      (.92, [0, 1, 0]), (1, [0, 1, 0])]
        normal_path = [(0, [0, 0, 1]), (1, [0, 0, 1])]
        twist = float(_motion_path(u, [(0, 0), (.30, 19), (.37, 21), (.57, -23), (.64, -23), (.91, 0), (1, 0)]))
        lean = float(_motion_path(u, [(0, 0), (.30, -2), (.57, 6), (.64, 6), (1, 0)]))
        shift = float(_motion_path(u, [(0, 0), (.30, .008), (.57, -.015), (.64, -.015), (1, 0)]))
        step = .035
    elif kind == 'punch':
        # A compact guard draws the rear fist beside the ribs, then drives a
        # right cross toward the target. The opposite fist protects the jaw.
        grip_path = [(0, [-.10, -.07, .11]), (.17, [-.10, -.07, .11]),
                     (.31, [-.18, -.055, -.035]), (.49, [.015, -.035, .295]),
                     (.53, [.015, -.035, .295]), (.74, [-.10, -.07, .11]),
                     (1, [-.10, -.07, .11])]
        shaft_path = [(0, [0, 1, 0]), (1, [0, 1, 0])]
        normal_path = [(0, [0, 0, 1]), (1, [0, 0, 1])]
        twist = float(_motion_path(u, [(0, 0), (.17, -8), (.31, -24),
                                      (.49, 25), (.53, 25), (.74, -8), (1, 0)]))
        lean = float(_motion_path(u, [(0, 0), (.31, -5), (.49, 8), (.53, 8), (.74, 0), (1, 0)]))
        shift = float(_motion_path(u, [(0, 0), (.31, -.01), (.49, .012), (.53, .012), (1, 0)]))
        step = .04
    else:
        # The shaft changes from upright preparation to a deliberate aim at
        # an imaginary chest-height target, and remains there during casting.
        is_rapier = kind == 'rapier'
        reach = .265 if is_rapier else .215
        grip_path = [(0, [-.12, -.15, .07]), (.28, [-.11, -.025, .11]),
                     (.45, [-.10, -.055, reach]), (.71, [-.10, -.055, reach]),
                     (.92, [-.12, -.15, .07]), (1, [-.12, -.15, .07])]
        shaft_path = [(0, [0, 1, 0]), (.28, [0, .96, -.25]),
                      (.45, [0, .035, 1]), (.71, [0, .035, 1]),
                      (.92, [0, 1, 0]), (1, [0, 1, 0])]
        normal_path = [(0, [0, 0, 1]), (.28, [0, 0, 1]),
                       (.45, [0, -1, .035]), (.71, [0, -1, .035]),
                       (.92, [0, 0, 1]), (1, [0, 0, 1])]
        twist = float(_motion_path(u, [(0, 0), (.28, -10 if is_rapier else -4),
                                      (.45, 12 if is_rapier else 4), (.71, 12 if is_rapier else 4), (1, 0)]))
        lean = float(_motion_path(u, [(0, 0), (.28, -6), (.45, 10 if is_rapier else 7),
                                     (.71, 10 if is_rapier else 7), (1, 0)]))
        shift = 0.
        step = .065 if is_rapier else .05
    personality = _attack_personality(number, kind)
    if personality:
        grip_path = personality['grip']
        shaft_path = personality['shaft']
        normal_path = personality['normal']
        twist, lean, shift = _motion_path(u, personality['torso'])
        step = personality['step']
    rotate('Bip001 Pelvis', up, twist*.38)
    rotate('Bip001 Spine', up, twist*.62)
    rotate('Bip001 Spine', right, lean*.65)
    rotate('Bip001 Spine1', right, lean*.35)
    rotate('Bip001 Head', up, -twist*.55)
    rotate('Bip001 Head', right, -lean*.25)
    if number == 8:
        tick = float(_motion_path(u, [(0, 0), (.22, -13), (.38, -13),
                                      (.51, 13), (.62, 13), (1, 0)]))
        rotate('Bip001 Head', forward, tick)
        rotate('Bip001 Spine1', forward, -tick*.22)
    advance = float(_motion_path(u, [(0, 0), (.28, .005), (.57, .024), (.71, .024), (1, 0)]))
    displacement = height*activity*(right*shift+forward*advance-up*.018)
    rotations, translations = rig.pose(changes, displacement)
    world, world_q = rig.world(rotations, translations)
    shoulders = [rig.bones[f'Bip001 {s} UpperArm'] for s in ('L', 'R') if f'Bip001 {s} UpperArm' in rig.bones]
    anchor = world[shoulders, :3, 3].mean(axis=0) if shoulders else rig.pos[rig.bones['Bip001 Spine1']]
    relative = _motion_path(u, grip_path)
    planned_grip = anchor+height*(right*relative[0]+up*relative[1]+forward*relative[2])
    shaft_values = _motion_path(u, shaft_path)
    normal_values = _motion_path(u, normal_path)
    shaft = _unit(right*shaft_values[0]+up*shaft_values[1]+forward*shaft_values[2], up)
    normal = _unit(right*normal_values[0]+up*normal_values[1]+forward*normal_values[2], forward)
    hand = rig.bones.get('Bip001 R Hand')
    if hand is not None:
        offset = rig.palm_offset('R')
        rest_grip = rig.pos[hand]+offset
        planned_grip = rest_grip+(planned_grip-rest_grip)*activity
        orientation = _fist_rotation(rig, 'R') if kind == 'punch' else _weapon_rotation(rig, shaft, normal)
        prop_delta = _slerp(_IDENTITY, orientation, activity)
        wrist_target = planned_grip-_qrot(prop_delta, offset)
        hand_q = _qmul(prop_delta, rig.rest_world_q[hand])
        elbow = rig.bones.get('Bip001 R Forearm')
        pole = anchor-height*(right*.27+up*.20)+forward*(height*.055)
        if elbow is not None:
            pole = rig.pos[elbow]+(pole-rig.pos[elbow])*activity
        rig.arm_target(rotations, translations, 'R', wrist_target, pole, hand_q)
        world, world_q = rig.world(rotations, translations)
        actual_grip = world[hand, :3, 3]+_qrot(prop_delta, offset)
        curl_center = actual_grip-forward*(height*.045) if kind == 'punch' else actual_grip
        curl_axis = up if kind == 'punch' else _qrot(prop_delta, up)
        tracks.update(rig.finger_grip(rotations, translations, 'R', curl_center,
                                     curl_axis, activity, closed_fist=kind == 'punch'))
        left_hand = rig.bones.get('Bip001 L Hand')
        if left_hand is not None:
            left_delta = (prop_delta if kind == 'scythe' else
                          _slerp(_IDENTITY, _fist_rotation(rig, 'L'), activity) if kind == 'punch' else
                          _slerp(_IDENTITY, _axisq(forward, -18), activity))
            if kind == 'scythe':
                left_goal = actual_grip-_qrot(prop_delta, up)*(height*.14)
            elif 'left' in personality:
                relative_left = _motion_path(u, personality['left'])
                left_goal = anchor+height*(right*relative_left[0]+up*relative_left[1]+forward*relative_left[2])
            elif kind == 'fan':
                left_goal = anchor+height*(right*.11-up*.18+forward*.11)
            elif kind == 'rapier':
                left_goal = anchor+height*(right*.20-up*.10-forward*.10)
            elif kind == 'punch':
                left_goal = anchor+height*(right*.105+up*.045+forward*.10)
            else:
                circle = max(0., math.sin(math.pi*np.clip((u-.43)/.30, 0, 1)))
                left_goal = actual_grip+height*(right*.065-up*.045-forward*.035+up*.022*circle)
            left_offset = rig.palm_offset('L')
            left_rest = rig.pos[left_hand]+left_offset
            left_goal = left_rest+(left_goal-left_rest)*activity
            pole = anchor+height*(right*.26-up*.19+forward*.04)
            elbow = rig.bones.get('Bip001 L Forearm')
            if elbow is not None:
                pole = rig.pos[elbow]+(pole-rig.pos[elbow])*activity
            rig.arm_target(rotations, translations, 'L', left_goal-_qrot(left_delta, left_offset), pole,
                           _qmul(left_delta, rig.rest_world_q[left_hand]))
            if kind == 'scythe':
                world, world_q = rig.world(rotations, translations)
                actual_left = world[left_hand, :3, 3]+_qrot(left_delta, left_offset)
                tracks.update(rig.finger_grip(rotations, translations, 'L', actual_left,
                                             _qrot(prop_delta, up), activity*.85))
            elif kind == 'punch':
                world, world_q = rig.world(rotations, translations)
                actual_left = world[left_hand, :3, 3]+_qrot(left_delta, left_offset)
                tracks.update(rig.finger_grip(rotations, translations, 'L', actual_left-forward*(height*.045),
                                             up, activity, closed_fist=True))
    for side, sign in (('L', 1), ('R', -1)):
        foot = rig.bones.get(f'Bip001 {side} Foot')
        if foot is not None:
            target = rig.pos[foot]+height*activity*(right*(sign*.015)+forward*(step if side == 'L' else -step*.45))
            rig.leg_target(rotations, translations, side, target)
        for part in ('UpperArm', 'Forearm', 'Hand', 'Thigh', 'Calf', 'Foot'):
            node = rig.bones.get(f'Bip001 {side} {part}')
            if node is not None:
                tracks.add(node)
    if u <= _EPS or u >= 1-_EPS:
        rotations, translations = rig.q.copy(), rig.t.copy()
    return rotations, translations, tracks


def _guard_or_lose_pose(rig, u, kind, number, *, lose=False):
    """Protected stance with recovery, or a grounded defeat that stays held."""
    if lose:
        progress = float(np.clip(u/.80, 0, 1))
        activity = progress*progress*(3-2*progress)
    else:
        enter = float(np.clip(u/.22, 0, 1))
        leave = float(np.clip((1-u)/.22, 0, 1))
        activity = min(enter*enter*(3-2*enter), leave*leave*(3-2*leave))
    right, up, forward, height = rig.right, rig.up, rig.forward, rig.height
    changes, tracks = defaultdict(list), set()

    def rotate(name, axis, degrees):
        node = rig.bones.get(name)
        if node is not None:
            changes[node].append((axis, float(degrees)*activity))
            tracks.add(node)

    twist = (-6 if number % 2 else 6) if not lose else (-7 if number % 2 else 7)
    lean = 7 if not lose else 20+(number % 3)*4
    rotate('Bip001 Pelvis', up, twist*.45)
    rotate('Bip001 Spine', up, twist*.55)
    rotate('Bip001 Spine', right, lean*.65)
    rotate('Bip001 Spine1', right, lean*.35)
    rotate('Bip001 Head', up, -twist*.65)
    rotate('Bip001 Head', right, -3 if not lose else 20+(8 if number == 8 else 0))
    if lose:
        rotate('Bip001 Head', forward, -5 if number % 2 else 5)
    displacement = height*activity*(-up*(.092 if lose else .036)+forward*(.014 if lose else -.006))
    rotations, translations = rig.pose(changes, displacement)
    world, world_q = rig.world(rotations, translations)
    shoulders = [rig.bones[f'Bip001 {s} UpperArm'] for s in ('L', 'R') if f'Bip001 {s} UpperArm' in rig.bones]
    anchor = world[shoulders, :3, 3].mean(axis=0) if shoulders else rig.pos[rig.bones['Bip001 Spine']]
    normal = forward
    if lose:
        right_relative, left_relative = [-.15, -.21, .13], [.13, -.21, .13]
        shaft = up
        if kind == 'rapier':
            shaft = _unit(up*.60+forward*.80)
            left_relative = [.04, -.10, .16]
        elif kind == 'scythe':
            right_relative = [-.14, -.16, .10]
            left_relative = [.065, -.15, .14]
        elif kind == 'fan':
            right_relative = [-.025, .005, .13]
            left_relative = [.075, -.12, .14]
        elif kind == 'wand':
            shaft = _unit(-up*.35+forward*.94)
        elif kind == 'punch':
            right_relative, left_relative = [-.07, -.015, .15], [.07, -.015, .15]
        elif number == 5:
            left_relative = [.04, .015, .13]
        elif number in (4, 10):
            right_relative, left_relative = [-.045, -.10, .13], [.045, -.10, .13]
    else:
        right_relative, left_relative = [-.065, -.065, .17], [.065, -.055, .16]
        shaft = _unit(up*.72+forward*.69)
        if kind == 'rapier':
            right_relative, left_relative = [-.08, -.065, .16], [.15, -.11, .06]
            shaft = _unit(up*.50+forward*.86)
        elif kind == 'scythe':
            right_relative = [-.11, -.095, .16]
            shaft = _unit(right*.80+up*.60)
        elif kind == 'fan':
            right_relative, left_relative = [-.025, .025, .14], [.055, -.10, .13]
            shaft = up
        elif kind == 'punch':
            right_relative, left_relative = [-.09, .025, .13], [.09, .025, .14]
            shaft = up
        elif kind == 'wand':
            right_relative, left_relative = [-.10, -.02, .17], [.08, -.08, .14]
            shaft = _unit(-right*.30+up*.92+forward*.25)
        elif number == 8:
            right_relative, left_relative = [-.10, -.01, .14], [.10, -.01, .14]
        elif number == 10:
            right_relative, left_relative = [-.075, .015, .17], [.075, .015, .17]
    prop_delta = _slerp(_IDENTITY, _fist_rotation(rig, 'R') if kind == 'punch' else
                        _weapon_rotation(rig, shaft, normal), activity)
    actual_grip = None
    for side, relative in (('R', right_relative), ('L', left_relative)):
        hand = rig.bones.get(f'Bip001 {side} Hand')
        if hand is None:
            continue
        sign = 1 if side == 'L' else -1
        offset = rig.palm_offset(side)
        delta = (prop_delta if side == 'R' or (kind == 'scythe' and not lose) else
                 _slerp(_IDENTITY, _fist_rotation(rig, side), activity) if kind == 'punch' else
                 _slerp(_IDENTITY, _axisq(forward, -sign*22), activity))
        goal = anchor+height*(right*relative[0]+up*relative[1]+forward*relative[2])
        if side == 'L' and kind == 'scythe' and not lose and actual_grip is not None:
            goal = actual_grip-_qrot(prop_delta, up)*height*.14
            rest_grip = rig.pos[hand]+offset
            goal = rest_grip+(goal-rest_grip)*activity
        else:
            rest_grip = rig.pos[hand]+offset
            goal = rest_grip+(goal-rest_grip)*activity
        pole = anchor+height*(right*sign*.26-up*.19+forward*.025)
        elbow = rig.bones.get(f'Bip001 {side} Forearm')
        if elbow is not None:
            pole = rig.pos[elbow]+(pole-rig.pos[elbow])*activity
        rig.arm_target(rotations, translations, side, goal-_qrot(delta, offset), pole,
                       _qmul(delta, rig.rest_world_q[hand]))
        world, world_q = rig.world(rotations, translations)
        actual = world[hand, :3, 3]+_qrot(delta, offset)
        if side == 'R':
            actual_grip = actual
        if side == 'R' or kind == 'punch' or (kind == 'scythe' and not lose):
            tracks.update(rig.finger_grip(rotations, translations, side,
                                         actual-forward*height*.045 if kind == 'punch' else actual,
                                         up if kind == 'punch' else _qrot(delta, up),
                                         activity, closed_fist=kind == 'punch'))
    for side, sign in (('L', 1), ('R', -1)):
        foot = rig.bones.get(f'Bip001 {side} Foot')
        if foot is not None:
            pitch = 35*activity if lose and side == 'R' else 0
            target = rig.pos[foot]+height*activity*(right*sign*.012+forward*((.052 if side == 'L' else -.048) if lose else 0))
            toe = rig.bones.get(f'Bip001 {side} Toe0')
            if pitch and toe is not None:
                offset = rig.pos[toe]-rig.pos[foot]
                target += offset-_qrot(_axisq(right, pitch), offset)+up*height*.004*activity
            rig.leg_target(rotations, translations, side, target, pitch)
        for part in ('UpperArm', 'Forearm', 'Hand', 'Thigh', 'Calf', 'Foot'):
            node = rig.bones.get(f'Bip001 {side} {part}')
            if node is not None:
                tracks.add(node)
    if u <= _EPS or (not lose and u >= 1-_EPS):
        rotations, translations = rig.q.copy(), rig.t.copy()
    return rotations, translations, tracks


def _run_arm_pose(rig, rotations, translations, phase, kind):
    """Tucked upper arms, low elbows and opposite forward/back wrist swings.

    Imported bind arms point sideways, so pitching them around the anatomical
    lateral axis mostly twists them. Palm/elbow IK establishes the running
    stance directly and keeps an upright carried prop outside the torso.
    """
    world, _ = rig.world(rotations, translations)
    shoulders = [rig.bones[f'Bip001 {s} UpperArm'] for s in ('L', 'R') if f'Bip001 {s} UpperArm' in rig.bones]
    if not shoulders:
        return set()
    right, up, forward, height = rig.right, rig.up, rig.forward, rig.height
    tracks = set()
    for side, sign in (('L', 1), ('R', -1)):
        hand = rig.bones.get(f'Bip001 {side} Hand')
        upper = rig.bones.get(f'Bip001 {side} UpperArm')
        fore = rig.bones.get(f'Bip001 {side} Forearm')
        if None in (hand, upper, fore):
            continue
        swing = -sign*math.cos(phase)
        thigh = rig.bones.get(f'Bip001 {side} Thigh')
        knee = rig.bones.get(f'Bip001 {side} Calf')
        if thigh is not None and knee is not None:
            leg = world[knee, :3, 3]-world[thigh, :3, 3]
            knee_drive = math.degrees(math.atan2(float(leg @ forward), float(-leg @ up)))
            swing = -float(np.clip((knee_drive-10)/45, -1, 1))
        shoulder = world[upper, :3, 3]
        length1 = np.linalg.norm(rig.pos[fore]-rig.pos[upper])
        length2 = np.linalg.norm(rig.pos[hand]-rig.pos[fore])
        reach = math.sqrt(length1*length1+length2*length2)
        pump = _axisq(right, -swing*27)
        direction = _unit(_qrot(pump, -up*.63+forward*.77)+right*sign*.12)
        grip = shoulder+direction*reach
        pole = shoulder+_qrot(pump, height*(-up*.235-forward*.08))+right*sign*height*.025
        offset = rig.palm_offset(side)
        # Preserve the upright bind orientation of rigid carried props. The
        # free hand forms a relaxed fist with forward-facing knuckles.
        delta = (_IDENTITY if side == 'R' and kind != 'punch' else
                 _qmul(_axisq(up, -sign*15), _fist_rotation(rig, side)))
        rig.arm_target(rotations, translations, side, grip-_qrot(delta, offset), pole,
                       _qmul(delta, rig.rest_world_q[hand]))
        world, _ = rig.world(rotations, translations)
        actual = world[hand, :3, 3]+_qrot(delta, offset)
        fist = side == 'L' or kind == 'punch'
        tracks.update(rig.finger_grip(rotations, translations, side,
                                     actual-forward*height*.045 if fist else actual,
                                     up, .90 if fist else .85, closed_fist=fist))
        for part in ('UpperArm', 'Forearm', 'Hand'):
            node = rig.bones.get(f'Bip001 {side} {part}')
            if node is not None:
                tracks.add(node)
    return tracks


def add_animations(doc: dict, append_accessor: Callable, character_id, attack_style='magic', *, clip_names=None) -> list:
    """Add seven animation clips and return the same list stored in the document.

    ``attack_style`` accepts ``magic``/``cast``/``charm``, ``wand``/``staff``, ``scythe``/``sword``, ``rapier``
    (grounded thrust), ``fan`` (open-fan flourish), ``kick`` or ``melee``/``punch``.
    Characters 11-14 use ``daggers``, ``fox_baton``, ``witch_staff`` and ``bouquet``
    with independent prop-aware Idle/Walk/Run/Attack/Defend/Victory/Lose poses.
    Unknown styles use a two-handed casting gesture.
    Every channel targets the selected body skeleton or a custom HairAccessory
    node in its hierarchy. Missing optional limb/accessory bones are skipped.
    ``extras.loop`` marks Idle, Walk and Run; glTF viewers choose playback looping.
    Defend enters, holds and recovers. Lose holds its terminal defeated pose.
    ``clip_names`` optionally limits generation, for animation-only refreshes.
    """
    rig = _Rig(doc)
    number = _character_number(character_id)
    style = str(attack_style).lower()
    weapon_kind = (style if style in _REFERENCE_STYLES.values() else
                   'scythe' if style in ('scythe', 'sword', 'slash') else
                   'fan' if style in ('fan', 'flourish') else
                   'rapier' if style in ('rapier', 'thrust', 'lunge') else
                   'wand' if style in ('wand', 'staff') or (number == 6 and style in ('magic', 'cast')) else
                   'charm' if style in ('magic', 'cast', 'charm') else
                   'punch' if style in ('punch', 'melee') else None)
    clips = []
    durations = (('Idle', 3.2), ('Walk', 1.2), ('Run', .8),
                 ('Attack', _ATTACK_DURATIONS.get(number, 1.6)),
                 ('Defend', 1.8), ('Victory', 2.8), ('Lose', 2.4))
    if number in _REFERENCE_STYLES:
        durations = tuple((name, {11: {'Walk': 1.10, 'Victory': 3.05},
                                 12: {'Walk': 1.05, 'Victory': 3.30},
                                 13: {'Walk': 1.55, 'Run': .92, 'Victory': 3.65},
                                 14: {'Walk': 1.65, 'Run': 1.02, 'Victory': 3.75}}[number].get(name, duration))
                          for name, duration in durations)
    selected = set(clip_names) if clip_names is not None else {name for name, _ in durations}
    if selected - {name for name, _ in durations}:
        raise ValueError('Unknown clip name requested.')
    for clip_name, duration in durations:
        if clip_name not in selected:
            continue
        times = np.linspace(0, duration, int(round(duration*30))+1, dtype=np.float64)
        # Explicit hold-boundary keys keep interpolated playback settled from
        # the advertised time, even when that time falls between 30 fps keys.
        boundaries = (.80,) if clip_name == 'Lose' else (.22, .78) if clip_name == 'Defend' else ()
        if boundaries:
            times = np.unique(np.r_[times, np.asarray(boundaries)*duration])
        rotation_samples = defaultdict(list)
        translation_samples = []
        for frame, time in enumerate(times):
            u = time/duration
            phase = 2*math.pi*u
            changes = defaultdict(list)

            def rotate(bone, axis, degrees):
                node = rig.bones.get(bone) if isinstance(bone, str) else bone
                if node is not None:
                    changes[node].append((axis, degrees))

            right, up, forward = rig.right, rig.up, rig.forward
            displacement = np.zeros(3)
            if clip_name == 'Idle':
                breath = math.sin(phase)
                rotate('Bip001 Spine', right, 1.1*breath)
                rotate('Bip001 Spine1', right, -.5*breath)
                rotate('Bip001 Head', forward, 1.2*math.sin(phase+.4))
                rotate('Bip001 Head', up, 1.4*math.sin(phase))
                for side, sign in (('L', -1), ('R', 1)):
                    rotate(f'Bip001 {side} UpperArm', forward, sign*.8*breath)
                    rotate(f'Bip001 {side} Forearm', right, -.8*breath)
                displacement = up*(rig.height*.0022*breath)
            elif clip_name == 'Walk':
                rotate('Bip001 Pelvis', forward, 2.1*math.sin(phase))
                rotate('Bip001 Pelvis', up, 3.0*math.cos(phase))
                rotate('Bip001 Spine', up, -4.0*math.cos(phase))
                rotate('Bip001 Spine1', right, 2.2)
                rotate('Bip001 Head', up, 1.0*math.cos(phase))
                for side, sign in (('L', 1), ('R', -1)):
                    rotate(f'Bip001 {side} UpperArm', right, 15*sign*math.cos(phase))
                    rotate(f'Bip001 {side} Forearm', right, -6-4*max(0., -sign*math.cos(phase)))
                displacement = up*(rig.height*(-.016+.005*(1-math.cos(phase*2))))
            elif clip_name == 'Run':
                rotate('Bip001 Pelvis', forward, 4.0*math.sin(phase))
                rotate('Bip001 Pelvis', up, 5.5*math.cos(phase))
                rotate('Bip001 Spine', up, -7.0*math.cos(phase))
                rotate('Bip001 Spine', right, 9.0)
                rotate('Bip001 Spine1', right, 4.5)
                rotate('Bip001 Head', right, -7.0)
                rotate('Bip001 Head', up, 1.5*math.cos(phase))
                aerial_bounce = .5*(1+math.cos(4*math.pi*(u-.43)))
                displacement = up*(rig.height*(-.026+.029*aerial_bounce))
            elif clip_name == 'Attack':
                wind = _envelope(u, .05, .30, .58)
                strike = _envelope(u, .30, .57, .94)
                if style in ('rapier', 'thrust', 'lunge'):
                    # The delivered rapier points up in the rest grip. Raising
                    # the elbow and counter-rotating the wrist aims its blade
                    # forward during the thrust instead of behind the caster.
                    rotate('Bip001 Pelvis', up, -8*wind+9*strike)
                    rotate('Bip001 Spine', up, -10*wind+6*strike)
                    rotate('Bip001 Spine', right, -3*wind+5*strike)
                    rotate('Bip001 R UpperArm', right, -35*wind-67*strike)
                    rotate('Bip001 R UpperArm', forward, -6*wind-5*strike)
                    rotate('Bip001 R Forearm', right, -48*wind+10*strike)
                    rotate('Bip001 R Hand', right, 105*wind+142*strike)
                    rotate('Bip001 R Hand', up, 10*wind-14*strike)
                    rotate('Bip001 L UpperArm', right, 14*wind+23*strike)
                    rotate('Bip001 L UpperArm', forward, 12*wind+24*strike)
                    rotate('Bip001 L Forearm', right, -26*wind-19*strike)
                    rotate('Bip001 Head', up, 5*wind-9*strike)
                elif style in ('fan', 'flourish'):
                    # An open fan sweeps toward the opposite shoulder, then
                    # turns out with a wrist flourish; the free hand balances
                    # the gesture. Hand counter-pitch keeps its face visible.
                    rotate('Bip001 Pelvis', up, -5*wind+8*strike)
                    rotate('Bip001 Spine', up, -8*wind+12*strike)
                    rotate('Bip001 R UpperArm', right, -32*wind-58*strike)
                    rotate('Bip001 R UpperArm', up, 15*wind+42*strike)
                    rotate('Bip001 R Forearm', right, -38*wind-17*strike)
                    rotate('Bip001 R Hand', right, 70*wind+75*strike)
                    rotate('Bip001 R Hand', up, -2*wind-62*strike)
                    rotate('Bip001 R Hand', forward, -20*wind+48*strike+15*math.sin(4*math.pi*u)*strike)
                    rotate('Bip001 L UpperArm', right, -15*wind-30*strike)
                    rotate('Bip001 L UpperArm', forward, 10*strike)
                    rotate('Bip001 L Forearm', right, -35*wind-38*strike)
                    rotate('Bip001 Head', up, 5*wind-8*strike)
                elif style in ('scythe', 'sword', 'slash'):
                    rotate('Bip001 Pelvis', up, -13*wind+19*strike)
                    rotate('Bip001 Spine', up, -17*wind+22*strike)
                    rotate('Bip001 Spine1', right, 5*strike)
                    rotate('Bip001 R UpperArm', right, -52*wind+30*strike)
                    rotate('Bip001 R UpperArm', forward, -32*wind+22*strike)
                    rotate('Bip001 R Forearm', right, -37*wind-15*strike)
                    rotate('Bip001 R Hand', up, -24*wind+20*strike)
                    rotate('Bip001 L UpperArm', right, -22*wind-32*strike)
                    rotate('Bip001 L Forearm', right, -28*wind-23*strike)
                    rotate('Bip001 L Thigh', right, -7*strike)
                    rotate('Bip001 L Calf', right, 10*strike)
                    rotate('Bip001 R Thigh', right, 6*strike)
                elif style in ('melee', 'punch', 'kick'):
                    rotate('Bip001 Spine', up, -18*wind+18*strike)
                    rotate('Bip001 R UpperArm', right, -22*wind-67*strike)
                    rotate('Bip001 R Forearm', right, -45*wind+8*strike)
                    rotate('Bip001 L UpperArm', right, -30*wind-24*strike)
                    rotate('Bip001 L Forearm', right, -40*(wind+strike))
                    if style == 'kick':
                        rotate('Bip001 R Thigh', right, -60*strike)
                        rotate('Bip001 R Calf', right, 42*wind+10*strike)
                        rotate('Bip001 R Foot', right, 23*strike)
                    else:
                        rotate('Bip001 L Thigh', right, -8*strike)
                        rotate('Bip001 L Calf', right, 10*strike)
                else:
                    rotate('Bip001 Spine', right, -5*wind+7*strike)
                    rotate('Bip001 Head', right, -5*wind+4*strike)
                    for side, sign in (('L', 1), ('R', -1)):
                        rotate(f'Bip001 {side} UpperArm', right, -22*wind-60*strike)
                        rotate(f'Bip001 {side} UpperArm', forward, sign*18*wind)
                        rotate(f'Bip001 {side} Forearm', right, -48*wind+10*strike)
                        rotate(f'Bip001 {side} Hand', forward, sign*15*strike)
                displacement = up*(-rig.height*.012*strike)
                if style in ('rapier', 'thrust', 'lunge'):
                    displacement += forward*(rig.height*.035*strike)
                elif style in ('fan', 'flourish'):
                    displacement = np.zeros(3)
            elif clip_name == 'Victory':
                cheer = _envelope(u, .06, .38, .95)
                wave = math.sin(6*math.pi*u)*cheer
                variant = number % 3
                if variant == 1:
                    # A raised right arm and wrist wave; left hand on the hip.
                    rotate('Bip001 R UpperArm', forward, -115*cheer)
                    rotate('Bip001 R Forearm', forward, -24*cheer)
                    rotate('Bip001 R Hand', right, 22*wave)
                    rotate('Bip001 L UpperArm', forward, 18*cheer)
                    rotate('Bip001 L Forearm', right, -40*cheer)
                    rotate('Bip001 Head', forward, -7*cheer)
                elif variant == 2:
                    for side, sign in (('L', 1), ('R', -1)):
                        rotate(f'Bip001 {side} UpperArm', forward, sign*105*cheer)
                        rotate(f'Bip001 {side} Forearm', right, -18*cheer)
                        rotate(f'Bip001 {side} Hand', right, sign*9*wave)
                    rotate('Bip001 Spine1', right, -6*cheer)
                    displacement = up*(rig.height*.012*max(0., math.sin(4*math.pi*u))*cheer)
                else:
                    # A courteous bow with arms brought toward the chest.
                    rotate('Bip001 Spine', right, 20*cheer)
                    rotate('Bip001 Spine1', right, 12*cheer)
                    rotate('Bip001 Head', right, 8*cheer)
                    for side, sign in (('L', 1), ('R', -1)):
                        rotate(f'Bip001 {side} UpperArm', right, -23*cheer)
                        rotate(f'Bip001 {side} UpperArm', forward, -sign*10*cheer)
                        rotate(f'Bip001 {side} Forearm', right, -56*cheer)
                rotate('Bip001 Pelvis', forward, 3*math.sin(phase)*cheer)
            for accessory_index, node in enumerate(rig.accessories):
                amplitude = 5.0 if clip_name == 'Run' else 2.8 if clip_name == 'Walk' else 1.2
                amplitude *= 1 if clip_name in ('Idle', 'Walk', 'Run') else math.sin(math.pi*u)**2
                rotate(node, right, amplitude*math.sin(phase+accessory_index*.7))
                rotate(node, forward, .6*amplitude*math.sin(phase+accessory_index*1.1))
            rotations, translations = rig.pose(changes, displacement)
            if number in _REFERENCE_STYLES:
                rotations, translations, personality_tracks = _reference_character_pose(rig, u, clip_name, number)
                for node in personality_tracks:
                    changes[node]
            elif clip_name == 'Attack' and weapon_kind:
                rotations, translations, weapon_tracks = _weapon_attack_pose(rig, u, weapon_kind, number)
                for node in weapon_tracks:
                    changes[node]
            elif clip_name in ('Defend', 'Lose'):
                rotations, translations, guard_tracks = _guard_or_lose_pose(rig, u, weapon_kind, number,
                                                                            lose=clip_name == 'Lose')
                for node in guard_tracks:
                    changes[node]
            elif clip_name == 'Run':
                rig.run_leg_ik(rotations, translations, 'L', u)
                rig.run_leg_ik(rotations, translations, 'R', u+.5)
                for index in _run_arm_pose(rig, rotations, translations, phase, weapon_kind):
                    changes[index]
                for side in ('L', 'R'):
                    for part in ('Thigh', 'Calf', 'Foot'):
                        index = rig.bones.get(f'Bip001 {side} {part}')
                        if index is not None:
                            changes[index]
            elif clip_name == 'Walk':
                rig.leg_ik(rotations, translations, 'L', phase)
                rig.leg_ik(rotations, translations, 'R', phase+math.pi)
                for side in ('L', 'R'):
                    for part in ('Thigh', 'Calf', 'Foot'):
                        index = rig.bones.get(f'Bip001 {side} {part}')
                        if index is not None:
                            changes[index]  # Include the IK output in tracks.
            elif clip_name == 'Attack' and style != 'kick':
                # A casting/punching crouch lowers the pelvis; hold both ankle
                # targets on their bind floor instead of lowering the soles
                # through the ground with the torso's weight shift.
                for side in ('L', 'R'):
                    foot = rig.bones.get(f'Bip001 {side} Foot')
                    if foot is not None:
                        rig.leg_target(rotations, translations, side, rig.pos[foot])
                    for part in ('Thigh', 'Calf', 'Foot'):
                        index = rig.bones.get(f'Bip001 {side} {part}')
                        if index is not None:
                            changes[index]
                # Match the exact original joint pose at the one-shot ends.
                if frame in (0, len(times)-1):
                    rotations = rig.q.copy()
            for node in changes:
                rotation_samples[node].append(rotations[node])
            translation_samples.append(translations[rig.root] if rig.root is not None else np.zeros(3))
        loop = clip_name in ('Idle', 'Walk', 'Run')
        clip = {'name': clip_name, 'samplers': [], 'channels': [],
                'extras': {'loop': loop, 'inPlace': True, 'durationSeconds': duration,
                           'characterId': str(character_id), 'procedural': True}}
        if clip_name == 'Attack':
            clip['extras']['attackStyle'] = style
            clip['extras']['action'] = _ATTACK_ACTIONS.get(number, f'{weapon_kind or style} attack')
            clip['extras']['description'] = clip['extras']['action']
            if weapon_kind:
                clip['extras'].update(weaponAware=True, weaponKind=weapon_kind, weaponGrip='Palm center',
                                      weaponBind={'shaftAxis': rig.up.tolist(), 'faceNormal': rig.forward.tolist()},
                                      impactWindow=[.38, .58] if weapon_kind == 'scythe' else
                                                   [.45, .71] if weapon_kind in ('wand', 'rapier', 'charm') else
                                                   [.43, .58] if weapon_kind == 'punch' else [.39, .64])
            if weapon_kind == 'scythe':
                clip['extras'].update(cuttingEdgeBindDirection=(-rig.up).tolist(),
                                      cuttingEdge='Inner concave edge', strikePlane='Overhead reaping arc')
        elif clip_name == 'Run':
            clip['extras'].update(gait='Run: short stance, heel recovery, knee drive and aerial phase',
                                  dutyFactor=.36, flightPhase=True, independentOfWalk=True)
        elif clip_name == 'Defend':
            clip['extras'].update(action=f'{weapon_kind or "palm"} guard: enter, hold and recover',
                                  holdWindowSeconds=[duration*.22, duration*.78])
        elif clip_name == 'Lose':
            clip['extras'].update(action='Grounded defeated crouch with lowered head and held finish',
                                  terminalPoseHeld=True, holdWindowSeconds=[duration*.80, duration])
        if number in _REFERENCE_STYLES:
            action = (_ATTACK_ACTIONS[number] if clip_name == 'Attack' else
                      _REFERENCE_ACTIONS[number].get(clip_name, clip['extras'].get('action', clip_name)))
            clip['extras'].update(action=action, description=action, personalityMotion=True,
                                  propGrip='Both palms' if number == 11 else 'Right palm',
                                  propBind={'shaftAxis': rig.up.tolist(), 'faceNormal': rig.forward.tolist()})
            if clip_name == 'Walk':
                clip['extras'].update(gait=action, independentPersonality=True)
            elif clip_name == 'Attack':
                clip['extras']['impactWindow'] = {11: [.35, .69], 12: [.48, .70],
                                                 13: [.53, .76], 14: [.48, .74]}[number]
        input_accessor = append_accessor(times.astype('<f4'), 'SCALAR', 5126)

        def channel(node, path, samples, kind):
            array = np.asarray(samples, dtype=np.float64)
            if loop:
                array[-1] = array[0]
            if path == 'rotation':
                array /= np.maximum(np.linalg.norm(array, axis=1, keepdims=True), _EPS)
                for i in range(1, len(array)):
                    if np.dot(array[i-1], array[i]) < 0:
                        array[i] *= -1
                if number in _REFERENCE_STYLES:
                    # Wrist/forearm IK can finish with the equivalent negative
                    # bind quaternion after a flourish. glTF takes the shortest
                    # quaternion arc; keep the explicit rest/loop contract exact.
                    if loop:
                        array[-1] = array[0]
                    elif clip_name != 'Lose':
                        array[0] = array[-1] = rig.q[node]
                if not np.allclose(np.linalg.norm(array, axis=1), 1, atol=1e-6):
                    raise ValueError(f'Invalid quaternion in {clip_name}.')
            if not np.isfinite(array).all():
                raise ValueError(f'Non-finite animation output in {clip_name}.')
            if 'matrix' in rig.nodes[node]:
                rig.nodes[node].pop('matrix')
                rig.nodes[node]['translation'] = rig.t[node].tolist()
                rig.nodes[node]['rotation'] = rig.q[node].tolist()
                rig.nodes[node]['scale'] = rig.s[node].tolist()
            output = append_accessor(array.astype('<f4'), kind, 5126)
            sampler = len(clip['samplers'])
            clip['samplers'].append({'input': input_accessor, 'output': output, 'interpolation': 'LINEAR'})
            clip['channels'].append({'sampler': sampler, 'target': {'node': int(node), 'path': path}})

        for node, samples in sorted(rotation_samples.items()):
            channel(node, 'rotation', samples, 'VEC4')
        if rig.root is not None:
            channel(rig.root, 'translation', translation_samples, 'VEC3')
        clips.append(clip)
    doc['animations'] = clips
    return clips


def _slerp(a, b, weight):
    """Shortest-path quaternion interpolation, with finite normalized output."""
    a, b = _qnorm(a), _qnorm(b)
    cosine = float(np.dot(a, b))
    if cosine < 0:
        b, cosine = -b, -cosine
    if cosine > .9995:
        return _qnorm(a+(b-a)*weight)
    angle = math.acos(float(np.clip(cosine, -1, 1)))
    return _qnorm((math.sin((1-weight)*angle)*a+math.sin(weight*angle)*b)/math.sin(angle))


def _native_samples(source_accessor, sampler, path, sample_times):
    times = np.asarray(source_accessor(sampler['input']), dtype=np.float64).reshape(-1)
    width = 4 if path == 'rotation' else 3
    values = np.asarray(source_accessor(sampler['output']), dtype=np.float64).reshape(-1, width)
    interpolation = sampler.get('interpolation', 'LINEAR')
    if not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError('Donor animation contains non-finite keys.')
    if not len(times) or np.any(np.diff(times) <= 0):
        raise ValueError('Donor animation times must be strictly increasing.')
    divisor = 3 if interpolation == 'CUBICSPLINE' else 1
    if len(values) != len(times)*divisor:
        raise ValueError('Donor animation sampler has inconsistent key counts.')
    if interpolation == 'CUBICSPLINE':
        values = values.reshape(len(times), 3, width)
    elif np.array_equal(values, np.broadcast_to(values[0], values.shape)):
        constant = _qnorm(values[0]) if path == 'rotation' else values[0]
        return np.repeat(constant[None, :], len(sample_times), axis=0)
    result = []
    for time in sample_times:
        if len(times) == 1 or time <= times[0]:
            value = values[0, 1] if interpolation == 'CUBICSPLINE' else values[0]
        elif time >= times[-1]:
            value = values[-1, 1] if interpolation == 'CUBICSPLINE' else values[-1]
        else:
            right = int(np.searchsorted(times, time, side='right'))
            left = right-1
            delta = times[right]-times[left]
            weight = float((time-times[left])/delta)
            if interpolation == 'STEP':
                value = values[left]
            elif interpolation == 'CUBICSPLINE':
                p0, p1 = values[left, 1], values[right, 1]
                m0, m1 = delta*values[left, 2], delta*values[right, 0]
                square, cube = weight*weight, weight*weight*weight
                value = ((2*cube-3*square+1)*p0+(cube-2*square+weight)*m0
                         +(-2*cube+3*square)*p1+(cube-square)*m1)
            elif path == 'rotation':
                value = _slerp(values[left], values[right], weight)
            else:
                value = values[left]*(1-weight)+values[right]*weight
        result.append(_qnorm(value) if path == 'rotation' else value)
    return np.asarray(result, dtype=np.float64)


def _native_clip(source_doc, priorities, node_map):
    animations = source_doc.get('animations', [])

    def usable(animation):
        return any(c.get('target', {}).get('node') in node_map
                   and c['target'].get('path') in ('rotation', 'translation')
                   for c in animation.get('channels', []))

    for wanted in priorities:
        exact = [a for a in animations if a.get('name', '').lower() == wanted.lower() and usable(a)]
        if exact:
            return exact[0]
    for wanted in priorities:
        variants = [a for a in animations if a.get('name', '').lower().startswith(wanted.lower()) and usable(a)]
        if variants:
            return sorted(variants, key=lambda a: a.get('name', ''))[0]
    return None


def add_donor_animations(doc: dict, append_accessor: Callable, source_doc: dict,
                         source_accessor: Callable, source_node_map: dict,
                         character_id, attack_style='magic') -> dict:
    """Preserve native body/cloth motion in Idle, Walk and Victory.

    Call after :func:`add_animations`. ``source_accessor(index)`` reads a donor
    accessor as a NumPy array, and ``source_node_map`` maps exact donor node IDs
    to the copied master-rig IDs. Never map nodes using only shared bone names:
    replacement hair can contain names also used by the original body donor.

    Selects Cafe_Idle/Formation_Idle, Cafe_Walk/Move_Ing and
    Victory_Start/Cafe_Reaction (including named variants). Missing native clips
    retain their procedural equivalents. Custom Attack is always retained.
    All mapped rotation/translation tracks are resampled at 30 fps, including
    skirt, coat, ribbon and hair joints, preserving their native timing together.
    Scale, weights and other visibility/material paths are never copied.

    Source/target rest-parent bases retarget each local transform. Root tracks
    lose constant horizontal offsets and linear travel while retaining vertical
    bounce and oscillatory lateral sway. Idle/Walk are corrected continuously
    to close exactly. Victory fades from/to the target bind/rest pose. Animated
    matrix nodes are converted to TRS, and every quaternion is normalized.
    Returns ``{'Idle': source_name_or_None, 'Walk': ..., 'Victory': ...}``.
    """
    if not doc.get('animations'):
        add_animations(doc, append_accessor, character_id, attack_style)
    node_map = {int(source): int(target) for source, target in source_node_map.items()
                if 0 <= int(source) < len(source_doc.get('nodes', []))
                and 0 <= int(target) < len(doc.get('nodes', []))}
    selected = {'Idle': None, 'Walk': None, 'Victory': None}
    if not node_map or not source_doc.get('animations'):
        return selected
    source_rig, target_rig = _Rig(source_doc), _Rig(doc)
    root_chain = set()
    ancestor = source_rig.root
    while ancestor is not None and ancestor >= 0:
        root_chain.add(int(ancestor))
        ancestor = int(source_rig.parent[ancestor])
    priorities = {'Idle': ('Cafe_Idle', 'Formation_Idle'),
                  'Walk': ('Cafe_Walk', 'Move_Ing'),
                  'Victory': ('Victory_Start', 'Cafe_Reaction')}
    replacements = {}
    for name, preferred in priorities.items():
        native = _native_clip(source_doc, preferred, node_map)
        if native is None:
            continue
        channels = [c for c in native.get('channels', [])
                    if c.get('target', {}).get('node') in node_map
                    and c['target'].get('path') in ('rotation', 'translation')]
        input_times = [np.asarray(source_accessor(native['samplers'][c['sampler']]['input']), dtype=float).reshape(-1)
                       for c in channels]
        if not input_times or any(not len(t) for t in input_times):
            continue
        begin = min(float(t[0]) for t in input_times)
        end = max(float(t[-1]) for t in input_times)
        duration = end-begin
        if not math.isfinite(duration) or duration <= _EPS:
            continue
        times = np.linspace(0, duration, max(2, int(round(duration*30))+1))
        progress = times/duration
        smooth = progress*progress*(3-2*progress)
        if name == 'Victory':
            fade_in = np.clip(progress/.12, 0, 1)
            fade_out = np.clip((1-progress)/.20, 0, 1)
            fade_in = fade_in*fade_in*(3-2*fade_in)
            fade_out = fade_out*fade_out*(3-2*fade_out)
            fade = np.minimum(fade_in, fade_out)
        loop = name in ('Idle', 'Walk')
        clip = {'name': name, 'channels': [], 'samplers': [],
                'extras': {'loop': loop, 'inPlace': True, 'durationSeconds': duration,
                           'characterId': str(character_id), 'procedural': False,
                           'nativeSourceClip': native.get('name', ''),
                           'secondaryMotion': 'Native donor skeleton and cloth timing'}}
        input_accessor = append_accessor(times.astype('<f4'), 'SCALAR', 5126)
        seen = set()
        for channel in channels:
            source_node = int(channel['target']['node'])
            target_node = node_map[source_node]
            path = channel['target']['path']
            identity = (target_node, path)
            if identity in seen:
                continue
            seen.add(identity)
            values = _native_samples(source_accessor, native['samplers'][channel['sampler']], path, times+begin)
            source_parent = source_rig.parent[source_node]
            target_parent = target_rig.parent[target_node]
            source_parent_q = source_rig.rest_world_q[source_parent] if source_parent >= 0 else _IDENTITY
            target_parent_q = target_rig.rest_world_q[target_parent] if target_parent >= 0 else _IDENTITY
            if path == 'rotation':
                basis = _qmul(_qinv(target_parent_q), source_parent_q)
                source_inverse = _qinv(source_rig.q[source_node])
                exact_copy = (abs(np.dot(basis, _IDENTITY)) > 1-1e-12
                              and abs(np.dot(source_rig.q[source_node], target_rig.q[target_node])) > 1-1e-12)
                if not exact_copy:
                    values = np.asarray([_qnorm(_qmul(_qmul(_qmul(basis, _qmul(v, source_inverse)),
                                                                _qinv(basis)), target_rig.q[target_node]))
                                         for v in values])
                for i in range(1, len(values)):
                    if np.dot(values[i-1], values[i]) < 0:
                        values[i] *= -1
                if loop:
                    # Distribute seam correction over the cycle rather than
                    # inserting a large discontinuity in its final frame.
                    correction = _qmul(_qinv(values[-1]), values[0])
                    values = np.asarray([_qnorm(_qmul(v, _slerp(_IDENTITY, correction, s)))
                                         for v, s in zip(values, smooth)])
                    values[-1] = values[0]
                else:
                    values = np.asarray([_slerp(target_rig.q[target_node], v, f)
                                         for v, f in zip(values, fade)])
                    values[0] = values[-1] = target_rig.q[target_node]
                for i in range(1, len(values)):
                    if np.dot(values[i-1], values[i]) < 0:
                        values[i] *= -1
                # A native prop may turn through a full revolution, making
                # the final equivalent quaternion negative after continuity
                # cleanup. Canonicalize the endpoints for exact clip seams;
                # glTF quaternion interpolation still takes the short arc.
                if loop:
                    values[-1] = values[0]
                else:
                    values[0] = values[-1] = target_rig.q[target_node]
            else:
                source_basis = (source_rig.rest_world[source_parent, :3, :3]
                                if source_parent >= 0 else np.eye(3))
                target_basis = (target_rig.rest_world[target_parent, :3, :3]
                                if target_parent >= 0 else np.eye(3))
                world_delta = (values-source_rig.t[source_node]) @ source_basis.T
                if source_node in root_chain:
                    up = target_rig.up
                    horizontal = world_delta-np.outer(world_delta @ up, up)
                    travel = horizontal[0]+np.outer(progress, horizontal[-1]-horizontal[0])
                    world_delta -= travel
                values = target_rig.t[target_node]+world_delta @ np.linalg.inv(target_basis).T
                if loop:
                    values -= np.outer(smooth, values[-1]-values[0])
                    values[-1] = values[0]
                else:
                    rest = target_rig.t[target_node]
                    values = rest+(values-rest)*fade[:, None]
                    values[0] = values[-1] = rest
            if not np.isfinite(values).all():
                raise ValueError(f'Non-finite retargeted donor animation: {name}/{target_node}/{path}.')
            node = doc['nodes'][target_node]
            if 'matrix' in node:
                node.pop('matrix')
                node['translation'] = target_rig.t[target_node].tolist()
                node['rotation'] = target_rig.q[target_node].tolist()
                node['scale'] = target_rig.s[target_node].tolist()
            output = append_accessor(values.astype('<f4'), 'VEC4' if path == 'rotation' else 'VEC3', 5126)
            index = len(clip['samplers'])
            clip['samplers'].append({'input': input_accessor, 'output': output, 'interpolation': 'LINEAR'})
            clip['channels'].append({'sampler': index, 'target': {'node': target_node, 'path': path}})
        if clip['channels']:
            selected[name] = native.get('name', '')
            replacements[name] = clip
    doc['animations'] = [replacements.get(a.get('name'), a) for a in doc['animations']]
    return selected


def refresh_glb_attack(path, output_path=None):
    """Replace only an embedded GLB's Attack, preserving its native clips/assets.

    Uses the current Attack extras to identify character and weapon style. Old
    binary bytes and accessors stay intact; replacement keys are appended. The
    destination is replaced atomically after complete validation/serialization.
    This explicit utility performs filesystem I/O; importing the module does not.
    """
    import json
    import os
    import struct
    import tempfile
    from pathlib import Path

    source = Path(path)
    destination = Path(output_path) if output_path is not None else source
    raw = source.read_bytes()
    if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
        raise ValueError(f'Invalid GLB header: {source}')
    chunks, offset = [], 12
    while offset < len(raw):
        length, kind = struct.unpack_from('<II', raw, offset)
        data = raw[offset+8:offset+8+length]
        if len(data) != length or length % 4:
            raise ValueError(f'Invalid GLB chunk: {source}')
        chunks.append([kind, data])
        offset += 8+length
    json_chunks = [i for i, (kind, _) in enumerate(chunks) if kind == 0x4E4F534A]
    bin_chunks = [i for i, (kind, _) in enumerate(chunks) if kind == 0x004E4942]
    if len(json_chunks) != 1 or len(bin_chunks) != 1:
        raise ValueError('Attack refresh requires one embedded JSON and BIN chunk.')
    doc = json.loads(chunks[json_chunks[0]][1])
    if len(doc.get('buffers', [])) != 1 or 'uri' in doc['buffers'][0]:
        raise ValueError('Attack refresh requires a single embedded buffer.')
    existing = doc.get('animations', [])
    attack = next((a for a in existing if a.get('name') == 'Attack'), None)
    if attack is None:
        raise ValueError(f'No Attack clip to refresh: {source}')
    extras = attack.get('extras', {})
    if 'characterId' not in extras or 'attackStyle' not in extras:
        raise ValueError('Attack must record characterId and attackStyle.')
    original_bin_length = len(chunks[bin_chunks[0]][1])
    binary = bytearray(chunks[bin_chunks[0]][1])

    def append(array, kind, component_type=5126):
        if component_type != 5126:
            raise ValueError('Animation refresh appends only float32 keys.')
        while len(binary) % 4:
            binary.append(0)
        array = np.asarray(array, dtype='<f4')
        payload = array.tobytes()
        view = len(doc.setdefault('bufferViews', []))
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(payload)})
        binary.extend(payload)
        index = len(doc.setdefault('accessors', []))
        accessor = {'bufferView': view, 'componentType': 5126, 'count': len(array), 'type': kind}
        if kind == 'SCALAR':
            accessor.update(min=[float(array.min())], max=[float(array.max())])
        doc['accessors'].append(accessor)
        return index

    replacement = add_animations(doc, append, extras['characterId'], extras['attackStyle'], clip_names=('Attack',))[0]
    doc['animations'] = [replacement if a is attack else a for a in existing]
    doc['buffers'][0]['byteLength'] = len(binary)
    json_bytes = json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    json_bytes += b' ' * (-len(json_bytes) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    chunks[json_chunks[0]][1] = json_bytes
    chunks[bin_chunks[0]][1] = bytes(binary)
    body = b''.join(struct.pack('<II', len(data), kind)+data for kind, data in chunks)
    result = struct.pack('<4sII', b'glTF', 2, len(body)+12)+body
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=destination.name+'.', suffix='.tmp', dir=destination.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(result)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'path': str(destination.resolve()), 'characterId': extras['characterId'],
            'attackStyle': extras['attackStyle'], 'addedBytes': len(binary)-original_bin_length}


def _sanity_check():
    # A minimal rotated skeleton checks axis independence, duplicate filtering,
    # normalization and exact looping without loading any external assets.
    nodes = [
        {'name': 'Scene', 'rotation': _axisq([1, 0, 0], -90).tolist(), 'children': [1, 15]},
        {'name': 'Bip001', 'translation': [0, 0, .9], 'children': [2]},
        {'name': 'Bip001 Pelvis', 'children': [3, 5, 8]},
        {'name': 'Bip001 Spine', 'translation': [0, 0, .2], 'children': [4, 11, 13]},
        {'name': 'Bip001 Head', 'translation': [0, 0, .3], 'children': [17]},
        {'name': 'Bip001 L Thigh', 'translation': [.1, 0, 0], 'children': [6]},
        {'name': 'Bip001 L Calf', 'translation': [0, 0, -.4], 'children': [7]},
        {'name': 'Bip001 L Foot', 'translation': [0, 0, -.4]},
        {'name': 'Bip001 R Thigh', 'translation': [-.1, 0, 0], 'children': [9]},
        {'name': 'Bip001 R Calf', 'translation': [0, 0, -.4], 'children': [10]},
        {'name': 'Bip001 R Foot', 'translation': [0, 0, -.4]},
        {'name': 'Bip001 L UpperArm', 'translation': [.2, 0, .15], 'children': [12]},
        {'name': 'Bip001 L Forearm', 'translation': [.2, 0, 0]},
        {'name': 'Bip001 R UpperArm', 'translation': [-.2, 0, .15], 'children': [14]},
        {'name': 'Bip001 R Forearm', 'translation': [-.2, 0, 0]},
        {'name': 'Bip001 Pelvis', 'children': [16]},
        {'name': 'Bip001 Head', 'translation': [0, 0, 1]},
        {'name': 'HairAccessory_Left', 'translation': [.15, 0, .1]},
        {'name': 'Mesh', 'mesh': 0, 'skin': 0},
    ]
    doc = {'nodes': nodes, 'skins': [{'joints': list(range(2, 15))}, {'joints': [15, 16]}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'JOINTS_0': 1, 'WEIGHTS_0': 2}}]}],
           'accessors': [{'count': 100}, {'count': 100}, {'count': 100}]}
    arrays = []

    def append(array, kind, component_type=5126):
        index = len(doc['accessors'])
        doc['accessors'].append({'count': len(array), 'type': kind, 'componentType': component_type})
        arrays.append((index, array))
        return index

    add_animations(doc, append, 'character_02', 'scythe')
    by_index = dict(arrays)
    assert [a['name'] for a in doc['animations']] == ['Idle', 'Walk', 'Run', 'Attack', 'Defend', 'Victory', 'Lose']
    for animation in doc['animations']:
        assert all(c['target']['node'] not in (15, 16) for c in animation['channels'])
        for c in animation['channels']:
            sampler = animation['samplers'][c['sampler']]
            values = by_index[sampler['output']]
            assert np.isfinite(values).all()
            if c['target']['path'] == 'rotation':
                assert np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-6)
            if animation['extras']['loop']:
                assert np.array_equal(values[0], values[-1])
            elif animation['name'] == 'Lose':
                hold = int(math.ceil(.8*(len(values)-1)))
                assert np.array_equal(values[hold:], np.broadcast_to(values[-1], values[hold:].shape))
    walk, run = (next(a for a in doc['animations'] if a['name'] == name) for name in ('Walk', 'Run'))
    common = 5  # The rotated fixture's left thigh is driven by both IK gaits.
    def output(clip):
        channel = next(c for c in clip['channels'] if c['target'] == {'node': common, 'path': 'rotation'})
        return by_index[clip['samplers'][channel['sampler']]['output']]
    walking, running = output(walk), output(run)
    assert any(abs(np.dot(walking[round(u*(len(walking)-1))], running[round(u*(len(running)-1))])) < .999
               for u in (.125, .25, .375, .5, .625, .75, .875))
    lose = next(a for a in doc['animations'] if a['name'] == 'Lose')
    assert any(not np.array_equal(by_index[lose['samplers'][c['sampler']]['output']][0],
                                  by_index[lose['samplers'][c['sampler']]['output']][-1])
               for c in lose['channels'])
    print('character_animations: seven clips, normalized rotations, exact loops, distinct Run, held Lose and skin filtering passed')


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Character animation sanity check or Attack-only GLB refresh.')
    parser.add_argument('--refresh-attack', nargs='+', metavar='GLB', help='Replace Attack in the listed GLBs in place.')
    arguments = parser.parse_args()
    if arguments.refresh_attack:
        for path in arguments.refresh_attack:
            print(json.dumps(refresh_glb_attack(path), ensure_ascii=False))
    else:
        _sanity_check()
