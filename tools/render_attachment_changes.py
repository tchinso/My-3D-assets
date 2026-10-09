"""Render Kimon's clothing bow and Momo's tail before/after the attachment edit.

Usage: python tools/render_attachment_changes.py --before tmp/before-assets
The before folder may contain flat GLBs or a characters/ directory tree.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from render_core import GLB, Renderer, mesh_bounds
from render_characters import font


ROOT = Path(__file__).resolve().parents[1]


def asset_path(root,slug):
    flat=root/(slug+'.glb')
    return flat if flat.exists() else root/'characters'/slug/(slug+'.glb')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output=args.output or args.root/'previews'/'attachment_changes.png'
    canvas=Image.new('RGB',(1920,1660),'#f3f5f8');draw=ImageDraw.Draw(canvas)
    draw.text((30,18),'Kimon / clothing bow attached to the blouse',font=font(30,True),fill='#15263a')
    renderer=Renderer(460,650)
    try:
        for row,(slug,angles) in enumerate((('12_kimon_fox_idol',(45,90)),('07_neon_cat',(90,180)))):
            before=GLB(asset_path(args.before,slug));after=GLB(asset_path(args.root,slug))
            meshes=[before.meshes(),after.meshes()]
            if row==0:
                bounds=(np.array([-.12,.49,-.12]),np.array([.12,.69,.20]));half_height=.14
            else:
                bounds=mesh_bounds(meshes[0]+meshes[1]);half_height=None
                draw.text((30,840),'Momo / cat tail removed',font=font(30,True),fill='#15263a')
            for version,glb in enumerate((before,after)):
                for view,angle in enumerate(angles):
                    column=version*2+view;x=20+column*480;y=70+row*820
                    label=f'{"Before" if version==0 else "After"} / {angle} degrees'
                    draw.text((x,y),label,font=font(23,True),fill='#64738a')
                    rendered=renderer.render(glb,meshes[version],angle=angle,bounds=bounds,
                                             camera_half_height=half_height,padding=1.08)
                    canvas.paste(rendered.convert('RGB'),(x,y+40))
    finally:
        renderer.close()
    output.parent.mkdir(parents=True,exist_ok=True);canvas.save(output)
    print(output)


if __name__=='__main__':
    main()
