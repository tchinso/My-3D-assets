"""Render character sheets and animation proofs directly from the delivered GLBs.

Usage: python tools/render_characters.py --root . [--ids 1,2] [--skip-gif]
Use --refresh-motions to preserve sheet turnarounds and redraw animation proofs.
Dependencies: numpy>=2, Pillow>=10, moderngl>=5.12. No source corpus is required.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from render_core import GLB, Renderer, mesh_bounds

INK = "#15263A"
MUTED = "#64738A"
PAPER = "#F3F5F8"
LINE = "#DCE3EB"
RENDER_BG = (0.953, 0.961, 0.973, 1)
FONT_PATHS = [Path("C:/Windows/Fonts/malgun.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
BOLD_PATHS = [Path("C:/Windows/Fonts/malgunbd.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]


def font(size, bold=False):
    paths = BOLD_PATHS if bold else FONT_PATHS
    path = next((path for path in paths if path.exists()), None)
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size=size)


def fit_font(draw, text, size, width, bold=False):
    while size > 16 and draw.textlength(text, font=font(size, bold)) > width:
        size -= 2
    return font(size, bold)


def wrap_text(draw, text, face, width):
    """Width-aware wrapping supports both Korean and whitespace-separated text."""
    lines, line = [], ""
    for paragraph in str(text).splitlines():
        if line:
            lines.append(line)
            line = ""
        words = paragraph.split(" ")
        for word in words:
            candidate = f"{line} {word}" if line else word
            if draw.textlength(candidate, font=face) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ""
            for char in word:
                if line and draw.textlength(line+char, font=face) > width:
                    lines.append(line)
                    line = ""
                line += char
    if line:
        lines.append(line)
    return lines


def palette_colors(entry):
    palette = entry.get("palette", ["#7CBDE2", "#FFFFFF", "#263855"])
    if isinstance(palette, dict):
        palette = list(palette.values())
    output = []
    for value in palette:
        if isinstance(value, dict):
            value = value.get("hex", value.get("color", "#7CBDE2"))
        if isinstance(value, str) and value.startswith("#"):
            output.append(value)
    return output or ["#7CBDE2", "#FFFFFF", "#263855"]


def design_lines(entry):
    design = entry.get("design", "")
    if isinstance(design, dict):
        preferred = ["hair", "outfit", "legwear", "accessories", "weapon", "motif", "details", "personality"]
        lines = []
        for key in preferred:
            value = design.get(key)
            if value:
                value = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                lines.append(value)
        if not lines:
            lines = [str(value) for value in design.values()]
    elif isinstance(design, list):
        lines = list(map(str, design))
    else:
        lines = [str(design)] if design else []
    return lines[:5]


def glb_path(root, entry):
    value = entry.get("glb", entry.get("path"))
    if value:
        return root/value
    return root/"characters"/entry["slug"]/f"{entry['slug']}.glb"


def clip_name(glb, wanted):
    return next((name for name in glb.animations if wanted.lower() in name.lower()), None)


def pose_meshes(glb, wanted, fraction=0.28):
    clip = clip_name(glb, wanted)
    return glb.meshes(clip, glb.duration(clip)*fraction) if clip else glb.meshes()


def heading(draw, text, xy, size=26, fill=INK):
    draw.text(xy, text, font=font(size, True), fill=fill)


def draw_signature_details(canvas, entry):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((64, 1340, 895, 1742), fill=PAPER)
    heading(draw, "SIGNATURE DETAILS", (65, 1343), 24)
    detail_font = font(24)
    accent = palette_colors(entry)[0]
    y = 1395
    for detail in design_lines(entry):
        for index, line in enumerate(wrap_text(draw, detail, detail_font, 790)):
            if y > 1700:
                return
            if index == 0:
                draw.ellipse((67, y+12, 75, y+20), fill=accent)
            draw.text((92, y), line, font=detail_font, fill=INK)
            y += 35
        y += 12


def draw_motion_studies(canvas, glb, pose_renderer):
    """Redraw only the motion panel, preserving the existing static artwork."""
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((950, 1340, 2340, 1742), fill=PAPER)
    heading(draw, "MOTION STUDIES", (960, 1343), 24)
    motion_times = {"Idle": 0.2, "Walk": 0.25, "Attack": 0.57, "Victory": 0.65}
    for index, (motion, fraction) in enumerate(motion_times.items()):
        x = 961+index*343
        draw.rounded_rectangle((x, 1390, x+318, 1727), radius=20, fill="#E8EDF3")
        pose = pose_meshes(glb, motion, fraction)
        image = pose_renderer.render(glb, pose, angle=24, background=RENDER_BG, padding=1.10)
        canvas.paste(image, (x+34, 1400))
        draw.text((x+22, 1693), motion.upper(), font=font(19, True), fill=INK)


def refresh_sheet_motions(entry, glb, pose_renderer):
    output = glb.path.with_name(f"{entry['slug']}_sheet.png")
    with Image.open(output) as image:
        if image.size != (2400, 1800):
            raise ValueError(f"Cannot refresh unexpected sheet dimensions: {output}")
        canvas = image.convert("RGB")
    draw_motion_studies(canvas, glb, pose_renderer)
    canvas.save(output, optimize=True)
    return output


def character_sheet(root, entry, glb, hero_renderer, pose_renderer):
    canvas = Image.new("RGB", (2400, 1800), PAPER)
    draw = ImageDraw.Draw(canvas)
    accent = palette_colors(entry)[0]
    draw.rectangle((0, 0, 2400, 14), fill=accent)
    draw.text((64, 39), f"CHARACTER / {int(entry['id']):02d}", font=font(25, True), fill=MUTED)
    name = entry.get("name", entry["slug"].replace("-", " ").title())
    draw.text((62, 77), name, font=fit_font(draw, name, 76, 1690, True), fill=INK)
    draw.text((65, 173), entry.get("name_ko", ""), font=font(32, True), fill=INK)
    tagline = str(entry.get("tagline", ""))
    draw.text((65, 223), tagline, font=fit_font(draw, tagline, 28, 1720), fill=MUTED)
    draw.rounded_rectangle((1845, 60, 2336, 240), radius=28, fill=INK)
    draw.text((1880, 82), "DESIGN PALETTE", font=font(22, True), fill="#B8C9DA")
    colors = palette_colors(entry)
    for index, color in enumerate(colors[:6]):
        x = 1881+index*69
        draw.rounded_rectangle((x, 130, x+50, 190), radius=10, fill=color, outline="#718399", width=1)
    draw.line((64, 278, 2336, 278), fill=LINE, width=2)

    # A neutral bind pose exposes the complete garment and keeps props off faces.
    meshes = glb.meshes()
    bounds = mesh_bounds(meshes)
    angles = [0, 35, 90, 180]
    labels = ["FRONT", "THREE QUARTER", "PROFILE", "BACK"]
    span = bounds[1]-bounds[0]
    max_width = max(abs(math.cos(math.radians(angle)))*span[0]+abs(math.sin(math.radians(angle)))*span[2] for angle in angles)
    half_height = max(span[1]/2, max_width/2*hero_renderer.height/hero_renderer.width)*1.10
    # Consistent physical scale across the turnarounds, including a carried weapon.
    for index, (angle, label) in enumerate(zip(angles, labels)):
        x = 64+index*575
        draw.rounded_rectangle((x, 304, x+548, 1310), radius=24, fill="#FFFFFF", outline=LINE, width=2)
        image = hero_renderer.render(glb, meshes, angle=angle, bounds=bounds, background=RENDER_BG, camera_half_height=half_height)
        canvas.paste(image, (x+24, 344))
        draw.text((x+28, 322), f"0{index+1} / {label}", font=font(21, True), fill=MUTED)
        draw.line((x+27, 1260, x+521, 1260), fill=LINE, width=1)
        draw.text((x+28, 1274), "ORTHOGRAPHIC VIEW", font=font(16), fill=MUTED)

    draw_signature_details(canvas, entry)
    draw.line((916, 1350, 916, 1734), fill=LINE, width=2)
    draw_motion_studies(canvas, glb, pose_renderer)
    draw.text((65, 1760), "CHARACTER COLLECTION / MODEL-ACCURATE TURNAROUND", font=font(16, True), fill=MUTED)
    output = glb.path.with_name(f"{entry['slug']}_sheet.png")
    canvas.save(output, optimize=True)
    return output


def contact_sheet(entries, glbs, renderer, output, motion=None, fraction=0.3):
    width, height = 2400, 1800
    canvas = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(canvas)
    title = f"{motion.upper()} / MOTION STUDY" if motion else "CHARACTER COLLECTION"
    heading(draw, title, (54, 36), 48)
    subtitle = "Poses evaluated from the exported GLB animation tracks" if motion else "10 designs / 4 animation clips each"
    draw.text((56, 109), subtitle, font=font(25), fill=MUTED)
    for index, (entry, glb) in enumerate(zip(entries, glbs)):
        x, y = 48+(index%5)*468, 173+(index//5)*794
        draw.rounded_rectangle((x, y, x+444, y+770), radius=24, fill="#FFFFFF", outline=LINE, width=2)
        accent = palette_colors(entry)[0]
        draw.rounded_rectangle((x+19, y+18, x+71, y+62), radius=10, fill=INK)
        draw.text((x+28, y+22), f"{int(entry['id']):02d}", font=font(24, True), fill="#FFFFFF")
        mesh = pose_meshes(glb, motion, fraction) if motion else glb.meshes()
        image = renderer.render(glb, mesh, angle=24 if motion else 12, background=RENDER_BG)
        canvas.paste(image, (x+27, y+77))
        name = entry.get("name", entry["slug"])
        draw.text((x+25, y+681), name, font=fit_font(draw, name, 29, 396, True), fill=INK)
        draw.text((x+25, y+725), entry.get("name_ko", ""), font=font(21), fill=MUTED)
        draw.rectangle((x+26, y+757, x+415, y+761), fill=accent)
    canvas.save(output, optimize=True)


def animation_grid(entries, glbs, renderer, output):
    # One compact GIF presents all ten actual skeletons through their three clips.
    frames = []
    motions = ["Walk", "Attack", "Victory"]
    frame_count = 12
    for motion in motions:
        motion_bounds = []
        for glb in glbs:
            clip = clip_name(glb, motion)
            duration = glb.duration(clip)
            samples = [mesh_bounds(glb.meshes(clip, duration*index/(frame_count-1))) for index in range(frame_count)]
            low = samples[0][0].copy()
            high = samples[0][1].copy()
            for sample_low, sample_high in samples[1:]:
                low = np.minimum(low, sample_low)
                high = np.maximum(high, sample_high)
            span = high-low
            motion_bounds.append((low-span*0.03, high+span*0.03))
        for frame in range(frame_count):
            canvas = Image.new("RGB", (1200, 840), PAPER)
            draw = ImageDraw.Draw(canvas)
            heading(draw, f"{motion.upper()} / CHARACTER COLLECTION", (22, 13), 25)
            draw.text((1075, 15), f"{frame+1:02d} / 12", font=font(17), fill=MUTED)
            for index, (entry, glb) in enumerate(zip(entries, glbs)):
                x, y = 12+(index%5)*238, 58+(index//5)*383
                clip = clip_name(glb, motion)
                duration = glb.duration(clip)
                time = duration*frame/(frame_count-1) if motion != "Walk" else duration*frame/frame_count
                mesh = glb.meshes(clip, time) if clip else glb.meshes()
                # A frame-independent camera prevents the model from changing scale.
                bounds = motion_bounds[index]
                image = renderer.render(glb, mesh, angle=18, bounds=bounds, background=RENDER_BG)
                canvas.paste(image, (x, y))
                label = f"{int(entry['id']):02d} {entry.get('name', entry['slug'])}"
                draw.text((x+7, y+336), label, font=fit_font(draw, label, 17, 220, True), fill=INK)
            frames.append(canvas.quantize(colors=128))
    durations = [100]*len(frames)
    for end in [frame_count-1, frame_count*2-1, frame_count*3-1]:
        durations[end] = 500
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, disposal=2, optimize=False)


def load_entries(root):
    manifest = json.loads((root/"characters"/"manifest.json").read_text(encoding="utf-8"))
    return manifest if isinstance(manifest, list) else manifest.get("characters", manifest.get("models", []))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ids", help="Comma-separated IDs or slugs; refresh mode limits sheets only")
    parser.add_argument("--skip-gif", action="store_true")
    sheet_mode = parser.add_mutually_exclusive_group()
    sheet_mode.add_argument("--contacts-only", action="store_true")
    sheet_mode.add_argument("--refresh-motions", action="store_true",
                            help="Keep existing sheet static views and lineup; refresh motion panels and proofs")
    args = parser.parse_args()
    root = args.root.resolve()
    entries = load_entries(root)
    chosen = None
    if args.ids:
        chosen = set(args.ids.split(","))
        if not args.refresh_motions:
            entries = [entry for entry in entries if str(entry["id"]) in chosen or entry["slug"] in chosen]
    sheet_entries = [entry for entry in entries if chosen is None or str(entry["id"]) in chosen or entry["slug"] in chosen]
    if not entries or not sheet_entries:
        raise SystemExit("No matching characters in manifest")
    if args.refresh_motions:
        missing = [glb_path(root, entry).with_name(f"{entry['slug']}_sheet.png")
                   for entry in sheet_entries
                   if not glb_path(root, entry).with_name(f"{entry['slug']}_sheet.png").is_file()]
        if missing:
            raise SystemExit(f"Refresh requires existing character sheets: {missing[0]}")
    glbs = [GLB(glb_path(root, entry)) for entry in entries]
    previews = root/"previews"
    previews.mkdir(exist_ok=True)
    hero = None if args.refresh_motions else Renderer(500, 900)
    pose = Renderer(250, 280, hero.ctx) if hero else Renderer(250, 280)
    contact, gif = Renderer(390, 590, pose.ctx), Renderer(226, 328, pose.ctx)
    renderers = ([hero] if hero else [])+[pose, contact, gif]
    try:
        if not args.contacts_only:
            for entry, glb in zip(entries, glbs):
                if chosen is not None and str(entry["id"]) not in chosen and entry["slug"] not in chosen:
                    continue
                output = (refresh_sheet_motions(entry, glb, pose) if args.refresh_motions
                          else character_sheet(root, entry, glb, hero, pose))
                print(f"Sheet: {output.relative_to(root)}", flush=True)
        if not args.refresh_motions:
            contact_sheet(entries, glbs, contact, previews/"lineup.png")
        for motion, fraction in [("Walk", 0.25), ("Attack", 0.57), ("Victory", 0.65)]:
            contact_sheet(entries, glbs, contact, previews/f"{motion.lower()}_poses.png", motion, fraction)
        if not args.skip_gif:
            animation_grid(entries, glbs, gif, previews/"motion_grid.gif")
        print(f"Previews: {previews}", flush=True)
    finally:
        for renderer in reversed(renderers):
            renderer.close()


if __name__ == "__main__":
    main()
