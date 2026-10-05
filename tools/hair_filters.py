"""Select real frontal fringe and loose back hair for the revised Sora.

Azusa (Swimsuit)'s central fringe and face-framing locks are retained; every
lateral high ponytail and long rear bundle is excluded. Miyo supplies loose
layered back hair and the rear scalp, with its original frontal fringe removed.
The two sources have the same Head rest pivot, so their small scalp overlap
fits before the builder applies its common chin/neck adjustment.
"""
from __future__ import annotations

import numpy as np


def hair_indices(part, source, mode):
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
    elif source == 'Miyo' and mode == 'back':
        front = np.array([n.startswith(('bone_f_hair', 'bone_f_l_hair', 'bone_f_r_hair')) for n in names])
        back = np.array([n.startswith(('bone_b_hair', 'bone_l_b_hair', 'bone_r_b_hair')) for n in names])
        head = np.array([n == 'bip001 head' for n in names])
        frontal = (front[joints]*weights).sum(1)
        rear = (back[joints]*weights).sum(1)
        skull = (head[joints]*weights).sum(1)
        keep = ((frontal[idx].max(1) < .08)
                & ((rear[idx].mean(1) > .10)
                   | ((skull[idx].mean(1) > .80) & (center[:, 2] < .035))))
    else:
        raise ValueError(f'Unsupported hair selection: {source}/{mode}')
    return idx[keep].copy()
