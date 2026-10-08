"""Curated original BlueArchive motions, retargeted to each assembled body.

The catalog is read only. Every selection below is an actual embedded source
clip, not a procedural gait or a shared pose given another character's name.
Anatomical bones are matched only inside the main body skeleton. Cloth is
matched by its garment category and rest position; source props, expressions,
scale and visibility are excluded. Call ``add_catalog_motions(builder)`` after
the original animation setup and before serializing the builder.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

from character_animations import (_Rig, _IDENTITY, _EPS, _native_samples,
                                  _qmul, _qinv, _qnorm, _qrot, _unit, _slerp,
                                  _weapon_rotation, _axisq)


# A different original performance is selected for every character in each
# refreshed category. The four additions also receive their own cafe gestures.
_RUN = {
    1: ('Momoi (Maid)', 'Move_Ing', 'Lively maid sprint with a large knee drive'),
    2: ('Haruka (Dress)', 'Move_Ing', 'Forward, determined reaper dash'),
    3: ('Serika', 'Move_Ing', 'Brisk schoolgirl sprint'),
    4: ('Sena (Casual)', 'Move_Ing', 'Composed, flowing dress run'),
    5: ('Reisa', 'Move_Ing', 'Confident academy charge'),
    6: ('Ibuki', 'Move_Ing', 'Light, buoyant sprite run'),
    7: ('Saori (Swimsuit)', 'Move_Ing', 'Low, agile city-cat dash'),
    8: ('Mutsuki', 'Move_Ing', 'Playful, asymmetric doll sprint'),
    9: ('Wakamo', 'Move_Ing', 'Strong, deliberate forward pursuit'),
    10: ('Atsuko', 'Move_Ing', 'Soft but decisive snow-dress run'),
    11: ('Neru', 'Move_Ing', 'Aggressive dual-arm scout sprint with a long stride'),
    12: ('Izuna', 'Move_Ing', 'Energetic fox-ninja bounding sprint'),
    13: ('Eri', 'DiceRace_Run', 'Expressive witch race run with free arm carriage'),
    14: ('Mari (Idol)', 'Move_Ing', 'Poised, buoyant bridal dash'),
}
_DEFEND = {
    1: ('Momoi (Maid)', 'Vital_Panic', 'Alert maid recoil and ready guard'),
    2: ('Tsurugi', 'Vital_Panic', 'Fierce two-arm reaper guard'),
    3: ('Serika', 'Vital_Panic', 'Compact, determined school guard'),
    4: ('Sena (Casual)', 'Vital_Panic', 'Calm, braced dress guard'),
    5: ('Noa', 'Vital_Panic', 'Measured academy defensive stance'),
    6: ('Ibuki', 'Vital_Panic', 'Small, startled sprite protection'),
    7: ('Asuna (School Uniform)', 'Vital_Panic', 'Agile, open city-cat guard'),
    8: ('Sakurako (Idol)', 'Vital_Panic', 'Expressive, drawn-in doll protection'),
    9: ('Mimori', 'Vital_Panic', 'Graceful, balanced fan-user guard'),
    10: ('Atsuko', 'Vital_Panic', 'Gentle, protective snow stance'),
    11: ('Mine', 'Vital_Panic', 'Firm, squared scout guard'),
    12: ('Izuna', 'Vital_Panic', 'Springy fox-ninja ready stance'),
    13: ('Eri', 'Vital_Panic', 'Witch recoil and braced casting guard'),
    14: ('Mari (Idol)', 'Vital_Panic', 'Reserved, protective bridal recoil'),
}
_LOSE = {
    1: ('Momoi (Maid)', 'Vital_Death', 'Maid stumbles and settles defeated'),
    2: ('Tsurugi', 'Vital_Death', 'Dramatic reaper collapse'),
    3: ('Serika', 'Vital_Death', 'Determined school stance gives way'),
    4: ('Sena (Casual)', 'Vital_Death', 'Controlled dress-wearer sinking defeat'),
    5: ('Noa', 'Vital_Death', 'Asymmetric academy fall and exhausted finish'),
    6: ('Ibuki', 'Vital_Death', 'Small sprite flinch and collapse'),
    7: ('Mika', 'Vital_Death', 'City-cat loses balance and folds into a dramatic defeat'),
    8: ('Sakurako (Idol)', 'Vital_Death', 'Expressive doll collapse'),
    9: ('Wakamo', 'Vital_Death', 'Dramatic fan-user fall'),
    10: ('Atsuko', 'Vital_Death', 'Gentle snow-character folding defeat'),
    11: ('Mine', 'Vital_Death', 'Scout loses balance and lands defeated'),
    12: ('Seia', 'Vital_Death', 'Fox idol falters and settles into defeat'),
    13: ('Eri', 'Vital_Death', 'Witch staggers and lowers into exhaustion'),
    14: ('Mari (Idol)', 'Vital_Death', 'Poised bridal character sinks defeated'),
}
_ADDITIONS = {
    11: ('Shiroko', 'Quiet scout breathing', 'Purposeful, observant scout walk', 'Small scout victory salute'),
    12: ('Izuna', 'Bright fox-ninja anticipation', 'Buoyant fox-ninja walk', 'Exuberant fox-ninja victory'),
    13: ('Eri', 'Thoughtful witch idle', 'Measured, composed witch walk', 'Cheerful witch celebration'),
    14: ('Mimori', 'Graceful, reserved bridal idle', 'Gentle ceremonial walk', 'Courteous bridal celebration'),
}
_ATTACK = {
    11: ('Neru', 'Exs', 'Aggressive native dual-arm scout combination, with fitted dagger grips'),
    12: ('Izuna', 'Exs', 'Native fox-ninja casting flourish, with a fitted starbell baton grip'),
    13: ('Eri', 'Exs', 'Native witch stirring and casting sweep, with a fitted flower-staff grip'),
    14: ('Mimori', 'Exs', 'Native support flourish, adapted to lifting the rose bouquet'),
}

_ANATOMY = re.compile(r'^Bip001(?:$| (?:Pelvis|Spine\d*|Neck|Head|[LR] (?:Clavicle|UpperArm|Forearm|Hand|Thigh|Calf|Foot|Toe\d*|Finger\d*)))$')
_EXCLUDED = re.compile(r'weapon|prop|halo|face|eye|mouth|brow|breast', re.I)


def _cloth_kind(name):
    name = name.lower()
    if _EXCLUDED.search(name):
        return None
    if 'skirt' in name or 'dresscover' in name:
        return 'skirt'
    if 'sleeve' in name or 'sodetake' in name:
        return 'sleeve'
    if 'jacket' in name or 'coat' in name:
        return 'jacket'
    if 'hair' in name:
        return 'hair'
    if any(word in name for word in ('ribbon', 'ribborn', 'muffler')):
        return 'ribbon'
    if 'tail' in name:
        return 'tail'
    return None


def _body_map(source_rig, target_rig):
    return {node: target_rig.bones[name] for name, node in source_rig.bones.items()
            if _ANATOMY.match(name) and name in target_rig.bones}


def _secondary_map(source_rig, target_rig, animation, exact_map):
    """Match secondary joints without ever attaching a source prop skeleton."""
    animated = {c['target']['node'] for c in animation['channels']
                if c['target']['path'] == 'rotation'}
    target_joints = set(target_rig.doc['skins'][target_rig.skin]['joints'])
    source_joints = set(source_rig.doc['skins'][source_rig.skin]['joints'])
    result = {}
    if exact_map:
        for source, target in exact_map.items():
            if source in animated and target in target_joints and _cloth_kind(source_rig.nodes[source].get('name', '')):
                result[int(target)] = (int(source), 1.0)
    # Normalized anatomical rest positions are used only for secondary cloth;
    # the body rig itself always uses explicit anatomical names.
    def position(rig, node, kind):
        anchor = rig.bones['Bip001 Head'] if kind == 'hair' else rig.bones['Bip001 Pelvis']
        delta = (rig.pos[node]-rig.pos[anchor])/rig.height
        return np.array([delta @ rig.right, delta @ rig.up, delta @ rig.forward])
    by_kind = {}
    for source in source_joints & animated:
        kind = _cloth_kind(source_rig.nodes[source].get('name', ''))
        if kind:
            by_kind.setdefault(kind, []).append((source, position(source_rig, source, kind)))
    for target in target_joints:
        if target in result:
            continue
        kind = _cloth_kind(target_rig.nodes[target].get('name', ''))
        candidates = by_kind.get(kind, ())
        if not candidates:
            continue
        where = position(target_rig, target, kind)
        source, pos = min(candidates, key=lambda item: float(np.linalg.norm(item[1]-where)))
        # Do not confuse a different-height chain's scalp/root with its tip.
        if np.linalg.norm(pos-where) < .24:
            result[int(target)] = (int(source), .65)
    return result


def _rotation_samples(source, animation, source_rig, target_rig, source_node, target_node, times, weight=1.):
    channel = next((c for c in animation['channels']
                    if c['target'] == {'node': source_node, 'path': 'rotation'}), None)
    if channel is None:
        return np.tile(target_rig.q[target_node], (len(times), 1))
    values = _native_samples(source.acc, animation['samplers'][channel['sampler']], 'rotation', times)
    sp, tp = source_rig.parent[source_node], target_rig.parent[target_node]
    sq = source_rig.rest_world_q[sp] if sp >= 0 else _IDENTITY
    tq = target_rig.rest_world_q[tp] if tp >= 0 else _IDENTITY
    basis = _qmul(_qinv(tq), sq)
    sinv = _qinv(source_rig.q[source_node])
    out = []
    for value in values:
        delta = _qmul(_qmul(basis, _qmul(value, sinv)), _qinv(basis))
        if weight < 1:
            delta = _slerp(_IDENTITY, delta, weight)
        out.append(_qnorm(_qmul(delta, target_rig.q[target_node])))
    return np.asarray(out)


def _translation_samples(source, animation, source_rig, target_rig, source_node, target_node, times):
    channel = next(c for c in animation['channels']
                   if c['target'] == {'node': source_node, 'path': 'translation'})
    values = _native_samples(source.acc, animation['samplers'][channel['sampler']], 'translation', times)
    sp, tp = source_rig.parent[source_node], target_rig.parent[target_node]
    source_basis = source_rig.rest_world[sp, :3, :3] if sp >= 0 else np.eye(3)
    target_basis = target_rig.rest_world[tp, :3, :3] if tp >= 0 else np.eye(3)
    world_delta = (values-source_rig.t[source_node]) @ source_basis.T
    world_delta *= target_rig.height/source_rig.height
    return target_rig.t[target_node]+world_delta @ np.linalg.inv(target_basis).T


def _append_channel(builder, clip, input_accessor, rig, node, path, values):
    values = np.asarray(values, dtype=float)
    if path == 'rotation':
        values /= np.maximum(np.linalg.norm(values, axis=1, keepdims=True), _EPS)
        for i in range(1, len(values)):
            if np.dot(values[i-1], values[i]) < 0:
                values[i] *= -1
        if clip['extras']['loop']:
            values[-1] = values[0]
    if not np.isfinite(values).all():
        raise ValueError(f'Invalid native animation output: {clip["name"]}/{node}/{path}')
    if 'matrix' in rig.nodes[node]:
        rig.nodes[node].pop('matrix')
        rig.nodes[node].update(translation=rig.t[node].tolist(), rotation=rig.q[node].tolist(), scale=rig.s[node].tolist())
    output = builder.acc(values.astype('<f4'), 'VEC4' if path == 'rotation' else 'VEC3', 5126)
    index = len(clip['samplers'])
    clip['samplers'].append({'input': input_accessor, 'output': output, 'interpolation': 'LINEAR'})
    clip['channels'].append({'sampler': index, 'target': {'node': int(node), 'path': path}})


def _fit_prop_grips(rig, number, name, rotations, translations, root_values, fade):
    """Refit wrists and fingers around target props, preserving native arms.

    The source motion drives shoulders, elbows, torso and legs unchanged. A
    handgun's grip direction cannot simply be reused for an upright staff or
    dagger: orient those props relative to the native forearm action and curl
    the actual target fingers around their fitted shaft at the measured palm.
    """
    if number == 7:
        return
    sides = ('L', 'R') if number == 11 else ('R',)
    for frame, activity in enumerate(fade):
        if activity <= 0:
            continue
        q, t = rig.q.copy(), rig.t.copy()
        for node, values in rotations.items():
            q[node] = values[frame]
        for node, values in translations.items():
            t[node] = values[frame]
        t[rig.root] = root_values[frame]
        for side in sides:
            hand = rig.bones.get(f'Bip001 {side} Hand')
            elbow = rig.bones.get(f'Bip001 {side} Forearm')
            if hand is None or elbow is None:
                continue
            world, world_q = rig.world(q, t)
            direction = _unit(world[hand, :3, 3]-world[elbow, :3, 3], rig.forward)
            if name == 'Lose':
                # A lowered defeated hand carries a long prop along the floor
                # instead of pointing its shaft down through the ground.
                shaft = _unit(rig.forward*.96-rig.right*.22+rig.up*.16, rig.forward)
            elif name != 'Attack':
                if number == 11:
                    shaft = _unit(-rig.up*.91+rig.forward*.25+rig.right*(-.25 if side == 'R' else .25))
                elif number == 14:
                    shaft = _unit(rig.up*.88+rig.forward*.44-rig.right*.10)
                elif number in (1, 2, 6, 12, 13):
                    shaft = _unit(rig.up*.82+rig.forward*.45-rig.right*.34)
                else:
                    shaft = _unit(rig.up*.96+rig.forward*.24-rig.right*.12)
            elif number == 11:
                # Each dagger follows its corresponding native arm's thrust
                # and sweep, retaining Neru's two different action paths.
                shaft = direction
            elif number == 12:
                shaft = _unit(rig.up*.86+direction*.30, rig.up)
            elif number == 13:
                shaft = _unit(rig.up*.93+direction*.16+rig.forward*.10, rig.up)
            else:
                shaft = _unit(rig.up*.95+rig.forward*.28, rig.up)
            normal = _unit(rig.forward-shaft*(rig.forward @ shaft), rig.right)
            delta = _weapon_rotation(rig, shaft, normal)
            goal_world = _qmul(delta, rig.rest_world_q[hand])
            parent = rig.parent[hand]
            goal_local = _qmul(_qinv(world_q[parent]), goal_world) if parent >= 0 else goal_world
            q[hand] = _slerp(q[hand], goal_local, activity)
            rotations.setdefault(hand, np.tile(rig.q[hand], (len(fade), 1)))[frame] = q[hand]
            world, world_q = rig.world(q, t)
            actual_delta = _qmul(world_q[hand], _qinv(rig.rest_world_q[hand]))
            actual_shaft = _qrot(actual_delta, rig.up)
            grip = world[hand, :3, 3]+_qrot(actual_delta, rig.palm_offset(side))
            tracks = rig.finger_grip(q, t, side, grip, actual_shaft, activity*.95)
            for node in tracks:
                rotations.setdefault(node, np.tile(rig.q[node], (len(fade), 1)))[frame] = q[node]


def _read_accessor(builder, index):
    accessor = builder.doc['accessors'][index]
    view = builder.doc['bufferViews'][accessor['bufferView']]
    dtype = np.dtype({5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[accessor['componentType']])
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[accessor['type']]
    values = np.ndarray((accessor['count'], width), dtype=dtype, buffer=builder.data,
                        offset=view.get('byteOffset', 0)+accessor.get('byteOffset', 0),
                        strides=(view.get('byteStride', dtype.itemsize*width), dtype.itemsize)).copy()
    if accessor.get('normalized') and dtype.kind in 'iu':
        values = values.astype(float)/np.iinfo(dtype).max
    return values


class _SkinFloor:
    """Floor of all used skinned vertices, including cloth, hair and props."""
    def __init__(self, builder, rig):
        self.rig = rig
        self.skin = builder.doc['skins'][rig.skin]
        self.nodes = np.asarray(self.skin['joints'], dtype=int)
        self.inverse = _read_accessor(builder, self.skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        positions, joints, weights = [], [], []
        for node in builder.doc['nodes']:
            if node.get('skin') != rig.skin or 'mesh' not in node:
                continue
            for primitive in builder.doc['meshes'][node['mesh']]['primitives']:
                attrs = primitive['attributes']
                used = np.unique(_read_accessor(builder, primitive['indices']).astype(int).ravel())
                positions.append(_read_accessor(builder, attrs['POSITION'])[used])
                joints.append(_read_accessor(builder, attrs['JOINTS_0'])[used].astype(int))
                weights.append(_read_accessor(builder, attrs['WEIGHTS_0'])[used].astype(float))
        self.positions = np.c_[np.concatenate(positions), np.ones(sum(len(p) for p in positions))]
        self.joints, self.weights = np.concatenate(joints), np.concatenate(weights)
        movable = np.zeros(len(rig.nodes), dtype=float)
        for node in rig.order:
            if node == rig.root or (rig.parent[node] >= 0 and movable[rig.parent[node]]):
                movable[node] = 1.
        self.move_weight = (movable[self.nodes][self.joints]*self.weights).sum(1)
        self.up4 = np.r_[rig.up, 0.]
        self.floor = float(self.heights(rig.rest_world).min())

    def heights(self, world):
        transforms = world[self.nodes] @ self.inverse
        rows = np.einsum('i,nij->nj', self.up4, transforms)
        heights = np.einsum('vij,vj->vi', rows[self.joints], self.positions)
        return (heights*self.weights).sum(1)

    def required_raise(self, world):
        heights = self.heights(world)
        eligible = self.move_weight > 1e-5
        return float(np.maximum(0., (self.floor-heights[eligible])/self.move_weight[eligible]).max(initial=0.))


def _fit_geometry_floor(floor, rotations, translations, root_values):
    rig, root = floor.rig, floor.rig.root
    parent = rig.parent[root]
    basis = rig.rest_world[parent, :3, :3] if parent >= 0 else np.eye(3)
    inverse = np.linalg.inv(basis)
    maximum = 0.
    for frame in range(len(root_values)):
        q, t = rig.q.copy(), rig.t.copy()
        for node, values in rotations.items():
            q[node] = values[frame]
        for node, values in translations.items():
            t[node] = values[frame]
        t[root] = root_values[frame]
        world, _ = rig.world(q, t)
        rise = floor.required_raise(world)
        if rise > 0:
            root_values[frame] += inverse @ (rig.up*(rise+.00015))
        maximum = max(maximum, rise)
    # Check actual quaternion interpolation between keys, too. Raising both
    # surrounding root keys by the same amount corrects that swept interval.
    for frame in range(len(root_values)-1):
        for fraction in (.25, .5, .75):
            q, t = rig.q.copy(), rig.t.copy()
            for node, values in rotations.items():
                q[node] = _slerp(values[frame], values[frame+1], fraction)
            for node, values in translations.items():
                t[node] = values[frame]*(1-fraction)+values[frame+1]*fraction
            t[root] = root_values[frame]*(1-fraction)+root_values[frame+1]*fraction
            world, _ = rig.world(q, t)
            rise = floor.required_raise(world)
            if rise > 1e-6:
                lift = inverse @ (rig.up*(rise+.00015))
                root_values[frame] += lift
                root_values[frame+1] += lift
            maximum = max(maximum, rise)
    return maximum


def _retarget(builder, name, selection, target_rig):
    donor, wanted, description = selection
    source = builder.source(donor)
    animation = next((a for a in source.doc.get('animations', [])
                      if a.get('name', '').lower() == wanted.lower()), None)
    if animation is None:
        raise ValueError(f'Required original motion is missing: {donor}.glb/{wanted}')
    source_rig = _Rig(source.doc)
    node_map = _body_map(source_rig, target_rig)
    if len(node_map) < 20:
        raise ValueError(f'Incomplete anatomical retarget: {donor}/{name}')
    channels = [c for c in animation['channels'] if c['target']['node'] in node_map
                and c['target']['path'] in ('rotation', 'translation')]
    inputs = [np.asarray(source.acc(animation['samplers'][c['sampler']]['input'])).reshape(-1) for c in channels]
    begin, end = min(float(t[0]) for t in inputs), max(float(t[-1]) for t in inputs)
    native_duration = end-begin
    if not math.isfinite(native_duration) or native_duration <= .05:
        raise ValueError(f'Invalid original motion duration: {donor}/{wanted}')
    loop = name in ('Idle', 'Walk', 'Run')
    duration = native_duration*1.25 if name == 'Lose' else native_duration
    times = np.linspace(0, duration, max(3, int(round(duration*30))+1))
    hold_begin = duration*.79 if name == 'Lose' else None
    if hold_begin is not None:
        # An explicit early boundary guarantees a strictly stationary final
        # fifth even after float32 time quantization and LINEAR interpolation.
        # The whole original defeat action is retained, retimed by only 1.3%.
        times = np.unique(np.asarray(np.r_[times, hold_begin], dtype='<f4')).astype(float)
        hold_begin = float(np.float32(hold_begin))
        native_times = begin+np.minimum(times/hold_begin*native_duration, native_duration)
    else:
        native_times = begin+np.minimum(times, native_duration)
    progress = np.clip((native_times-begin)/native_duration, 0, 1)
    smooth = progress*progress*(3-2*progress)
    if loop:
        fade = np.ones(len(times))
    else:
        fade = np.clip(progress/.12, 0, 1)
        fade = fade*fade*(3-2*fade)
        if name != 'Lose':
            leave = np.clip((1-progress)/.18, 0, 1)
            fade = np.minimum(fade, leave*leave*(3-2*leave))
    adaptation = ['Main anatomical rotations and translations retargeted through source and target rest-parent bases',
                  'Non-root body translation deltas scaled to the target/source height ratio',
                  'Horizontal root travel removed; native vertical bounce retained',
                  'Source props, expressions, scale and visibility excluded',
                  'Native garment rotations fitted to target cloth categories and rest positions',
                  '30 fps quaternion resampling and normalized rotations']
    if loop:
        adaptation.append('Continuous endpoint correction for an exact loop seam')
        adaptation.append('Constant source horizontal heading aligned to the target rest heading; dynamic turns retained')
    elif name == 'Lose':
        adaptation.append('Native final defeat pose held for the final 20% of the output clip')
    else:
        adaptation.append('Smooth entry and recovery to the target bind pose')
    if int(builder.c['id']) != 7:
        adaptation.append('Only target wrists and fingers refitted for actual prop carriage; native shoulders and elbows retained')
    adaptation.append('Actual skinned hair, clothing, body and prop vertices fitted above the bind floor at keys and interpolation quarter steps')
    provenance = {'source_file': donor+'.glb', 'source_clip': animation['name'],
                  'adaptation': adaptation, 'description': description}
    clip = {'name': name, 'channels': [], 'samplers': [], 'extras': {
        'loop': loop, 'inPlace': True, 'durationSeconds': float(duration),
        'characterId': str(builder.c['id']), 'procedural': False,
        'nativeSourceClip': animation['name'], 'source_file': donor+'.glb',
        'source_clip': animation['name'], 'description': description, 'action': description,
        'sourceDurationSeconds': float(native_duration), 'adaptation': adaptation,
        'secondaryMotion': 'Native source garment rotations fitted to target cloth',
        'personalityMotion': True}}
    if name == 'Lose':
        clip['extras'].update(terminalPoseHeld=True, holdWindowSeconds=[hold_begin, duration])
    if name == 'Run':
        clip['extras'].update(gait=description, independentOfWalk=True, nativeStride=True)
    if name == 'Attack':
        clip['extras'].update(attackStyle=builder.c['attack'], weaponAware=True,
                              propGrip='Both palms' if builder.c['id'] == 11 else 'Right palm',
                              propBind={'shaftAxis': target_rig.up.tolist(), 'faceNormal': target_rig.forward.tolist()},
                              gripAdaptation='Wrist orientation and target finger curl only; native shoulders and elbows retained')
    exact = builder.source_node_map if donor == builder.src.name else {}
    secondaries = _secondary_map(source_rig, target_rig, animation, exact)
    rotations, translations = {}, {}
    for source_node, target_node in node_map.items():
        if any(c['target'] == {'node': source_node, 'path': 'rotation'} for c in channels):
            rotations[target_node] = _rotation_samples(source, animation, source_rig, target_rig,
                                                       source_node, target_node, native_times)
        if target_node != target_rig.root and any(c['target'] == {'node': source_node, 'path': 'translation'}
                                                 for c in channels):
            translations[target_node] = _translation_samples(source, animation, source_rig, target_rig,
                                                              source_node, target_node, native_times)
    for target_node, (source_node, weight) in secondaries.items():
        if target_node not in rotations:
            rotations[target_node] = _rotation_samples(source, animation, source_rig, target_rig,
                                                       source_node, target_node, native_times, weight)
    for node, values in rotations.items():
        if loop:
            correction = _qmul(_qinv(values[-1]), values[0])
            values[:] = [_qnorm(_qmul(q, _slerp(_IDENTITY, correction, s))) for q, s in zip(values, smooth)]
            values[-1] = values[0]
        else:
            values[:] = [_slerp(target_rig.q[node], q, f) for q, f in zip(values, fade)]
            values[0] = target_rig.q[node]
            if name != 'Lose':
                values[-1] = target_rig.q[node]
    for node, values in translations.items():
        if loop:
            values -= np.outer(smooth, values[-1]-values[0])
            values[-1] = values[0]
        else:
            values[:] = target_rig.t[node]+(values-target_rig.t[node])*fade[:, None]
            values[0] = target_rig.t[node]
            if name != 'Lose':
                values[-1] = target_rig.t[node]
    # Bake the source root's entire ancestor chain. Some original performances
    # animate bone_root above Bip001; silently dropping it would lose jumps.
    source_t = np.tile(source_rig.t[None, :, :], (len(times), 1, 1))
    source_q = np.tile(source_rig.q[None, :, :], (len(times), 1, 1))
    ancestors = set()
    ancestor = source_rig.root
    while ancestor >= 0:
        ancestors.add(int(ancestor))
        ancestor = source_rig.parent[ancestor]
    for channel in animation['channels']:
        node, path = channel['target']['node'], channel['target']['path']
        if node in ancestors and path in ('rotation', 'translation'):
            values = _native_samples(source.acc, animation['samplers'][channel['sampler']], path, native_times)
            (source_q if path == 'rotation' else source_t)[:, node] = values
    source_poses = [source_rig.world(q, t) for q, t in zip(source_q, source_t)]
    source_world = np.asarray([world[source_rig.root, :3, 3] for world, _ in source_poses])
    # Root rotations also include any animated ancestors, in the same way as
    # their translations. A source scene/FX parent can otherwise disappear.
    root = target_rig.root
    parent = target_rig.parent[root]
    parent_q = target_rig.rest_world_q[parent] if parent >= 0 else _IDENTITY
    source_rest_inverse = _qinv(source_rig.rest_world_q[source_rig.root])
    root_rotations = np.asarray([_qnorm(_qmul(_qinv(parent_q), _qmul(
        _qmul(world_q[source_rig.root], source_rest_inverse), target_rig.rest_world_q[root])))
        for _, world_q in source_poses])
    heading_correction = _IDENTITY.copy()
    if loop:
        rest_inverse = _qinv(target_rig.rest_world_q[root])
        facings = np.asarray([_qrot(_qmul(_qmul(parent_q, q), rest_inverse), target_rig.forward)
                              for q in root_rotations])
        facings -= np.outer(facings @ target_rig.up, target_rig.up)
        mean = facings.mean(0)
        if np.linalg.norm(mean) < .05:
            mean = facings[0]
        angle = math.degrees(math.atan2(mean @ target_rig.right, mean @ target_rig.forward))
        heading_correction = _axisq(target_rig.up, -angle)
        root_rotations = np.asarray([_qnorm(_qmul(_qinv(parent_q), _qmul(
            heading_correction, _qmul(parent_q, q)))) for q in root_rotations])
        clip['extras']['removedConstantHeadingDegrees'] = float(angle)
    if loop:
        correction = _qmul(_qinv(root_rotations[-1]), root_rotations[0])
        root_rotations = np.asarray([_qnorm(_qmul(q, _slerp(_IDENTITY, correction, s)))
                                     for q, s in zip(root_rotations, smooth)])
        root_rotations[-1] = root_rotations[0]
    else:
        root_rotations = np.asarray([_slerp(target_rig.q[root], q, f) for q, f in zip(root_rotations, fade)])
        root_rotations[0] = target_rig.q[root]
        if name != 'Lose':
            root_rotations[-1] = target_rig.q[root]
    rotations[root] = root_rotations
    world_delta = (source_world-source_rig.pos[source_rig.root])*(target_rig.height/source_rig.height)
    if loop:
        world_delta = np.asarray([_qrot(heading_correction, delta) for delta in world_delta])
    up = target_rig.up
    horizontal = world_delta-np.outer(world_delta @ up, up)
    if loop:
        world_delta -= horizontal[0]+np.outer(progress, horizontal[-1]-horizontal[0])
    else:
        # Keep short natural body sway; large original battlefield dashes would
        # otherwise move an in-place preview off screen during a skill action.
        world_delta -= horizontal
        centered = horizontal-horizontal[0]
        length = np.linalg.norm(centered, axis=1)
        world_delta += centered*np.minimum(1., target_rig.height*.035/np.maximum(length, _EPS))[:, None]
    basis = target_rig.rest_world[parent, :3, :3] if parent >= 0 else np.eye(3)
    root_values = target_rig.t[root]+world_delta @ np.linalg.inv(basis).T
    if loop:
        root_values -= np.outer(smooth, root_values[-1]-root_values[0])
        root_values[-1] = root_values[0]
    else:
        root_values = target_rig.t[root]+(root_values-target_rig.t[root])*fade[:, None]
        root_values[0] = target_rig.t[root]
        if name != 'Lose':
            root_values[-1] = target_rig.t[root]
    # A different donor may have different shin lengths. Raise the complete
    # retargeted body only when an ankle would sink below its target bind floor.
    feet = [target_rig.bones[n] for n in ('Bip001 L Foot', 'Bip001 R Foot') if n in target_rig.bones]
    floor = min(target_rig.pos[i] @ up for i in feet)
    for frame in range(len(times)):
        q, t = target_rig.q.copy(), target_rig.t.copy()
        for node, values in rotations.items():
            q[node] = values[frame]
        for node, values in translations.items():
            t[node] = values[frame]
        t[root] = root_values[frame]
        world, _ = target_rig.world(q, t)
        low = min(world[i, :3, 3] @ up for i in feet)
        rise = max(0., floor-low)
        if rise:
            root_values[frame] += np.linalg.inv(basis) @ (up*rise)
    if loop:
        root_values[-1] = root_values[0]
    if name == 'Lose':
        held = times >= hold_begin
        root_values[held] = root_values[np.flatnonzero(held)[0]]
        for values in rotations.values():
            values[held] = values[np.flatnonzero(held)[0]]
        for values in translations.values():
            values[held] = values[np.flatnonzero(held)[0]]
    if name == 'Attack' or name in ('Idle', 'Walk', 'Run', 'Defend', 'Lose', 'Victory'):
        _fit_prop_grips(target_rig, int(builder.c['id']), name, rotations, translations, root_values, fade)
        if int(builder.c['id']) != 7:
            clip['extras']['gripAdaptation'] = 'Wrist orientation and target finger curl only; native shoulders and elbows retained'
    maximum_floor_lift = _fit_geometry_floor(builder._motion_floor, rotations, translations, root_values)
    clip['extras']['geometryFloorFit'] = True
    clip['extras']['skinnedGeometryFloorFit'] = {'maximumRootRaiseMeters': maximum_floor_lift,
                                              'bindFloorMeters': builder._motion_floor.floor,
                                              'includes': ['body', 'clothing', 'hair', 'props']}
    if loop:
        root_values[-1] = root_values[0]
    if name == 'Lose':
        held = times >= hold_begin
        # The terminal geometry is static; keep every held transform bitwise
        # equal after the floor and fitted-grip passes as well.
        root_values[held] = root_values[-1]
        for values in rotations.values():
            values[held] = values[-1]
        for values in translations.values():
            values[held] = values[-1]
    input_accessor = builder.acc(times.astype('<f4'), 'SCALAR', 5126)
    for node, values in sorted(rotations.items()):
        _append_channel(builder, clip, input_accessor, target_rig, node, 'rotation', values)
    for node, values in sorted(translations.items()):
        _append_channel(builder, clip, input_accessor, target_rig, node, 'translation', values)
    _append_channel(builder, clip, input_accessor, target_rig, root, 'translation', root_values)
    return clip, provenance


def add_catalog_motions(builder):
    """Install the curated motions and attach reviewable per-clip provenance."""
    number = int(builder.c['id'])
    selections = {'Run': _RUN[number], 'Defend': _DEFEND[number], 'Lose': _LOSE[number]}
    if number in _ADDITIONS:
        donor, idle, walk, victory = _ADDITIONS[number]
        selections.update(Idle=(donor, 'Cafe_Idle', idle), Walk=(donor, 'Cafe_Walk', walk),
                          Victory=(donor, 'Victory_Start', victory), Attack=_ATTACK[number])
    rig = _Rig(builder.doc)
    builder._motion_floor = _SkinFloor(builder, rig)
    replacements, selected = {}, {}
    builder.motion_sources = getattr(builder, 'motion_sources', {})
    for name, selection in selections.items():
        clip, provenance = _retarget(builder, name, selection, rig)
        replacements[name] = clip
        selected[name] = provenance['source_clip']
        builder.motion_sources[name] = provenance
    builder.doc['animations'] = [replacements.get(a['name'], a) for a in builder.doc['animations']]
    return selected


def motion_fingerprint(doc, accessor, animation, samples=41):
    """Numeric body-motion signature; independent of rig IDs and file names.

    Compare rotations at normalized phases, relative to each target rest pose.
    This exposes duplicate performances even if metadata or durations differ.
    """
    rig = _Rig(doc)
    channels = {c['target']['node']: c for c in animation['channels'] if c['target']['path'] == 'rotation'}
    times = [np.asarray(accessor(s['input'])).reshape(-1) for s in animation['samplers']]
    sample_times = np.linspace(min(t[0] for t in times), max(t[-1] for t in times), samples)
    values = []
    for name in ['Bip001 Pelvis', 'Bip001 Spine', 'Bip001 Spine1', 'Bip001 Head'] + [
            f'Bip001 {side} {part}' for side in ('L', 'R')
            for part in ('Thigh', 'Calf', 'Foot', 'UpperArm', 'Forearm', 'Hand')]:
        node = rig.bones.get(name)
        if node is None:
            values.append(np.tile(_IDENTITY, (samples, 1)))
            continue
        channel = channels.get(node)
        array = (_native_samples(accessor, animation['samplers'][channel['sampler']], 'rotation', sample_times)
                 if channel else np.tile(rig.q[node], (samples, 1)))
        inverse = _qinv(rig.q[node])
        array = np.asarray([_qmul(q, inverse) for q in array])
        array *= np.where(array[:, -1:] < 0, -1, 1)
        values.append(array)
    result = np.asarray(values)
    return result, hashlib.sha256(np.round(result, 4).astype('<f4').tobytes()).hexdigest()


def motion_distance(first, second):
    """RMS angular difference in degrees across anatomical bones and phases."""
    first, second = np.asarray(first,dtype=float), np.asarray(second,dtype=float)
    first = first/np.maximum(np.linalg.norm(first,axis=-1,keepdims=True),_EPS)
    second = second/np.maximum(np.linalg.norm(second,axis=-1,keepdims=True),_EPS)
    cosine = np.clip(np.abs((first*second).sum(-1)), 0, 1)
    return float(2*np.degrees(np.sqrt(np.mean(np.arccos(cosine)**2))))
