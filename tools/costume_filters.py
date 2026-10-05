"""Topology filters for two actual source wardrobes.

All decisions use connected component bounds and original atlas islands. The
functions are pure: they do not mutate arrays, materials, source files or GLBs.
Call costume_keep before selecting or recoloring leg triangles. For Ibuki, this
replaces a global Y cutoff: the entire boot islands are removed, while genuine
bare legs and the bloomer/frill islands remain intact.
"""
from __future__ import annotations

import numpy as np


def _inside(lo, hi, rect, epsilon=.002):
    u0, u1, v0, v1 = rect
    return (lo[0] >= u0-epsilon and hi[0] <= u1+epsilon
            and lo[1] >= v0-epsilon and hi[1] <= v1+epsilon)


def costume_keep(cid, pos, idx, uv, groups, keep):
    """Return a filtered copy of keep, using the supplied full source groups.

    cid6 groups are the original non-welded index components. cid9 groups must
    weld position seams, as its large coat and separate buttons span UV seams.
    The existing wing, headgear and bag filters can run before this function.
    """
    result = np.asarray(keep, dtype=bool).copy()
    if cid not in (6, 9):
        return result
    pos, idx, uv = np.asarray(pos), np.asarray(idx), np.asarray(uv)
    for triangles in groups:
        triangles = np.asarray(triangles, dtype=int)
        vertices = np.unique(idx[triangles])
        if not len(vertices):
            continue
        points, coords = pos[vertices], uv[vertices]
        lo, hi = points.min(0), points.max(0)
        ulo, uhi = coords.min(0), coords.max(0)
        n, count = len(vertices), len(triangles)
        remove = False
        if cid == 6:
            # The narrow anatomical neck shares the coat-seam atlas slot.
            # Restore this exact small island if the earlier generic seam
            # filter rejected it; full coat seam strips are much larger.
            neck = (n == 7 and count == 6 and abs(points[:, 0]).max() < .029
                    and .565 < lo[1] < .580 and .615 < hi[1] < .625
                    and _inside(ulo, uhi, (.393, .399, .918, .929)))
            if neck:
                result[triangles] = True
                continue
            # Original full outer coat, its white seam tape, red lining and
            # green side panels. Their split trims were left by the first pass.
            outer = (uhi[0] < .36 and ulo[1] > .58)
            seam = _inside(ulo, uhi, (.365, .405, .918, .930))
            lining = _inside(ulo, uhi, (.680, .765, .950, .986))
            panels = _inside(ulo, uhi, (.365, .485, .700, .817)) and hi[1] < .32
            # Collar and two long hanging trim bands, independent of the
            # retained blouse. None of these islands is anatomical neck skin.
            collar = _inside(ulo, uhi, (.648, .822, .035, .160)) and n >= 70
            bands = _inside(ulo, uhi, (.646, .702, .170, .294)) and lo[1] < .10
            band_roots = _inside(ulo, uhi, (.560, .644, .205, .465)) and n == 26
            edge_piping = _inside(ulo, uhi, (.648, .774, .950, .969))
            # All boot and sole pieces share this right-edge atlas region.
            # Remove whole islands rather than slicing boot geometry by Y.
            boots = ulo[0] > .975 and ulo[1] > .720 and hi[1] < .13
            # Detached waist loops and fasteners attached to the removed coat.
            waist_loops = _inside(ulo, uhi, (.977, .990, .265, .442)) and n <= 16
            panel_buttons = _inside(ulo, uhi, (.877, .892, .272, .451)) and hi[1] < .25
            golden_tassels = (n <= 20 and abs(points[:, 0].mean()) > .085
                             and .10 < points[:, 1].mean() < .46
                             and points[:, 2].mean() > .06
                             and _inside(ulo, uhi, (.390, .404, .967, .983)))
            remove = any((outer, seam, lining, panels, collar, bands,
                          band_roots, edge_piping, boots, waist_loops,
                          panel_buttons, golden_tassels))
        else:
            # Genuine qipao/chest knots remain. These two button islands,
            # epaulette and its fastener were positioned on the removed coat.
            positive_side = lo[0] > .075 and hi[0] < .18
            button = (n == 41 and count == 58 and positive_side
                      and _inside(ulo, uhi, (.265, .451, .225, .490)))
            epaulette = (n == 56 and count == 40 and positive_side
                         and _inside(ulo, uhi, (.305, .458, .000, .230)))
            epaulette_fastener = (n == 88 and count == 180 and positive_side
                                 and _inside(ulo, uhi, (.008, .026, .511, .528)))
            remove = button or epaulette or epaulette_fastener
        if remove:
            result[triangles] = False
    return result


def leg_triangles(cid, pos, idx, uv, groups, bone_names):
    """Select anatomical leg triangles; preserve Ibuki bloomers and frills.

    For cid6, call with the same unfiltered source idx/groups as costume_keep,
    then intersect the result with the final keep mask. Its two genuine bare
    leg islands are UV U.013-.051,V.556-.559 (51 vertices/87 triangles each).
    No height slicing is performed, so legs overlap transplanted ankle/feet.
    Other designs retain the builder's dominant bone and centroid selection.
    """
    pos, idx, uv = np.asarray(pos), np.asarray(idx), np.asarray(uv)
    if cid == 6:
        result = np.zeros(len(idx), dtype=bool)
        for triangles in groups:
            triangles = np.asarray(triangles, dtype=int)
            vertices = np.unique(idx[triangles])
            coords = uv[vertices]
            if (len(vertices) == 51 and len(triangles) == 87
                    and _inside(coords.min(0), coords.max(0), (.010, .054, .551, .564))):
                result[triangles] = True
        return result
    leg_vertex = np.array([any(s in str(name) for s in (' thigh', ' calf', ' foot'))
                           for name in bone_names], dtype=bool)
    centers = pos[idx].mean(1)
    return (leg_vertex[idx].any(1) & (centers[:, 1] < .43)
            & (np.abs(centers[:, 0]) < .2) & (centers[:, 1] > .072))
