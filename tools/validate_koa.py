"""Check Koa's exported attachment rig and render motion proofs.

No donor corpus is needed. Samples include all animation keys and interpolation
quarter steps, and floor checks use every referenced vertex, not joint proxies.
Usage: python tools/validate_koa.py [--proofs]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from render_core import GLB, Renderer, mesh_bounds


ROOT = Path(__file__).resolve().parents[1]
SLUG = '15_scarlet_familiar'
CLIPS = ('Idle', 'Walk', 'Run', 'Attack', 'Defend', 'Victory', 'Lose')
ATTACHMENTS = {'Rabu::Point_hair_B_00': 'Bip001 Head',
               'Hina::Wing_Root': 'Bip001 Spine1'}
RIG_TOLERANCE = 3e-6
FLOOR_TOLERANCE = 0.002


def sample_times(glb, clip):
    keys = np.unique(np.concatenate([glb.accessor(s['input']).ravel()
                                    for s in clip['samplers']])).astype(float)
    if len(keys) < 2:
        return keys
    return np.unique(np.r_[keys, *(keys[:-1]+np.diff(keys)*f for f in (.25, .5, .75))])


def geometry_data(glb):
    """Cache referenced positions and skin slots once for whole-mesh checks."""
    data = []
    glb.evaluate()
    first_mouth = None
    for ni in glb.active_nodes:
        node = glb.doc['nodes'][ni]
        if 'mesh' not in node:
            continue
        if node.get('name', '').lower().startswith('mouth_'):
            if first_mouth is None:
                first_mouth = ni
            elif ni != first_mouth:
                continue
        for primitive in glb.doc['meshes'][node['mesh']]['primitives']:
            attrs = primitive['attributes']
            pos = glb.accessor(attrs['POSITION'])
            used = (np.unique(glb.accessor(primitive['indices']).astype(int))
                    if 'indices' in primitive else np.arange(len(pos)))
            item = {'node': ni, 'name': node.get('name', ''),
                    'pos': np.c_[pos[used], np.ones(len(used))]}
            if 'skin' in node and 'JOINTS_0' in attrs:
                item.update(skin=node['skin'],
                            joints=glb.accessor(attrs['JOINTS_0'])[used].astype(int),
                            weights=glb.accessor(attrs['WEIGHTS_0'])[used].astype(float))
            data.append(item)
    return data


def deformed(glb, geometry, skins):
    matrices = [np.asarray([glb.global_mats[joint] @ inverse[k]
                           for k, joint in enumerate(skin['joints'])])
                for skin, inverse in skins]
    result = []
    for item in geometry:
        if 'skin' in item:
            transforms = matrices[item['skin']][item['joints']]
            position = np.einsum('vijc,vc->vij', transforms, item['pos'])[:, :, :3]
            position = (position*item['weights'][:, :, None]).sum(axis=1)
        else:
            position = (item['pos'] @ glb.global_mats[item['node']].T)[:, :3]
        result.append(position)
    return np.concatenate(result)


def triangle_contact(glb, primitive, point):
    """Locate a recorded contact on the actual indexed hair surface."""
    pos = glb.accessor(primitive['attributes']['POSITION']).astype(float)
    triangles = glb.accessor(primitive['indices']).reshape(-1, 3).astype(int)
    p = pos[triangles]
    ab, ac, ap = p[:, 1]-p[:, 0], p[:, 2]-p[:, 0], point-p[:, 0]
    aa, bb, cc = (ab*ab).sum(1), (ab*ac).sum(1), (ac*ac).sum(1)
    d, e = (ab*ap).sum(1), (ac*ap).sum(1)
    denominator = aa*cc-bb*bb
    safe = np.where(np.abs(denominator)>1e-18, denominator, 1.)
    u, v = (cc*d-bb*e)/safe, (aa*e-bb*d)/safe
    plane = np.c_[1-u-v, u, v]
    inside = (plane >= 0).all(1) & (np.abs(denominator)>1e-18)
    candidates = [plane]
    for i, j in ((0, 1), (1, 2), (2, 0)):
        edge = p[:, j]-p[:, i]
        t = np.clip(((point-p[:, i])*edge).sum(1)/np.maximum((edge*edge).sum(1), 1e-18), 0, 1)
        bary = np.zeros_like(plane)
        bary[:, i], bary[:, j] = 1-t, t
        candidates.append(bary)
    bary = np.stack(candidates)
    points = (p[None]*bary[:, :, :, None]).sum(2)
    distance = np.linalg.norm(points-point, axis=2)
    distance[0, ~inside] = np.inf
    kind, index = np.unravel_index(distance.argmin(), distance.shape)
    return triangles[index], bary[kind, index], float(distance[kind, index])


def deform_vertices(glb, node, primitive, vertices, skins):
    attrs = primitive['attributes']
    points = glb.accessor(attrs['POSITION'])[vertices]
    joints = glb.accessor(attrs['JOINTS_0'])[vertices].astype(int)
    weights = glb.accessor(attrs['WEIGHTS_0'])[vertices]
    skin, inverse = skins[node['skin']]
    matrices = np.asarray([glb.global_mats[joint] @ inverse[k] for k, joint in enumerate(skin['joints'])])
    blend = (matrices[joints]*weights[:, :, None, None]).sum(1)
    return np.einsum('nij,nj->ni', blend, np.c_[points, np.ones(len(points))])[:, :3]


def validate(glb):
    errors = []
    nodes = glb.doc['nodes']
    names = {n.get('name'): i for i, n in enumerate(nodes)}
    parents = {child: i for i, node in enumerate(nodes) for child in node.get('children', [])}
    glb.evaluate()
    bind = {i: matrix.copy() for i, matrix in glb.global_mats.items()}
    skins = [(skin, glb.accessor(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1))
             for skin in glb.doc['skins']]
    bind_error = max(float(np.abs(bind[joint] @ inverse[k]-np.eye(4)).max())
                     for skin, inverse in skins for k, joint in enumerate(skin['joints']))
    if bind_error > RIG_TOLERANCE:
        errors.append(f'Inverse bind matrices disagree with rest rig: {bind_error:.8g}')
    anchors = {}
    for name, support in ATTACHMENTS.items():
        if name not in names or support not in names:
            errors.append(f'Missing attachment/support: {name} / {support}')
            continue
        node, parent = names[name], names[support]
        ancestor = parents.get(node)
        while ancestor is not None and ancestor != parent:
            ancestor = parents.get(ancestor)
        if ancestor != parent or (name == 'Hina::Wing_Root' and parents.get(node) != parent):
            errors.append(f'{name} must follow {support}' + (' directly' if name == 'Hina::Wing_Root' else ''))
        anchors[name] = (node, parent, np.linalg.inv(bind[parent]) @ bind[node])
    head = names['Bip001 Head']
    head_descendants = {head}
    for _ in nodes:
        added = {child for parent in head_descendants for child in nodes[parent].get('children', [])}
        if added.issubset(head_descendants):
            break
        head_descendants.update(added)
    hair_node = next(n for n in nodes if n.get('name', '').startswith('Hair / Rabu'))
    hair = glb.doc['meshes'][hair_node['mesh']]['primitives'][0]
    hair_attrs = hair['attributes']
    hair_used = np.unique(glb.accessor(hair['indices']).astype(int))
    hair_weights = glb.accessor(hair_attrs['WEIGHTS_0'])[hair_used]
    hair_slots = glb.accessor(hair_attrs['JOINTS_0'])[hair_used].astype(int)
    hair_skin = glb.doc['skins'][hair_node['skin']]
    weighted_nodes = np.asarray(hair_skin['joints'])[hair_slots]
    if any(int(node) not in head_descendants for node in weighted_nodes[hair_weights > 1e-6]):
        errors.append('Hair contains weights outside the Head branch')
    hair_pos = glb.accessor(hair_attrs['POSITION'])[hair_used]
    scalp = hair_pos[:, 1] >= bind[head][1, 3]+.14
    scalp_head_weight = np.where(weighted_nodes == head, hair_weights, 0.).sum(1)[scalp]
    if not len(scalp_head_weight) or np.min(scalp_head_weight) < 1-1e-6:
        errors.append('Hair scalp is not rigidly weighted to Head')
    contacts = []
    fit = glb.doc.get('extras', {}).get('appearance_fit', {}).get('wings', {})
    for anchor in fit.get('head_anchors', []):
        position = np.asarray(anchor['position'], dtype=float)
        surface = np.asarray(anchor['surface_point'], dtype=float)
        choices = []
        for node in nodes:
            if node.get('name') != 'Koa scalloped upper bat wing':
                continue
            primitive = glb.doc['meshes'][node['mesh']]['primitives'][0]
            points = glb.accessor(primitive['attributes']['POSITION'])
            vertex = int(np.argmin(np.linalg.norm(points-position, axis=1)))
            choices.append((float(np.linalg.norm(points[vertex]-position)), node, primitive, vertex))
        gap, node, primitive, vertex = min(choices, key=lambda item: item[0])
        if gap > 1e-6:
            errors.append('Recorded upper-wing anchor is absent from exported membrane')
        triangle, bary, miss = triangle_contact(glb, hair, surface)
        if miss > 2e-5:
            errors.append('Recorded upper-wing surface point misses actual hair triangles')
        clearance = float(np.linalg.norm(position-surface))
        if clearance > .012:
            errors.append(f'Upper-wing root floats {clearance:.6f} from scalp')
        contacts.append((node, primitive, vertex, triangle, bary, clearance))
    if len(contacts) != 2:
        errors.append('Expected two recorded upper-wing surface attachments')
    geometry = geometry_data(glb)
    rest = deformed(glb, geometry, skins)
    rest_floor = float(rest[:, 1].min())
    height = float(np.ptp(rest[:, 1]))
    results = {}
    motion_sources = glb.doc.get('extras', {}).get('motion_sources', {})
    for wanted in CLIPS:
        clip = glb.animation(wanted)
        if clip is None:
            errors.append(f'Missing {wanted}')
            continue
        extras = clip.get('extras', {})
        provenance = motion_sources.get(wanted, {})
        if (extras.get('procedural') is not False or
                not extras.get('source_file', '').endswith('.glb') or
                not extras.get('source_clip') or
                any(extras.get(key) != provenance.get(key) for key in ('source_file', 'source_clip'))):
            errors.append(f'{wanted}: missing or inconsistent native motion provenance')
        targets = [(c['target']['node'], c['target']['path']) for c in clip['channels']]
        if len(targets) != len(set(targets)):
            errors.append(f'{wanted}: duplicate animation targets')
        seam = 0.
        if wanted in ('Idle', 'Walk', 'Run'):
            for channel in clip['channels']:
                sampler = clip['samplers'][channel['sampler']]
                values = glb.accessor(sampler['output'])
                first, last = values[0], values[-1]
                if channel['target']['path'] == 'rotation' and np.dot(first, last) < 0:
                    last = -last
                seam = max(seam, float(np.abs(first-last).max()))
            if seam > 1e-6:
                errors.append(f'{wanted}: loop seam differs by {seam:.8g}')
        drift = {name: 0. for name in anchors}
        contact_error = 0.
        lowest, largest_span = float('inf'), 0.
        finite = True
        times = sample_times(glb, clip)
        for time in times:
            glb.evaluate(wanted, float(time))
            for name, (node, support, local) in anchors.items():
                # Native wing root rotation supplies flex, but its origin must
                # remain seated in the torso's supporting frame.
                actual = np.linalg.inv(glb.global_mats[support]) @ glb.global_mats[node]
                difference = (actual[:3, 3]-local[:3, 3] if name == 'Hina::Wing_Root'
                              else actual-local)
                drift[name] = max(drift[name], float(np.abs(difference).max()))
            for node, primitive, vertex, triangle, bary, clearance in contacts:
                wing_point = deform_vertices(glb, node, primitive, [vertex], skins)[0]
                hair_point = (deform_vertices(glb, hair_node, hair, triangle, skins)*bary[:, None]).sum(0)
                contact_error = max(contact_error, abs(float(np.linalg.norm(wing_point-hair_point))-clearance))
            positions = deformed(glb, geometry, skins)
            finite &= bool(np.isfinite(positions).all())
            lowest = min(lowest, float(positions[:, 1].min()))
            largest_span = max(largest_span, float(np.ptp(positions, axis=0).max()))
        for name, deviation in drift.items():
            if deviation > RIG_TOLERANCE:
                errors.append(f'{wanted}: {name} loses its supporting frame ({deviation:.8g})')
        if contact_error > 2e-5:
            errors.append(f'{wanted}: upper-wing roots lose scalp contact ({contact_error:.8g})')
        if not finite:
            errors.append(f'{wanted}: posed geometry contains non-finite vertices')
        floor_penetration = max(0., rest_floor-lowest)
        if floor_penetration > FLOOR_TOLERANCE:
            errors.append(f'{wanted}: geometry crosses bind floor by {floor_penetration:.6f}')
        if largest_span > height*4:
            errors.append(f'{wanted}: posed geometry expands beyond four bind heights')
        results[wanted] = {'source_file': extras.get('source_file'),
                           'source_clip': extras.get('source_clip'),
                           'duration_seconds': glb.duration(wanted),
                           'keys_and_subframes_checked': len(times),
                           'maximum_attachment_frame_error': drift,
                           'maximum_head_wing_contact_error': contact_error,
                           'loop_endpoint_error': seam,
                           'minimum_vertex_height': lowest,
                           'maximum_floor_penetration': floor_penetration,
                           'all_vertices_finite': finite}
    return {'valid': not errors, 'errors': errors,
            'scope': 'Exported Koa rig, inverse bind matrices, attachment frames, native motion provenance, exact loops and every used skinned vertex at keys and interpolation quarter steps',
            'sha256': hashlib.sha256(glb.path.read_bytes()).hexdigest(),
            'used_vertices': sum(len(item['pos']) for item in geometry),
            'pinned_scalp_vertices': int(scalp.sum()), 'upper_wing_attachments': len(contacts),
            'maximum_bind_matrix_error': bind_error,
            'bind_floor': rest_floor, 'floor_tolerance': FLOOR_TOLERANCE,
            'attachment_frame_tolerance': RIG_TOLERANCE, 'clips': results}


def render_proofs(glb, output):
    from PIL import Image, ImageDraw
    from render_characters import font, save_preview

    width, height = 270, 350
    renderer = Renderer(width, height)
    sampled = [glb.meshes(clip, glb.duration(clip)*float(phase))
               for clip in ('Run', 'Attack') for phase in np.linspace(0, 1, 17)]
    lows, highs = zip(*(mesh_bounds(meshes) for meshes in sampled))
    bounds = np.min(lows, axis=0), np.max(highs, axis=0)
    span = bounds[1]-bounds[0]
    camera_half_height = max(span[1]/2, np.hypot(span[0], span[2])/2*height/width)*1.08
    phases = (0., .16, .32, .50, .68, .84)
    angles = (25, 90, 180)
    sequence = Image.new('RGB', (width*6, (height+42)*6+62), '#F3F5F8')
    draw = ImageDraw.Draw(sequence)
    draw.text((16, 12), 'Koa · native run and magic attack / exported GLB', fill='#15263A', font=font(24, True))
    try:
        for ci, clip in enumerate(('Run', 'Attack')):
            for ai, angle in enumerate(angles):
                for pi, phase in enumerate(phases):
                    x, y = pi*width, 62+(ci*3+ai)*(height+42)
                    image = renderer.render(glb, glb.meshes(clip, glb.duration(clip)*phase), angle=angle,
                                            bounds=bounds, camera_half_height=camera_half_height)
                    sequence.paste(image, (x, y+35))
                    draw.text((x+8, y+6), f'{clip} · {angle}° · {phase:.0%}', fill='#15263A', font=font(18))
            frames = []
            count = max(24, int(round(glb.duration(clip)*15)))
            for phase in np.linspace(0, 1, count, endpoint=False):
                frame = Image.new('RGB', (width*3, height+42), '#F3F5F8')
                label = ImageDraw.Draw(frame)
                meshes = glb.meshes(clip, glb.duration(clip)*float(phase))
                for ai, angle in enumerate(angles):
                    frame.paste(renderer.render(glb, meshes, angle=angle, bounds=bounds,
                                                camera_half_height=camera_half_height), (ai*width, 42))
                    label.text((ai*width+8, 10), f'{clip} · {angle}°', fill='#15263A', font=font(19, True))
                frames.append(frame)
            # GIF timing is quantized to centiseconds. Distribute rounding
            # across frames so the preview retains the GLB's native duration.
            ticks = np.rint(np.linspace(0, glb.duration(clip)*100, count+1)).astype(int)
            milliseconds = (np.diff(ticks)*10).tolist()
            save_preview(frames[0], output/f'koa_{clip.lower()}.gif', save_all=True,
                         append_images=frames[1:], loop=0, duration=milliseconds, disposal=2)
        save_preview(sequence, output/'koa_motion_sequence.png')
    finally:
        renderer.close()
    return ['koa_motion_sequence.png', 'koa_run.gif', 'koa_attack.gif']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--proofs', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    report_path = args.report or root/'previews'/'koa_validation.json'
    glb = GLB(root/'characters'/SLUG/f'{SLUG}.glb')
    report = validate(glb)
    if args.proofs:
        output = root/'previews'
        output.mkdir(exist_ok=True)
        report['proofs'] = render_proofs(glb, output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'valid': report['valid'], 'report': str(report_path), 'errors': report['errors']}, indent=2))
    raise SystemExit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
