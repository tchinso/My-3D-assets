"""Select donor fringes, loose hair, buns and ears without altering source files.

Azusa (Swimsuit)'s central fringe and face-framing locks are retained; every
lateral high ponytail and long rear bundle is excluded. Miyo supplies loose
layered back hair and the rear scalp, with its original frontal fringe removed.
The two sources have the same Head rest pivot, so their small scalp overlap
fits before the builder applies its common chin/neck adjustment.
Momo combines Miyo's fringe and framing locks with Kirara's rear waves and
spiral side buns, plus Kazusa's connected cat-ear surfaces. Meilin keeps
Serika's real curved twin-tail topology with a broader cross-section.
"""
from __future__ import annotations

import numpy as np


def hair_indices(part, source, mode, groups=None):
    """Return selected source triangles, without modifying any input.

    part is the dictionary yielded by build_characters.Source.parts(). Use
    hair_indices(part, 'Azusa (Swimsuit)', 'front') and
    hair_indices(part, 'Miyo', 'back') before mesh emission. Preserve UVs,
    normals, joints and weights; tint each donor's original hair texture.
    """
    idx = np.asarray(part['idx'])
    pos = np.asarray(part['pos'])
    names = np.asarray([str(n).lower() for n in part['names']])
    joints, weights = np.asarray(part['j']), np.asarray(part['w'])
    center = pos[idx].mean(1)
    if source == 'Azusa (Swimsuit)' and mode == 'front':
        # Head/crown, pointed central fringe, independent face-framing locks
        # and the small ahoge. Front weights prevent rear bundles attached to
        # the same scalp component from passing a component-level filter.
        allowed = np.array([n == 'bip001 head' or n.startswith(('bone_hair_f_', 'bone_hair_m_', 'bone_hair_t'))
                            for n in names])
        pony_or_back = np.array([n.startswith(('bone_hair_l_l_', 'bone_hair_r_r_', 'bone_hair_b_'))
                                 for n in names])
        coverage = (allowed[joints]*weights).sum(1)
        unwanted = (pony_or_back[joints]*weights).sum(1)
        keep = ((coverage[idx].mean(1) > .75) & (unwanted[idx].max(1) < .10)
                & (center[:, 2] > -.025) & (np.abs(center[:, 0]) < .195))
    elif source == 'Miyo' and mode in ('front', 'back'):
        front = np.array([n.startswith(('bone_f_hair', 'bone_f_l_hair', 'bone_f_r_hair')) for n in names])
        back = np.array([n.startswith(('bone_b_hair', 'bone_l_b_hair', 'bone_r_b_hair')) for n in names])
        head = np.array([n == 'bip001 head' for n in names])
        frontal = (front[joints]*weights).sum(1)
        rear = (back[joints]*weights).sum(1)
        skull = (head[joints]*weights).sum(1)
        if mode == 'back':
            keep = ((frontal[idx].max(1) < .08)
                    & ((rear[idx].mean(1) > .10)
                       | ((skull[idx].mean(1) > .80) & (center[:, 2] < .035))))
        else:
            # Preserve Miyo's actual layered fringe and long face-framing locks.
            keep = ((frontal[idx].mean(1) > .10)
                    | ((skull[idx].mean(1) > .80) & (center[:, 2] >= .035)))
    elif source == 'Kirara' and mode == 'back':
        # Kirara supplies real spiral side buns and the long loose waves. Keep
        # whole connected locks: filtering by individual bone weights would
        # open holes at their Head-weighted roots.
        if groups is None:
            raise ValueError('Kirara back hair requires connected triangle groups')
        keep = np.zeros(len(idx), bool)
        for group in groups:
            vertices = np.unique(idx[group]); q = pos[vertices]
            dom = names[joints[vertices][np.arange(len(vertices)), weights[vertices].argmax(1)]]
            rear = np.array([n.startswith(('bone_hair_b_', 'bone_hair_ll_', 'bone_hair_rr_')) for n in dom])
            scalp = (q[:, 2].mean() < -.025 and q[:, 1].min() > .68)
            bun = (np.abs(q[:, 0]).mean() > .13 and q[:, 2].max() < .005)
            keep[group] = rear.any() or scalp or bun
    elif source == 'Kazusa' and mode == 'ears':
        if groups is None:
            raise ValueError('Cat ears require connected triangle groups')
        ear = np.array([n.startswith('bone_ear_') for n in names])
        coverage = (ear[joints]*weights).sum(1)
        keep = np.zeros(len(idx), bool)
        for group in groups:
            vertices = np.unique(idx[group])
            keep[group] = coverage[vertices].max() > .25
    else:
        raise ValueError(f'Unsupported hair selection: {source}/{mode}')
    return idx[keep].copy()


def thicken_twintails(part, source, groups):
    """Widen Serika's real tail cross-sections while preserving roots and UVs.

    The center line is sampled from the combined locks on each side at each
    height. This preserves the donor's curved flow and pointed ends, instead
    of spreading the whole tail away from the head or scaling its length.
    """
    if source != 'Serika (Swimsuit)':
        raise ValueError(f'Unsupported twin-tail fit: {source}')
    pos = np.asarray(part['pos']).copy(); idx = np.asarray(part['idx'])
    names = np.asarray([str(n).lower() for n in part['names']])
    joints, weights = np.asarray(part['j']), np.asarray(part['w'])
    tails = []
    for group in groups:
        vertices = np.unique(idx[group])
        dom = names[joints[vertices][np.arange(len(vertices)), weights[vertices].argmax(1)]]
        if any(n.startswith('bone_twintail_') for n in dom):
            tails.append(vertices)
    for side in (-1, 1):
        chunks = [v for v in tails if np.sign(pos[v, 0].mean()) == side]
        if not chunks:
            continue
        vertices = np.unique(np.concatenate(chunks)); q = pos[vertices].copy()
        low, high = float(q[:, 1].min()), float(q[:, 1].max())
        levels = np.linspace(low, high, 22); centers = []
        for y in levels:
            nearby = q[np.abs(q[:, 1]-y) < .045]
            if not len(nearby): nearby = q[np.argsort(np.abs(q[:, 1]-y))[:8]]
            centers.append((nearby[:, [0, 2]].min(0)+nearby[:, [0, 2]].max(0))*.5)
        centers = np.asarray(centers)
        axis = np.c_[np.interp(q[:, 1], levels, centers[:, 0]), np.interp(q[:, 1], levels, centers[:, 1])]
        strength = np.clip((high-q[:, 1])/.11, 0, 1)
        taper = .35+.65*np.clip((q[:, 1]-low)/.12, 0, 1)
        scale = 1+strength[:, None]*taper[:, None]*[.72, .38]
        pos[vertices[:, None], [0, 2]] = axis+(q[:, [0, 2]]-axis)*scale
    return pos
