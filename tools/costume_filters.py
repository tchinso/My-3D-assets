"""Topology filters for two actual source wardrobes.

All decisions use connected component bounds and original atlas islands. The
functions are pure: they do not mutate arrays, materials, source files or GLBs.
Call costume_keep before selecting or recoloring leg triangles. For Ibuki, this
replaces a global Y cutoff: the entire boot islands are removed, while genuine
bare legs and the bloomer/frill islands remain intact.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def repaint_marks(cid, material_name, image):
    """Replace two donor marks in their exact 512-pixel body-atlas islands.

    This runs after the costume hue pass. Source images remain untouched, as
    do all pixels outside the local skirt logo and school-medal atlas regions.
    Reisa's badge uses a mirrored half-island, whose center seam is U345/512.
    """
    if image.size != (512, 512):
        return image
    if cid == 1 and material_name == 'CH0201_Body':
        a = np.array(image).copy()
        # Reconstruct the navy cloth from the clean pixels on either side of
        # the brackets and their underline, including the printed dark halo.
        x0, x1, y0, y1 = 429, 466, 184, 225
        t = np.linspace(0, 1, x1-x0)[None, :, None]
        left = a[y0:y1, x0-1, :3].astype(float)[:, None, :]
        right = a[y0:y1, x1, :3].astype(float)[:, None, :]
        a[y0:y1, x0:x1, :3] = np.rint(left*(1-t)+right*t).astype('u1')
        return Image.fromarray(a)
    if cid != 5 or material_name != 'CH0167_Body':
        return image
    a = np.array(image).copy()
    # The old white emblem occupies a uniform dark badge island. The nearest
    # clean pixels on the same rows recover its already-tinted fabric color.
    a[90:174, 338:388, :3] = a[90:174, 393:394, :3]
    # These three lime swatches are used exclusively by the medal's top gems
    # and outer frame (11/7/15-vertex source components), not blazer fabric.
    patch = a[84:181, 306:338, :3]
    r, g, b = patch.astype(float).transpose(2, 0, 1)
    lime = (r > 150) & (g > 190) & (b < 160) & (g > b*1.3)
    shade = np.clip(g/235, .72, 1.03)
    patch[lime] = np.clip(np.array([224, 192, 128])*shade[lime, None], 0, 255).astype('u1')
    base = Image.fromarray(a)
    scale = 4
    overlay = Image.new('RGBA', (512*scale, 512*scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    gold = (227, 195, 137, 255)
    ivory = (250, 245, 224, 255)
    rose = (219, 151, 177, 255)
    rose_shade = (154, 90, 121, 255)

    def xy(points):
        return [(int(round(x*scale)), int(round(y*scale))) for x, y in points]

    def line(points, color, width=1.4):
        draw.line(xy(points), fill=color, width=round(width*scale), joint='curve')

    def polygon(points, color):
        draw.polygon(xy(points), fill=color)

    def ellipse(box, fill, outline=None, width=1):
        draw.ellipse(tuple(int(round(v*scale)) for v in box), fill=fill,
                     outline=outline, width=round(width*scale))

    # Only the right half of this design is stored. The source badge mirrors
    # it across U345, producing a centered rose, paired laurels and open book.
    line([(345, 78), (399, 66), (391, 118), (382, 151),
          (365, 177), (345, 190)], gold, 1.8)
    line([(345, 82), (395, 71), (387, 118), (378, 150),
          (362, 173), (345, 185)], ivory, .7)
    polygon([(345, 89), (347, 94), (352, 96), (347, 98),
             (345, 103), (343, 98), (338, 96), (343, 94)], gold)
    # Four visible half-petals become an eight-petal academy rose on the mesh.
    for dx, dy in [(0, -11), (8, -8), (11, 0), (8, 8), (0, 11)]:
        ellipse((345+dx-6, 122+dy-7, 345+dx+6, 122+dy+7), rose, ivory, .8)
    ellipse((340, 117, 350, 127), rose_shade, gold, 1)
    ellipse((343, 120, 347, 124), gold)
    line([(356, 160), (367, 148), (372, 134), (372, 115), (369, 107)], gold, 1.3)
    for points in [
            [(361, 155), (369, 153), (367, 146)],
            [(366, 147), (375, 144), (371, 137)],
            [(370, 137), (379, 132), (372, 127)],
            [(372, 126), (379, 120), (371, 117)],
            [(371, 116), (377, 109), (369, 108)],
            [(364, 151), (357, 148), (359, 156)],
            [(369, 141), (362, 138), (364, 148)],
            [(372, 130), (365, 127), (367, 139)],
            [(372, 119), (365, 115), (367, 127)]]:
        polygon(points, gold)
    polygon([(345, 159), (355, 155), (361, 156), (361, 168),
             (354, 166), (345, 170)], ivory)
    line([(345, 159), (355, 155), (361, 156), (361, 168),
          (354, 166), (345, 170)], gold, 1)
    line([(345, 163), (353, 159), (358, 160)], rose_shade, .65)
    line([(345, 167), (353, 163), (358, 164)], rose_shade, .65)
    # Restrict antialiasing to the half-island. Its unused left side must not
    # bleed the motif into the neighboring color swatches at the center seam.
    overlay = overlay.resize((512, 512), Image.Resampling.LANCZOS)
    mask = Image.new('L', (512, 512), 0)
    ImageDraw.Draw(mask).rectangle((345, 61, 404, 196), fill=255)
    overlay.putalpha(Image.fromarray(np.minimum(np.array(overlay.getchannel('A')),
                                               np.array(mask))))
    return Image.alpha_composite(base, overlay)


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
