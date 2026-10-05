"""Refresh the viewer's pinned, offline Three.js runtime (MIT license)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VERSION = "r180"
FILES = {
    "build/three.module.min.js": "three.module.min.js",
    "build/three.core.min.js": "three.core.min.js",
    "examples/jsm/loaders/GLTFLoader.js": "addons/loaders/GLTFLoader.js",
    "examples/jsm/controls/OrbitControls.js": "addons/controls/OrbitControls.js",
    "examples/jsm/utils/BufferGeometryUtils.js": "addons/utils/BufferGeometryUtils.js",
    "LICENSE": "LICENSE",
}


def fetch(item):
    source, target = item
    url = f"https://raw.githubusercontent.com/mrdoob/three.js/{VERSION}/{source}"
    data = urlopen(url, timeout=45).read()
    path = ROOT/"viewer"/"vendor"/target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return target, len(data)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=6) as pool:
        for target, count in pool.map(fetch, FILES.items()):
            print(target, count)
