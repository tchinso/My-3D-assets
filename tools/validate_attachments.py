"""Verify Kimon's animated bow contact and Momo's isolated tail removal.

Usage: python tools/validate_attachments.py --before tmp/before-assets
Writes previews/attachment_validation.json and exits nonzero on a failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from render_core import GLB
from render_attachment_changes import ROOT, asset_path


CLIPS=('Idle','Walk','Run','Attack','Defend','Victory','Lose')


def momo_check(root,before):
    slug='07_neon_cat'
    old=GLB(asset_path(before,slug));new=GLB(asset_path(root,slug))
    tails=[m for m in old.doc['meshes'] if m['name']=='Curled cat tail']
    retained=[m for m in old.doc['meshes'] if m['name']!='Curled cat tail']
    errors=[];comparisons=0
    if len(tails)!=1:errors.append('Expected one original Momo cat-tail mesh')
    if any('cat tail' in m.get('name','').lower() for m in new.doc['meshes']):
        errors.append('Momo still contains a cat-tail mesh')
    if len(retained)!=len(new.doc['meshes']):errors.append('Momo retained mesh count changed')
    for a,b in zip(retained,new.doc['meshes']):
        if a['name']!=b['name']:
            errors.append(f'Momo retained mesh changed: {a["name"]}');continue
        if len(a['primitives'])!=len(b['primitives']):errors.append(f'Momo primitive count changed: {a["name"]}')
        for pa,pb in zip(a['primitives'],b['primitives']):
            if set(pa['attributes'])!=set(pb['attributes']):
                errors.append(f'Momo attribute set changed: {a["name"]}');continue
            for attr in pa['attributes']:
                comparisons+=1
                if not np.array_equal(old.accessor(pa['attributes'][attr]),new.accessor(pb['attributes'][attr])):
                    errors.append(f'Momo retained buffer changed: {a["name"]} / {attr}')
            comparisons+=1
            if not np.array_equal(old.accessor(pa['indices']),new.accessor(pb['indices'])):
                errors.append(f'Momo retained indices changed: {a["name"]}')
    removed=sum(old.accessor(p['indices']).size//3 for m in tails for p in m['primitives'])
    return {'non_tail_mesh_buffers_identical':not errors,'buffers_compared':comparisons,
            'removed_tail_triangles':removed},errors


def kimon_check(root):
    glb=GLB(asset_path(root,'12_kimon_fox_idol'))
    knot_node=next(n for n in glb.doc['nodes'] if n.get('name')=='Kimon orange bow tie knot')
    cloth_node=next(n for n in glb.doc['nodes'] if n.get('name','').startswith('Reference donor garment'))
    knot=glb.doc['meshes'][knot_node['mesh']]['primitives'][0]
    cloth=glb.doc['meshes'][cloth_node['mesh']]['primitives'][0]
    fit=glb.doc['extras']['appearance_fit']['clothing_ribbon']
    anchor=np.asarray(fit['knot_anchor']);clearance=float(fit['surface_clearance'])
    kp=glb.accessor(knot['attributes']['POSITION']);cp=glb.accessor(cloth['attributes']['POSITION'])
    ci=glb.accessor(cloth['indices']).reshape(-1,3)
    ki=int(np.argmin(np.linalg.norm(kp-anchor,axis=1)))
    if np.linalg.norm(kp[ki]-anchor)>1e-6:raise ValueError('Kimon knot contact vertex misses its recorded anchor')
    triangles=cp[ci];a=triangles[:,0,:2];ab=triangles[:,1,:2]-a;ac=triangles[:,2,:2]-a;ap=anchor[:2]-a
    determinant=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
    denominator=np.where(np.abs(determinant)>1e-12,determinant,1)
    u=(ap[:,0]*ac[:,1]-ap[:,1]*ac[:,0])/denominator
    v=(ab[:,0]*ap[:,1]-ab[:,1]*ap[:,0])/denominator
    bary=np.c_[1-u-v,u,v]
    inside=(bary>=-1e-7).all(1)&(np.abs(determinant)>1e-12)
    if not inside.any():raise ValueError('Kimon knot anchor has no supporting blouse triangle')
    depth=(triangles[:,:,2]*bary).sum(1)
    ti=int(np.argmax(np.where(inside,depth,-np.inf)))
    if knot_node['skin']!=cloth_node['skin']:raise ValueError('Kimon bow and blouse use different skins')
    skin=glb.doc['skins'][knot_node['skin']]
    inverse=glb.accessor(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)

    def vertex_data(primitive,vertices):
        attrs=primitive['attributes']
        return (glb.accessor(attrs['POSITION'])[vertices],glb.accessor(attrs['JOINTS_0'])[vertices].astype(int),
                glb.accessor(attrs['WEIGHTS_0'])[vertices])

    knot_data=vertex_data(knot,[ki]);cloth_data=vertex_data(cloth,ci[ti])

    def deform(data,matrices):
        pos,joints,weights=data;blend=(matrices[joints]*weights[:,:,None,None]).sum(1)
        return np.einsum('nij,nj->ni',blend,np.c_[pos,np.ones(len(pos))])[:,:3]

    errors=[];gaps={};samples=33;tolerance=2e-5
    for clip in CLIPS:
        if clip not in glb.animations:
            errors.append(f'Kimon missing clip: {clip}');continue
        distances=[]
        for time in np.linspace(0,glb.duration(clip),samples):
            glb.evaluate(clip,float(time))
            matrices=np.asarray([glb.global_mats[joint]@inverse[k] for k,joint in enumerate(skin['joints'])])
            knot_point=deform(knot_data,matrices)[0]
            cloth_point=(deform(cloth_data,matrices)*bary[ti,:,None]).sum(0)
            distances.append(float(np.linalg.norm(knot_point-cloth_point)))
        deviations=np.abs(np.asarray(distances)-clearance)
        gaps[clip]={'minimum_gap':min(distances),'maximum_gap':max(distances),
                    'maximum_contact_error':float(deviations.max())}
        if not np.isfinite(distances).all() or deviations.max()>tolerance:
            errors.append(f'Kimon knot loses blouse contact in {clip}')
    return {'samples_per_clip':samples,'surface_clearance':clearance,'contact_error_tolerance':tolerance,
            'gap_by_clip':gaps,'contact_preserved':not errors},errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();report={'errors':[]}
    for name,check in (('Momo',lambda:momo_check(args.root,args.before)),('Kimon',lambda:kimon_check(args.root))):
        try:
            details,errors=check();report[name]=details;report['errors'].extend(errors)
        except (KeyError,IndexError,ValueError,FileNotFoundError,StopIteration) as exc:
            report['errors'].append(f'{name}: {type(exc).__name__}: {exc}')
    report['valid']=not report['errors']
    target=args.report or args.root/'previews'/'attachment_validation.json'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'valid':report['valid'],'report':str(target),'errors':report['errors']},indent=2))
    raise SystemExit(0 if report['valid'] else 1)


if __name__=='__main__':
    main()
