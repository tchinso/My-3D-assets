"""Audit exported anatomical motion individuality and optional preservation.

Compare 41 normalized phases of body rotations, independently of donor names,
mesh geometry and playback duration. --before accepts a folder of earlier GLBs
named by slug, to verify preserved Idle/Walk/Attack/Victory on the first ten.
"""
import argparse
import json
from pathlib import Path

from validate_characters import Asset
from source_motion_refresh import motion_fingerprint, motion_distance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--before',type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root/'characters/manifest.json').read_text(encoding='utf-8'))
    report = {'sample_phases':41, 'categories':{}, 'preserved_original_clips':[], 'errors':[]}
    curves = {name:[] for name in ('Run','Defend','Lose','Walk','Victory','Attack')}
    for entry in manifest:
        asset = Asset(root/entry['glb'])
        clips = {clip['name']:clip for clip in asset.doc['animations']}
        for name in curves:
            array, digest = motion_fingerprint(asset.doc, asset.accessor, clips[name])
            curves[name].append((entry['id'],entry['name'],array,digest,entry['motion_sources'].get(name)))
        if args.before and entry['id'] <= 10:
            before = Asset(args.before/f"{entry['slug']}.glb")
            old_clips = {clip['name']:clip for clip in before.doc['animations']}
            for name in ('Idle','Walk','Attack','Victory'):
                old, _ = motion_fingerprint(before.doc,before.accessor,old_clips[name])
                new, _ = motion_fingerprint(asset.doc,asset.accessor,clips[name])
                distance = motion_distance(old,new)
                report['preserved_original_clips'].append({'character':entry['name'],'clip':name,'rms_degrees':distance})
                if distance > .01:
                    report['errors'].append(f"Preserved {entry['name']}/{name} changed by {distance:.4f} degrees")
    for name, items in curves.items():
        pairs = []
        for i, first in enumerate(items):
            for second in items[i+1:]:
                distance = motion_distance(first[2],second[2])
                pairs.append({'characters':[first[1],second[1]],'rms_degrees':distance})
                if first[3] == second[3] and (name in ('Run','Defend','Lose','Attack') or first[0] >= 11 or second[0] >= 11):
                    report['errors'].append(f"Duplicated {name}: {first[1]}, {second[1]}")
        pairs.sort(key=lambda pair:pair['rms_degrees'])
        report['categories'][name] = {
            'unique_anatomical_fingerprints':len({item[3] for item in items}),
            'nearest_pairs':pairs[:3],
            'characters':[{'name':item[1],'sha256':item[3],'source':item[4]} for item in items]}
        if name in ('Run','Defend','Lose') and pairs[0]['rms_degrees'] < 5:
            report['errors'].append(f"Near-shared {name} performance: {pairs[0]}")
    report['summary'] = {
        'characters':len(manifest),
        'replaced_clips':sum(7 if entry['id'] >= 11 else 3 for entry in manifest),
        'preserved_clips_checked':len(report['preserved_original_clips']),
        'errors':len(report['errors']),'status':'passed' if not report['errors'] else 'failed'}
    (root/'previews/motion_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary']))
    for name in ('Run','Defend','Lose'):
        print(name,report['categories'][name]['nearest_pairs'][0])
    if report['errors']:
        print('\n'.join(report['errors']))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
