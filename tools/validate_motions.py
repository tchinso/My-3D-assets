"""Audit exported anatomical motion individuality and optional preservation.

Compare 41 normalized phases of body rotations, independently of donor names,
mesh geometry and playback duration. --before accepts earlier GLBs named by
slug, checks the ten replaced Attacks, and preserves every other established
clip. Only vertical root floor fitting may change for edited accessories 7/12.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from validate_characters import Asset, REQUIRED_CLIPS, anatomical_bones
from source_motion_refresh import motion_fingerprint, motion_distance


NEAR_SHARED_DEGREES = 5.
# motion_fingerprint orders pelvis/spine/head, then six joints per side.
# Fitted prop wrists must not make otherwise shared body attacks look unique.
CORE_BODY_INDICES = [index for index in range(16) if index not in (9, 15)]
FLOOR_EDIT_IDS = {7, 12}
TRACK_TOLERANCE = 2e-6


def _target_keys(doc):
    """Stable hierarchy paths survive accessor and unrelated node reordering."""
    nodes = doc['nodes']
    parents = {child: index for index, node in enumerate(nodes) for child in node.get('children', [])}
    roots = [index for index in range(len(nodes)) if index not in parents]
    keys = {}

    def visit(siblings, prefix):
        occurrences = {}
        for index in siblings:
            name = nodes[index].get('name', '<unnamed>')
            ordinal = occurrences.get(name, 0)
            occurrences[name] = ordinal+1
            keys[index] = prefix+((name, ordinal),)
            visit(nodes[index].get('children', []), keys[index])

    visit(roots, ())
    return keys, parents


def preserved_tracks(before, after, old_clip, new_clip, allow_floor_fit=False):
    """Check all exported tracks, including cloth, root travel and key timing.

    Anatomical fingerprints intentionally ignore translations and secondary
    joints; preservation must check them too. Accessor IDs and clip metadata
    are not compared because serialization and provenance can change safely.
    """
    old_keys, _ = _target_keys(before.doc)
    new_keys, parents = _target_keys(after.doc)
    old_channels = {(old_keys[channel['target']['node']], channel['target']['path']): channel
                    for channel in old_clip['channels']}
    new_channels = {(new_keys[channel['target']['node']], channel['target']['path']): channel
                    for channel in new_clip['channels']}
    differences = []
    maximum_change, maximum_floor_adjustment = 0., 0.
    if old_channels.keys() != new_channels.keys():
        differences.append('Animated targets changed')
    root = anatomical_bones(after).get('Bip001')
    world = after.world() if allow_floor_fit else None
    for key in old_channels.keys() & new_channels.keys():
        old_channel, new_channel = old_channels[key], new_channels[key]
        old_sampler = old_clip['samplers'][old_channel['sampler']]
        new_sampler = new_clip['samplers'][new_channel['sampler']]
        label = '/'.join(name for name, _ in key[0])+':'+key[1]
        if old_sampler.get('interpolation', 'LINEAR') != new_sampler.get('interpolation', 'LINEAR'):
            differences.append(f'{label} interpolation changed')
        old_times = before.accessor(old_sampler['input'])
        new_times = after.accessor(new_sampler['input'])
        if old_times.shape != new_times.shape or not np.allclose(old_times, new_times, rtol=0, atol=1e-7):
            differences.append(f'{label} key timing changed')
            continue
        old_values = before.accessor(old_sampler['output']).astype(float)
        new_values = after.accessor(new_sampler['output']).astype(float)
        if old_values.shape != new_values.shape:
            differences.append(f'{label} output shape changed')
            continue
        delta = new_values-old_values
        node = new_channel['target']['node']
        if allow_floor_fit and node == root and key[1] == 'translation':
            # A root may have a rotated/scaled parent. Permit only world-up
            # displacement rather than assuming its local Y axis is vertical.
            parent = parents.get(node)
            basis = world[parent][:3, :3] if parent is not None else np.eye(3)
            delta = delta @ basis.T
            maximum_floor_adjustment = max(maximum_floor_adjustment, float(np.abs(delta[:, 1]).max()))
            delta = delta[:, (0, 2)]
        elif key[1] == 'rotation':
            # q and -q represent the same rotation.
            delta = np.minimum(np.linalg.norm(delta, axis=1), np.linalg.norm(new_values+old_values, axis=1))
        change = float(np.abs(delta).max())
        maximum_change = max(maximum_change, change)
        if change > TRACK_TOLERANCE:
            differences.append(f'{label} values changed by {change:.7g}')
    return {'checked_tracks': len(old_channels), 'max_preserved_value_change': maximum_change,
            'allowed_vertical_root_adjustment_meters': maximum_floor_adjustment,
            'track_differences': differences}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root/'characters/manifest.json').read_text(encoding='utf-8'))
    report = {'sample_phases': 41, 'near_shared_threshold_degrees': NEAR_SHARED_DEGREES,
              'attack_comparison': 'Rest-relative anatomical rotations excluding fitted wrists; normalized playback phases',
              'categories': {}, 'preserved_original_clips': [], 'replaced_attack_clips': [], 'errors': []}
    curves = {name: [] for name in ('Run', 'Defend', 'Lose', 'Walk', 'Victory', 'Attack')}
    for entry in manifest:
        asset = Asset(root/entry['glb'])
        clips = {clip['name']: clip for clip in asset.doc['animations']}
        for name in curves:
            array, digest = motion_fingerprint(asset.doc, asset.accessor, clips[name])
            curves[name].append((entry['id'], entry['name'], array, digest, entry['motion_sources'].get(name)))
        if args.before:
            before = Asset(args.before/f"{entry['slug']}.glb")
            old_clips = {clip['name']: clip for clip in before.doc['animations']}
            for name in REQUIRED_CLIPS:
                old, _ = motion_fingerprint(before.doc, before.accessor, old_clips[name])
                new, _ = motion_fingerprint(asset.doc, asset.accessor, clips[name])
                distance = motion_distance(old, new)
                if name == 'Attack' and entry['id'] <= 10:
                    core_distance = motion_distance(old[CORE_BODY_INDICES], new[CORE_BODY_INDICES])
                    report['replaced_attack_clips'].append({'character': entry['name'], 'rms_degrees': distance,
                                                           'core_body_rms_degrees': core_distance})
                    if core_distance < NEAR_SHARED_DEGREES:
                        report['errors'].append(f"Replaced {entry['name']}/Attack remains near its former performance ({core_distance:.4f} degrees)")
                    continue
                preservation = preserved_tracks(before, asset, old_clips[name], clips[name],
                                                entry['id'] in FLOOR_EDIT_IDS)
                result = {'character': entry['name'], 'clip': name, 'rms_degrees': distance, **preservation}
                report['preserved_original_clips'].append(result)
                if distance > .01 or preservation['track_differences']:
                    report['errors'].append(f"Preserved {entry['name']}/{name} changed: {distance:.4f} degrees; "
                                            +'; '.join(preservation['track_differences']))
    for name, items in curves.items():
        pairs, donors = [], {}
        for i, first in enumerate(items):
            if name in ('Run', 'Defend', 'Lose', 'Attack'):
                provenance = first[4] or {}
                donor = provenance.get('source_file', '')
                source_clip = provenance.get('source_clip', '')
                key = donor.casefold()
                if not donor or not source_clip:
                    report['errors'].append(f"{first[1]}/{name} lacks native donor provenance")
                elif key in donors:
                    report['errors'].append(f"Reused {name} donor {donor}: {donors[key]}, {first[1]}")
                else:
                    donors[key] = first[1]
            for second in items[i+1:]:
                distance = motion_distance(first[2], second[2])
                pair = {'characters': [first[1], second[1]], 'rms_degrees': distance}
                if name == 'Attack':
                    core_distance = motion_distance(first[2][CORE_BODY_INDICES], second[2][CORE_BODY_INDICES])
                    pair['core_body_rms_degrees'] = core_distance
                    if core_distance < NEAR_SHARED_DEGREES:
                        report['errors'].append(f"Near-shared Attack performance: {pair}")
                pairs.append(pair)
                if first[3] == second[3] and (name in ('Run', 'Defend', 'Lose', 'Attack') or first[0] >= 11 or second[0] >= 11):
                    report['errors'].append(f"Duplicated {name}: {first[1]}, {second[1]}")
        pairs.sort(key=lambda pair: pair.get('core_body_rms_degrees', pair['rms_degrees']))
        report['categories'][name] = {
            'unique_anatomical_fingerprints': len({item[3] for item in items}),
            'unique_native_donors': len(donors) if donors else None,
            'nearest_pairs': pairs[:3],
            'characters': [{'name': item[1], 'sha256': item[3], 'source': item[4]} for item in items]}
        if name in ('Run', 'Defend', 'Lose') and pairs and pairs[0]['rms_degrees'] < NEAR_SHARED_DEGREES:
            report['errors'].append(f"Near-shared {name} performance: {pairs[0]}")
    report['summary'] = {
        'characters': len(manifest),
        'replaced_clips': sum(7 if entry['id'] >= 11 else 4 for entry in manifest),
        'refreshed_attack_clips': sum(entry['id'] <= 10 for entry in manifest),
        'preserved_attack_clips': sum(entry['id'] >= 11 for entry in manifest),
        'replaced_attacks_checked': len(report['replaced_attack_clips']),
        'preserved_clips_checked': len(report['preserved_original_clips']),
        'errors': len(report['errors']), 'status': 'passed' if not report['errors'] else 'failed'}
    (root/'previews/motion_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['summary']))
    for name in ('Run', 'Defend', 'Lose', 'Attack'):
        if report['categories'][name]['nearest_pairs']:
            print(name, report['categories'][name]['nearest_pairs'][0])
    if report['errors']:
        print('\n'.join(report['errors']))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
