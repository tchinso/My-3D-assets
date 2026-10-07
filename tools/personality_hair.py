"""Reference hair edits for Marin, Viola and Rosette, using donor topology.

The source GLBs stay read-only. Fitted tail vertices and rest pivots receive
matching fits before animation retargeting. Geometry-selected mint gradient
materials preserve the source shading even when source UV islands overlap.
"""
from __future__ import annotations

import math
import copy
import numpy as np
from PIL import Image


def _names(part):
    return np.asarray([str(name).lower() for name in part['names']])


def _dominant(part, vertices):
    joints = part['j'][vertices]
    weights = part['w'][vertices]
    return _names(part)[joints[np.arange(len(vertices)), weights.argmax(1)]]


def _rosette_forehead_curl(points):
    q = np.asarray(points, dtype=float).copy()
    source = q.copy()
    q[:, 0] = .012+(source[:, 1]-1.006)*1.45
    q[:, 1] = .899-(source[:, 0]-.035)*.93
    q[:, 2] = .12
    return q


def _fit_to_forehead(curl, source_pos, source_idx):
    """Lay the reused curl on the actual front hair surface in XY projection."""
    q = curl.copy()
    triangles = source_pos[source_idx]
    triangles = triangles[(triangles[:, :, 1].min(1) > .80) & (triangles[:, :, 2].max(1) > .07)]
    for point in q:
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        v0, v1, v2 = b[:, :2]-a[:, :2], c[:, :2]-a[:, :2], point[:2]-a[:, :2]
        den = v0[:, 0]*v1[:, 1]-v1[:, 0]*v0[:, 1]
        valid = np.abs(den) > 1e-10
        den = np.where(valid, den, 1)
        u = (v2[:, 0]*v1[:, 1]-v1[:, 0]*v2[:, 1])/den
        v = (v0[:, 0]*v2[:, 1]-v2[:, 0]*v0[:, 1])/den
        inside = valid & (u >= -.001) & (v >= -.001) & (u+v <= 1.001)
        if inside.any():
            z = a[:, 2]+u*(b[:, 2]-a[:, 2])+v*(c[:, 2]-a[:, 2])
            point[2] = z[inside].max()+.0015
    return q


def _marin_native_tail_fit(points):
    """Keep Yoshimi's actual full loose curls and fit their root to Miku's cap."""
    q = np.asarray(points, dtype=float).copy()
    side = np.where(q[:, 0] < 0, -1, 1)
    q[:, 0] = side*(.150+(np.abs(q[:, 0])-.150)*1.16)
    q[:, 1] = .905+(q[:, 1]-.905)*1.325
    q[:, 2] += .059
    return q


def _rosette_seia_tail_fit(points):
    """Fit Seia's actual broad two-turn spiral ponytail, preserving its volume."""
    q = np.asarray(points, dtype=float).copy()
    side = np.where(q[:, 0] < 0, -1, 1)
    spread = np.clip((.820-q[:, 1])/.19, 0, 1)
    spread = spread*spread*(3-2*spread)
    q[:, 0] = side*(np.abs(q[:, 0])-.004+.048*spread)
    q[:, 1] = .864+.90*(q[:, 1]-.820)
    q[:, 2] += .032+.040*spread
    return q


def _rosette_face_lock_fit(points):
    """Let the original small cheek locks continue softly below the collar."""
    q = np.asarray(points, dtype=float).copy()
    lower = np.clip((.742-q[:, 1])/.092, 0, 1)
    q[:, 1] -= .073*lower
    q[:, 0] += np.sign(q[:, 0])*.010*lower
    q[:, 2] += .024*lower
    return q


def add_mirrored_rosette_tail(builder, part, source):
    """Import a mirrored copy with its own fitted donor joint hierarchy."""
    mirrored = copy.copy(source)
    mirrored.name = source.name+' mirror'
    reflection = np.diag([-1., 1, 1, 1])
    mirrored.world = {index: reflection @ world @ reflection for index, world in source.world.items()}
    mirrored_part = part.copy()
    mirrored_part['pos'] = part['pos']*[-1, 1, 1]
    mirrored_part['norm'] = part['norm']*[-1, 1, 1]
    mirrored_part['idx'] = part['idx'][:, [0, 2, 1]]
    builder.add_source(mirrored_part, mirrored, 'hair')


def select_and_fit(builder, part, source, groups):
    """Keep complete hair locks and fit their existing vertex positions."""
    cid = builder.c['id']
    pos, idx = part['pos'].copy(), part['idx'].copy()
    keep = np.ones(len(idx), dtype=bool)
    if cid == 1:
        if source.name == 'Erika':
            keep[:] = False
            for group in groups:
                vertices = np.unique(idx[group]); names = _dominant(part, vertices)
                if any(n.startswith('bone_hair_t_') for n in names):
                    keep[group] = True
            return pos, idx[keep]
        if source.name == 'Yoshimi':
            keep[:] = False; selected = []
            for group in groups:
                vertices = np.unique(idx[group]); names = _dominant(part, vertices)
                if any(n.startswith(('bone_hair_b_l_', 'bone_hair_b_r_')) for n in names):
                    keep[group] = True; selected.extend(vertices)
            vertices = np.unique(selected)
            pos[vertices] = _marin_native_tail_fit(pos[vertices])
            return pos, idx[keep]
        # Keep Miku's crown and fringe. Yoshimi supplies the complete curled
        # tails, while physical navy bows replace Miku's neon tie rectangles.
        for group in groups:
            vertices = np.unique(idx[group]); q = pos[vertices]
            names = _dominant(part, vertices)
            if any(n.startswith(('bone_hair_b_l_', 'bone_hair_b_r_')) for n in names):
                keep[group] = False
                continue
            tie = (len(group) <= 6 and q[:, 1].min() > .84 and q[:, 1].max() < .94
                   and np.abs(q[:, 0]).mean() > .11
                   and all(n.startswith(('bone_hair_b_l_01', 'bone_hair_b_r_01')) for n in names))
            if tie:
                keep[group] = False
        builder.appearance_fit['hair'] = {
            'method': 'Miku crown and fringe with Yoshimi actual substantial loose curled twin-tail locks, fitted root and gently lengthened silhouette',
            'root_ornaments': ['woven pink side braids', 'navy silk bows', 'small pearls', 'tea cup and spoon charms'],
            'hair_tint': '#ed9bc2', 'donor_ahoge': 'selective Erika curved ahoge',
            'curl_turns_per_side': 'one to two gentle donor turns', 'tail_rest_pivots': 'matched to fitted donor locks',
            'cross_section_fit': 'Actual donor solid curl topology preserved; lateral scale 1.16, length scale 1.325 with the root fixed',
        }
    elif cid == 2:
        # Erika provides real short layered locks, a curved ahoge and flipping
        # sides. Sweep the fringe across the forehead and lift the lower ends.
        used = np.unique(idx); q = pos[used].copy()
        front = np.clip((q[:, 2]-.055)/.075, 0, 1)
        fringe = front*np.clip((.96-q[:, 1])/.19, 0, 1)
        q[:, 0] += .021*fringe
        lower = np.clip((.81-q[:, 1])/.14, 0, 1)
        side = np.clip((np.abs(q[:, 0])-.095)/.065, 0, 1)
        q[:, 0] += np.sign(q[:, 0])*.045*lower*side
        q[:, 1] += .027*lower*side
        q[:, 2] += .010*lower*side
        pos[used] = q
        builder.appearance_fit['hair'] = {
            'method': 'Erika short layered bob, fitted side-swept fringe, face-framing locks and outward lifted tips',
            'hair_tint': '#5456c9', 'donor_ahoge': 'retained',
        }
    elif cid == 8:
        if source.name == 'Erika':
            keep[:] = False; selected = []
            for group in groups:
                vertices = np.unique(idx[group]); names = _dominant(part, vertices)
                if any(n.startswith('bone_hair_t_') for n in names):
                    keep[group] = True; selected.extend(vertices)
            vertices = np.unique(selected)
            crown = next(p for p in builder.source('Reisa (Magical)').parts() if 'hair' in p['mat']['name'].lower())
            curl = _fit_to_forehead(_rosette_forehead_curl(pos[vertices]), crown['pos'], crown['idx'])
            head = next(i for i, node in enumerate(source.doc['nodes']) if node.get('name') == 'Bip001 Head' and i in source.world)
            delta = builder.headpos-source.world[head][:3, 3]; delta[1] += builder.head_adjust
            pos[vertices] = curl+[0, builder.head_adjust, 0]-delta
            return pos, idx[keep]
        if source.name.startswith('Seia (Swimsuit)'):
            keep[:] = False; selected = []
            for group in groups:
                vertices = np.unique(idx[group]); names = _dominant(part, vertices)
                if any(n.startswith(('bone_hair_01', 'bone_hair_02', 'bone_hair_03', 'bone_hair_04')) for n in names):
                    keep[group] = True; selected.extend(vertices)
            vertices = np.unique(selected)
            pos[vertices] = _rosette_seia_tail_fit(pos[vertices])
            return pos, idx[keep]
        framing, long_framing = [], []
        for group in groups:
            vertices = np.unique(idx[group]); names = _dominant(part, vertices)
            if any(n.startswith(('bone_hair_l_0', 'bone_hair_r_0')) for n in names):
                keep[group] = False
            elif any(n.startswith('bone_hair_t_') for n in names):
                keep[group] = False
            elif any(n.startswith(('bone_hair_rll_', 'bone_hair_fll_')) for n in names):
                long_framing.extend(vertices)
            elif any(n.startswith(('bone_hair_fr_', 'bone_hair_fl_')) for n in names):
                framing.extend(vertices)
        if framing:
            vertices = np.unique(framing); q = pos[vertices].copy()
            lower = np.clip((.79-q[:, 1])/.13, 0, 1)
            q[:, 1] -= .016*lower
            q[:, 0] += np.sign(q[:, 0])*.010*lower
            pos[vertices] = q
        if long_framing:
            vertices = np.unique(long_framing)
            pos[vertices] = _rosette_face_lock_fit(pos[vertices])
        builder.appearance_fit['hair'] = {
            'method': 'Reisa Magical crown and framing locks with two fitted Seia Swimsuit solid spiral ponytail copies, one mirrored with independent joints; Erika curved ahoge fitted as a wide forehead curl',
            'curl_turns_per_side': 'two broad actual donor spiral turns', 'tail_length_scale': .90,
            'curl_volume_fit': 'Actual continuous solid spiral topology retained, including its nonmonotonic front/back depth; no guide loops or ribbon transport',
            'hair_tint': '#f5c3d3', 'curled_tip_tint': '#91ded9',
            'gradient_method': 'Geometry-selected gradient bands with the original shaded UV atlas; overlapping islands remain independent',
            'face_framing': 'retained fringe, cheek locks extended below the collar and enlarged surface-fitted central forehead curl',
        }
    return pos, idx[keep]


def recolor(builder, part, image):
    """Preserve each source hair atlas's painted shading."""
    a = np.asarray(image).copy()
    lum = a[:, :, :3].astype(float) @ np.array([.27, .57, .16])/255
    color = np.array([int(builder.c['hair_color'][i:i+2], 16) for i in (1, 3, 5)], dtype=float)
    shade = .73+.27*lum if builder.c['id'] != 8 else .80+.20*lum
    tint = np.broadcast_to(color, (*lum.shape, 3)).copy()
    a[:, :, :3] = np.clip(tint*shade[:, :, None], 0, 255).astype('u1')
    return Image.fromarray(a)


def emit_rosette(builder, part, source, pos, idx, uv, norm, joints, weights, original_vertices, image):
    """Avoid tinting upper coils that reuse the same UVs as the mint ends.

    Only the selected donor triangles change materials. Source positions,
    normals, UVs and skinning remain on the complete fitted locks.
    """
    if builder.c['id'] != 8:
        return False
    names = _names(part)
    tail_bones = np.array([n.startswith(('bone_hair_01', 'bone_hair_02', 'bone_hair_03', 'bone_hair_04')) for n in names])
    tail_weight = (tail_bones[part['j']]*part['w']).sum(1)[original_vertices]
    original_height = part['pos'][original_vertices, 1]
    amount = np.clip((.60-original_height)/.15, 0, 1)*np.clip(tail_weight, 0, 1)
    bands = np.round(amount[idx].mean(1)*16).astype(int)
    ahoge_bones = np.array([n.startswith('bone_hair_t_') for n in names])
    curl_weight = (ahoge_bones[part['j']]*part['w']).sum(1)[original_vertices]
    curl = curl_weight[idx].max(1) > .05
    bands[curl] = 17
    array = np.asarray(image).copy()
    pink = np.array([245, 195, 211], dtype=float)
    shade = np.mean(array[:, :, :3].astype(float)/pink, axis=2)
    for band in np.unique(bands):
        color = np.array([229, 164, 190], dtype=float) if band == 17 else pink+(np.array([145, 222, 217])-pink)*(band/16)
        tinted = array.copy(); tinted[:, :, :3] = np.clip(color*shade[:, :, None], 0, 255).astype('u1')
        label = 'central forehead curl' if band == 17 else f'curl gradient {band:02d}'
        material = builder.wardrobe_material(source.name+'/'+part['mat']['name']+'/'+label, part, Image.fromarray(tinted))
        builder.mesh('Hair / '+source.name+' / '+label, pos, idx[bands == band], material,
                     j=joints, w=weights, uv=uv, norm=norm)
    return True


def fit_rest_pivots(builder):
    """Match changed hair pivots while preserving the garment/body skeleton."""
    if builder.c['id'] not in (1, 8):
        return
    changed = set()
    delta = np.zeros(3)
    if builder.c['id'] == 1:
        source = builder.source('Yoshimi')
        source_head = next(i for i, node in enumerate(source.doc['nodes']) if node.get('name') == 'Bip001 Head' and i in source.world)
        delta = builder.headpos-source.world[source_head][:3, 3]; delta[1] += builder.head_adjust
    for name, node_index in builder.bone.items():
        key = name.lower()
        point = builder.world[node_index][:3, 3][None, :]
        if builder.c['id'] == 1 and key.startswith(('yoshimi::bone_hair_b_l_', 'yoshimi::bone_hair_b_r_')):
            target = _marin_native_tail_fit(point-delta)[0]+delta
        elif builder.c['id'] == 8 and key.startswith(('seia (swimsuit)::bone_hair_0', 'seia (swimsuit) mirror::bone_hair_0')):
            source = builder.source('Seia (Swimsuit)')
            source_head = next(i for i, node in enumerate(source.doc['nodes']) if node.get('name') == 'Bip001 Head' and i in source.world)
            tail_delta = builder.headpos-source.world[source_head][:3, 3]; tail_delta[1] += builder.head_adjust
            target = _rosette_seia_tail_fit(point-tail_delta)[0]+tail_delta
        elif builder.c['id'] == 8 and key.startswith('erika::bone_hair_t_'):
            source = builder.source('Erika')
            source_head = next(i for i, node in enumerate(source.doc['nodes']) if node.get('name') == 'Bip001 Head' and i in source.world)
            curl_delta = builder.headpos-source.world[source_head][:3, 3]; curl_delta[1] += builder.head_adjust
            target = _rosette_forehead_curl(point-curl_delta)[0]
            target[1] += builder.head_adjust
        elif builder.c['id'] == 8 and key.startswith(('bone_hair_rll_', 'bone_hair_fll_')):
            target = _rosette_face_lock_fit(point)[0]
            target[1] += builder.head_adjust
        else:
            continue
        builder.world[node_index] = builder.world[node_index].copy()
        builder.world[node_index][:3, 3] = target
        changed.add(node_index)
    parents = {child: index for index, node in enumerate(builder.doc['nodes']) for child in node.get('children', [])}
    for index, node in enumerate(builder.doc['nodes']):
        if index not in builder.world or (index not in changed and parents.get(index) not in changed):
            continue
        parent = parents.get(index)
        local = np.linalg.inv(builder.world[parent]) @ builder.world[index] if parent is not None else builder.world[index]
        for key in ('translation', 'rotation', 'scale'):
            node.pop(key, None)
        node['matrix'] = local.T.reshape(-1).tolist()


def ornaments(builder):
    """Marin's restrained service details sit at the existing tail roots."""
    if builder.c['id'] != 1:
        return
    source = builder.source('Hatsune Miku')
    source_head = next(i for i, node in enumerate(source.doc['nodes']) if node.get('name') == 'Bip001 Head' and i in source.world)
    delta = builder.headpos-source.world[source_head][:3, 3]; delta[1] += builder.head_adjust
    navy = builder.material('Marin navy silk hair bows', '#192944')
    braid = builder.material('Marin woven rose hair roots', '#dc8dad')
    highlight = builder.material('Marin woven hair highlights', '#f1b3cf')
    pearl = builder.material('Marin pearl hair details', '#fff7f1')
    gold = builder.material('Marin small service hair charms', '#d2b878', metal=.55)
    for side in (-1, 1):
        for strand in range(3):
            points = []
            for t in np.linspace(0, 1, 40):
                phase = t*6*math.pi+strand*2*math.pi/3
                center = np.array([side*(.097+.083*t), .936-.068*t, .088-.114*t])
                center += np.array([side*.0022*math.cos(phase), .0038*math.sin(phase), .0038*math.cos(phase)])
                points.append(center+delta)
            builder.tube('Marin woven twin-tail root strand', points, [.0032]*len(points), highlight if strand == 1 else braid, 'Bip001 Head', 8)
        center = np.array([side*.190, .884, -.043])+delta
        builder.bow('Marin structured navy tail bow', center, .041, navy)
        builder.ellipsoid('Marin pearl bow knot', center+[0, 0, .008], (.0055, .0055, .004), pearl, seg=16, rings=8)
        for t in (.23, .39, .55, .71):
            location = np.array([side*(.097+.083*t), .940-.068*t, .097-.114*t])+delta
            builder.ellipsoid('Marin tiny braid pearl', location, (.0025, .0025, .0025), pearl, seg=12, rings=6)
        charm = center+np.array([side*.018, -.051, .010])
        builder.tube('Marin fine hanging charm cord', [center+[side*.013, -.020, .006], charm], [.0011, .0011], gold, 'Bip001 Head', 8)
        if side == -1:
            builder.tube('Marin miniature spoon handle', [charm+[0, -.010, 0], charm+[0, .007, 0]], [.0015, .0014], gold, 'Bip001 Head', 10)
            builder.ellipsoid('Marin miniature spoon bowl', charm+[0, .011, 0], (.0042, .0060, .0017), pearl, seg=16, rings=8)
        else:
            builder.ellipsoid('Marin miniature tea cup', charm, (.0065, .0046, .0045), pearl, seg=16, rings=8)
            rim = [charm+[.0064*math.cos(t), .0036, .0045*math.sin(t)] for t in np.linspace(0, 2*math.pi, 21)]
            builder.tube('Marin tea cup gold rim', rim, [.0008]*len(rim), gold, 'Bip001 Head', 8)
            handle = [charm+[.007+.0028*math.cos(t), .0028*math.sin(t), 0] for t in np.linspace(-math.pi/2, math.pi/2, 15)]
            builder.tube('Marin tea cup handle', handle, [.0010]*len(handle), gold, 'Bip001 Head', 8)
