"""Verify Viola's sharp crescent edge against the exported attack trajectory.

Usage: python tools/validate_cutting_edge.py character.glb --output report.json
Optional: --before earlier.glb --proof comparison.png

The test uses actual skinned blade vertices. Its outward direction is
perpendicular to the authored inner edge, rather than the inner/outer chord,
which also contains a tangential component and can give a misleading result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from render_core import GLB, Renderer, mesh_bounds


def measure(path):
    glb = GLB(path)
    duration = glb.duration('Attack')
    node = next(node for node in glb.doc['nodes']
                if node.get('name') == 'Bevelled crescent steel blade')
    primitive = glb.doc['meshes'][node['mesh']]['primitives'][0]
    attrs = primitive['attributes']
    skin = glb.doc['skins'][node['skin']]
    positions = glb.accessor(attrs['POSITION'])
    # Each authored blade station contains outer-front, inner-front,
    # outer-back, inner-back. Average front/back to remove its bevel depth.
    middle = len(positions)//4//2
    ids = np.array([(middle-1)*4+1, (middle-1)*4+3,
                    middle*4, middle*4+1, middle*4+2, middle*4+3,
                    (middle+1)*4+1, (middle+1)*4+3])
    position = np.c_[positions[ids], np.ones(len(ids))]
    joints = glb.accessor(attrs['JOINTS_0'])[ids].astype(int)
    weights = glb.accessor(attrs['WEIGHTS_0'])[ids]
    inverse = glb.accessor(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
    reports = []
    for begin, end in ((.30, .42), (.66, .78)):
        times = np.linspace(begin, end, 121)*duration
        points, outwards = [], []
        for time in times:
            glb.evaluate('Attack', float(time))
            matrices = np.array([glb.global_mats[joint] for joint in skin['joints']]) @ inverse
            blend = (matrices[joints]*weights[:, :, None, None]).sum(1)
            vertices = np.einsum('nij,nj->ni', blend, position)[:, :3]
            inner = (vertices[3]+vertices[5])*.5
            outer = (vertices[2]+vertices[4])*.5
            tangent = (vertices[6]+vertices[7]-vertices[0]-vertices[1])*.5
            tangent /= np.linalg.norm(tangent)
            outward = inner-outer
            outward -= tangent*(outward @ tangent)
            outward /= np.linalg.norm(outward)
            points.append(inner)
            outwards.append(outward)
        velocities = np.gradient(np.array(points), times, axis=0)
        signed = np.einsum('ij,ij->i', velocities, np.array(outwards))
        reports.append({
            'phase_window': [begin, end], 'samples': len(times),
            'cutting_edge_leading_fraction': float(np.mean(signed > 0)),
            'mean_signed_edge_velocity_mps': float(np.mean(signed)),
            'min_signed_edge_velocity_mps': float(np.min(signed)),
            'max_signed_edge_velocity_mps': float(np.max(signed)),
        })
    passed = (all(window['mean_signed_edge_velocity_mps'] > 0 for window in reports)
              and reports[1]['cutting_edge_leading_fraction'] >= .95)
    return {
        'file': str(Path(path).resolve()),
        'method': 'Exported skinned inner/outer blade midpoints and inner-edge tangent; sharp-edge outward normal dotted with its velocity',
        'strike_windows': reports,
        'criteria': 'Both sweep windows have positive mean edge-leading velocity; at least 95% of primary-strike samples lead with the cutting edge',
        'pass': passed,
    }


def proof(before, after, output):
    from PIL import Image, ImageDraw, ImageFont

    models = [GLB(before), GLB(after)]
    fractions = [.34, .40, .48, .56, .72, .78]
    poses = [[glb.meshes('Attack', glb.duration('Attack')*phase) for phase in fractions]
             for glb in models]
    bounds = (np.min([mesh_bounds(meshes)[0] for row in poses for meshes in row], 0),
              np.max([mesh_bounds(meshes)[1] for row in poses for meshes in row], 0))
    renderer = Renderer(230, 290)
    sheet = Image.new('RGB', (1380, 640), 'white')
    draw = ImageDraw.Draw(sheet)
    font_path = Path('C:/Windows/Fonts/arial.ttf')
    font = ImageFont.truetype(str(font_path), 16) if font_path.exists() else ImageFont.load_default(size=16)
    for row, (glb, poses) in enumerate(zip(models, poses)):
        for column, meshes in enumerate(poses):
            sheet.paste(renderer.render(glb, meshes, angle=22, bounds=bounds),
                        (column*230, row*320+30))
            label = 'Before' if row == 0 else 'Cutting edge leads'
            draw.text((column*230+8, row*320+6), f'{label} {fractions[column]}', font=font, fill='black')
    sheet.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('glb', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--before', type=Path)
    parser.add_argument('--proof', type=Path)
    args = parser.parse_args()
    if args.proof and not args.before:
        parser.error('--proof requires --before')
    report = measure(args.glb)
    if args.before:
        report['before'] = measure(args.before)
    if args.proof:
        proof(args.before, args.glb, args.proof)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
