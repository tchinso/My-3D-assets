"""Copy user map references and produce small local UI thumbnails/portraits.

No image is projected onto the 3D environment. References are retained for
comparison and the destination picker. Existing character GLBs stay unchanged.
"""
import argparse
import json
import shutil
from pathlib import Path
from PIL import Image, ImageOps

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=Path(r'C:\Codex\3D_Map_References'))
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
references = args.root / 'map-viewer' / 'references'
portraits = args.root / 'map-viewer' / 'portraits'
references.mkdir(parents=True, exist_ok=True)
portraits.mkdir(parents=True, exist_ok=True)
images = sorted(p for p in args.source.iterdir() if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'})
if len(images) != 25:
    raise ValueError(f'Expected exactly 25 reference images, found {len(images)}')
for image in images:
    shutil.copy2(image, references / image.name)
    with Image.open(image) as opened:
        ImageOps.contain(opened.convert('RGB'), (480, 320)).save(references / f'{image.stem}_thumb.webp', quality=85)
entries = json.loads((args.root / 'characters' / 'manifest.json').read_text(encoding='utf-8'))
for entry in entries:
    with Image.open(args.root / entry['sheet']) as sheet:
        sheet.crop((90, 430, 580, 1140)).resize((180, 260)).save(portraits / f"{entry['slug']}.webp", quality=90)
print(f'Prepared {len(images)} reference images and {len(entries)} character portraits')
