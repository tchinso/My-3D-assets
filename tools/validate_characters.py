"""Check delivered GLBs and PNG sheets without rendering or changing the assets.

Usage: python tools/validate_characters.py --root .
The only written file is previews/validation.json. --report - writes to stdout;
--skip-sheets is intended for a structural check before the sheets are produced.
This complements, rather than replaces, the Khronos glTF validator and visual QA.
Dependencies: NumPy and Pillow.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
import math
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


DTYPES = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
SHAPES = {"SCALAR": (1, 1), "VEC2": (1, 2), "VEC3": (1, 3), "VEC4": (1, 4),
          "MAT2": (2, 2), "MAT3": (3, 3), "MAT4": (4, 4)}
REQUIRED_CLIPS = ("Idle", "Walk", "Run", "Attack", "Defend", "Victory", "Lose")
LOOP_CLIPS = {"Idle", "Walk", "Run"}
POSE_FRACTIONS = (0., .125, .25, .375, .5, .625, .75, .875, 1.)
SHEET_SIZE = (2400, 1800)


def declared_design_ids(path):
    """Read literal design IDs and local DESIGNS extensions without executing code."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    identifiers, imported = set(), {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "DESIGNS":
                    imported[alias.asname or alias.name] = path.parent/(node.module.replace(".", "/")+".py")
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "DESIGNS" for target in node.targets):
            for design in node.value.elts:
                value = next(keyword.value for keyword in design.keywords if keyword.arg == "id")
                identifiers.add(int(ast.literal_eval(value)))
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "extend"
                and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "DESIGNS"):
            extension = node.value.args[0]
            if not isinstance(extension, ast.Name) or extension.id not in imported:
                raise ValueError("DESIGNS extension must refer to a local declarative design module")
            identifiers.update(declared_design_ids(imported[extension.id]))
    if not identifiers:
        raise ValueError(f"No declared design IDs in {path}")
    return identifiers


def qmatrix(q):
    x, y, z, w = np.asarray(q, dtype=float)
    return np.array([[1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w],
                     [2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w],
                     [2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y]])


def local_matrix(node):
    if "matrix" in node:
        return np.asarray(node["matrix"], dtype=float).reshape(4, 4).T
    result = np.eye(4)
    result[:3, :3] = qmatrix(node.get("rotation", [0, 0, 0, 1])) @ np.diag(node.get("scale", [1, 1, 1]))
    result[:3, 3] = node.get("translation", [0, 0, 0])
    return result


def slerp(a, b, fraction):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    a = a / max(float(np.linalg.norm(a)), 1e-15)
    b = b / max(float(np.linalg.norm(b)), 1e-15)
    dot = float(a @ b)
    if dot < 0:
        b, dot = -b, -dot
    if dot > .9995:
        value = a + fraction * (b-a)
        return value / max(float(np.linalg.norm(value)), 1e-15)
    angle = math.acos(float(np.clip(dot, -1, 1)))
    return (math.sin((1-fraction)*angle)*a + math.sin(fraction*angle)*b) / math.sin(angle)


class Asset:
    """Strict embedded GLB reader; accessor data are checked before construction."""

    def __init__(self, path):
        self.path = Path(path)
        data = self.path.read_bytes()
        if len(data) < 12:
            raise ValueError("GLB header is truncated")
        magic, version, declared = struct.unpack_from("<4sII", data)
        if magic != b"glTF" or version != 2 or declared != len(data):
            raise ValueError(f"GLB header mismatch: magic={magic!r}, version={version}, declared={declared}, actual={len(data)}")
        chunks, offset = [], 12
        while offset < len(data):
            if offset + 8 > len(data):
                raise ValueError("GLB chunk header is truncated")
            length, kind = struct.unpack_from("<II", data, offset)
            if length % 4 or offset + 8 + length > len(data):
                raise ValueError("GLB chunk alignment or length is invalid")
            chunks.append((kind, data[offset+8:offset+8+length]))
            offset += 8 + length
        if not chunks or chunks[0][0] != 0x4E4F534A:
            raise ValueError("First GLB chunk must be JSON")
        if sum(kind == 0x4E4F534A for kind, _ in chunks) != 1:
            raise ValueError("GLB must have exactly one JSON chunk")
        bins = [chunk for kind, chunk in chunks if kind == 0x004E4942]
        if len(bins) != 1:
            raise ValueError("Character GLB must have one embedded BIN chunk")
        self.doc = json.loads(chunks[0][1].decode("utf-8"))
        self.binary, self.cache = bins[0], {}
        buffers = self.doc.get("buffers", [])
        if len(buffers) != 1 or "uri" in buffers[0]:
            raise ValueError("Character GLB must use one embedded buffer without a URI")
        length = int(buffers[0].get("byteLength", -1))
        if length < 0 or len(self.binary) - length not in (0, 1, 2, 3):
            raise ValueError("Embedded buffer length differs from BIN chunk beyond allowed padding")
        self.byte_length = length
        for index, view in enumerate(self.doc.get("bufferViews", [])):
            start, size = int(view.get("byteOffset", 0)), int(view.get("byteLength", -1))
            if view.get("buffer", 0) != 0 or start < 0 or size < 0 or start+size > length:
                raise ValueError(f"bufferView {index} is outside the embedded buffer")

    def view_bytes(self, index):
        view = self.doc["bufferViews"][index]
        start = view.get("byteOffset", 0)
        return self.binary[start:start+view["byteLength"]]

    def _layout(self, accessor):
        dtype = np.dtype(DTYPES[accessor["componentType"]])
        columns, rows = SHAPES[accessor["type"]]
        column_size = rows*dtype.itemsize
        column_stride = ((column_size+3)//4)*4 if columns > 1 else column_size
        offsets = [column*column_stride+row*dtype.itemsize for column in range(columns) for row in range(rows)]
        return dtype, offsets, columns*column_stride

    def _read(self, accessor, view_index, offset, count, tightly_packed=False):
        dtype, offsets, packed = self._layout(accessor)
        view = self.doc["bufferViews"][view_index]
        stride = packed if tightly_packed else int(view.get("byteStride", packed))
        offset = int(offset)
        if count < 0 or offset < 0 or stride < packed or stride % dtype.itemsize:
            raise ValueError("Accessor count, byteOffset, or byteStride is invalid")
        required = offset + (count-1)*stride + packed if count else offset
        if required > view["byteLength"]:
            raise ValueError("Accessor exceeds its bufferView")
        absolute = int(view.get("byteOffset", 0))+offset
        if absolute % dtype.itemsize:
            raise ValueError("Accessor component alignment is invalid")
        result = np.empty((count, len(offsets)), dtype=dtype)
        for column, component_offset in enumerate(offsets):
            result[:, column] = np.ndarray((count,), dtype=dtype, buffer=self.binary,
                                           offset=absolute+component_offset, strides=(stride,))
        return result

    def accessor(self, index):
        if index in self.cache:
            return self.cache[index]
        accessor = self.doc["accessors"][index]
        dtype, offsets, _ = self._layout(accessor)
        count = int(accessor["count"])
        if "bufferView" in accessor:
            array = self._read(accessor, accessor["bufferView"], accessor.get("byteOffset", 0), count)
        else:
            array = np.zeros((count, len(offsets)), dtype=dtype)
        if "sparse" in accessor:
            sparse = accessor["sparse"]
            sparse_count = int(sparse["count"])
            if not 0 <= sparse_count <= count:
                raise ValueError("Sparse count is outside accessor count")
            indices, values = sparse["indices"], sparse["values"]
            if indices["componentType"] not in (5121, 5123, 5125):
                raise ValueError("Sparse indices must be unsigned integers")
            descriptor = {"componentType": indices["componentType"], "type": "SCALAR"}
            ids = self._read(descriptor, indices["bufferView"], indices.get("byteOffset", 0), sparse_count, True).ravel()
            if len(ids) and (ids[-1] >= count or np.any(np.diff(ids.astype(np.int64)) <= 0)):
                raise ValueError("Sparse indices are unsorted, repeated, or outside accessor")
            array[ids] = self._read(accessor, values["bufferView"], values.get("byteOffset", 0), sparse_count, True)
        if accessor.get("normalized"):
            if dtype.kind not in "iu":
                raise ValueError("Only integer accessors can be normalized")
            array = array.astype(float)/np.iinfo(dtype).max
            if dtype.kind == "i":
                array = np.maximum(array, -1)
        self.cache[index] = array
        return array

    def world(self, overrides=None):
        nodes = self.doc.get("nodes", [])
        parents, result, pending = {}, {}, set()
        for index, node in enumerate(nodes):
            for child in node.get("children", []):
                if not isinstance(child, int) or not 0 <= child < len(nodes):
                    raise ValueError(f"Node {index} has invalid child {child}")
                if child in parents:
                    raise ValueError(f"Node {child} has multiple parents")
                parents[child] = index

        def visit(index):
            if index in result:
                return result[index]
            if index in pending:
                raise ValueError("Node hierarchy contains a cycle")
            pending.add(index)
            node = dict(nodes[index])
            if overrides and index in overrides:
                node.update(overrides[index])
            local = local_matrix(node)
            result[index] = visit(parents[index]) @ local if index in parents else local
            pending.remove(index)
            return result[index]

        for index in range(len(nodes)):
            visit(index)
        return result

    def animated_world(self, animation, time):
        overrides = {}
        for channel in animation.get("channels", []):
            target = channel["target"]
            if target["path"] not in ("rotation", "translation", "scale"):
                continue
            sampler = animation["samplers"][channel["sampler"]]
            times = self.accessor(sampler["input"]).ravel()
            values = self.accessor(sampler["output"])
            interpolation = sampler.get("interpolation", "LINEAR")
            cubic = interpolation == "CUBICSPLINE"
            keys = values[1::3] if cubic else values
            if time <= times[0]:
                value = keys[0]
            elif time >= times[-1]:
                value = keys[-1]
            else:
                upper = int(np.searchsorted(times, time, side="right"))
                lower, span = upper-1, float(times[upper]-times[upper-1])
                fraction = float((time-times[lower])/span)
                if interpolation == "STEP":
                    value = keys[lower]
                elif cubic:
                    t = fraction
                    value = ((2*t**3-3*t*t+1)*keys[lower] + (t**3-2*t*t+t)*span*values[3*lower+2]
                             + (-2*t**3+3*t*t)*keys[upper] + (t**3-t*t)*span*values[3*upper])
                    if target["path"] == "rotation":
                        value = value / max(float(np.linalg.norm(value)), 1e-15)
                elif target["path"] == "rotation":
                    value = slerp(keys[lower], keys[upper], fraction)
                else:
                    value = keys[lower]+fraction*(keys[upper]-keys[lower])
            overrides.setdefault(target["node"], {})[target["path"]] = value
        return self.world(overrides)


def sample_geometry(asset, max_vertices=64):
    """Representative referenced vertices, including every visible mesh primitive."""
    samples = []
    nodes = asset.doc.get("nodes", [])
    active = set()

    def visit(index):
        if index in active:
            return
        active.add(index)
        for child in nodes[index].get("children", []):
            visit(child)

    scene = asset.doc["scenes"][asset.doc.get("scene", 0)]
    for root in scene.get("nodes", []):
        visit(root)
    for index in sorted(active):
        node = nodes[index]
        if "mesh" not in node:
            continue
        for primitive in asset.doc["meshes"][node["mesh"]].get("primitives", []):
            attrs = primitive["attributes"]
            positions = asset.accessor(attrs["POSITION"])
            ids = np.unique(asset.accessor(primitive["indices"]).ravel()) if "indices" in primitive else np.arange(len(positions))
            if not len(ids):
                continue
            if max_vertices is not None:
                ids = ids[np.linspace(0, len(ids)-1, min(max_vertices, len(ids)), dtype=int)].astype(int)
            position = positions[ids].astype(float)
            if "skin" in node and "JOINTS_0" in attrs:
                skin = asset.doc["skins"][node["skin"]]
                inverse = asset.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
                samples.append((index, position, asset.accessor(attrs["JOINTS_0"])[ids].astype(int),
                                asset.accessor(attrs["WEIGHTS_0"])[ids], skin["joints"], inverse))
            else:
                samples.append((index, position, None, None, None, None))
    return samples


def pose_samples(samples, world):
    points, skin_matrices = [], {}
    for node, position, joints, weights, skin_joints, inverse in samples:
        homogeneous = np.c_[position, np.ones(len(position))]
        if joints is None:
            points.append((homogeneous @ world[node].T)[:, :3])
        else:
            key = (tuple(skin_joints), inverse.ctypes.data)
            if key not in skin_matrices:
                skin_matrices[key] = np.array([world[joint] @ inverse[slot] for slot, joint in enumerate(skin_joints)])
            matrices = skin_matrices[key]
            blended = (matrices[joints]*weights[:, :, None, None]).sum(axis=1)
            points.append(np.einsum("nij,nj->ni", blended, homogeneous)[:, :3])
    return np.concatenate(points) if points else np.empty((0, 3))


def main_skin_joints(asset):
    nodes = asset.doc.get("nodes", [])
    scores = {}
    for node in nodes:
        if "skin" in node and "mesh" in node:
            scores[node["skin"]] = scores.get(node["skin"], 0)+sum(
                asset.doc["accessors"][primitive["attributes"]["POSITION"]]["count"]
                for primitive in asset.doc["meshes"][node["mesh"]].get("primitives", []))
    if not scores:
        return []
    return asset.doc["skins"][max(scores, key=scores.get)]["joints"]


def anatomical_bones(asset):
    """Named body bones, including unweighted hands below the main skin root."""
    nodes = asset.doc.get("nodes", [])
    joints = main_skin_joints(asset)
    bones = {}
    for index in joints:
        bones.setdefault(nodes[index].get("name", ""), index)
    parents = {child: index for index, node in enumerate(nodes) for child in node.get("children", [])}
    root = None
    for joint in joints:
        ancestor = joint
        while ancestor is not None:
            if nodes[ancestor].get("name") == "Bip001":
                root = ancestor
                break
            ancestor = parents.get(ancestor)
        if root is not None:
            break
    if root is None:
        return bones
    pending = [root]
    while pending:
        index = pending.pop()
        name = nodes[index].get("name", "")
        if name.startswith("Bip001_Weapon"):
            continue
        if name == "Bip001" or name.startswith("Bip001 "):
            bones.setdefault(name, index)
        pending.extend(nodes[index].get("children", []))
    return bones


def run_arm_metrics(asset, rest_world, posed_worlds):
    """Measure exported arm posture, independent of Euler angles or IK recipes.

    Outward elbow reach is relative to upper-arm length; flexion is zero for a
    straight arm. Rest anatomy supplies the character's lateral and up axes.
    """
    bones = anatomical_bones(asset)

    def position(world, name):
        if name not in bones:
            raise ValueError(f"Run arm check requires {name}")
        return world[bones[name]][:3, 3]

    lateral = position(rest_world, "Bip001 L Thigh")-position(rest_world, "Bip001 R Thigh")
    lateral /= max(float(np.linalg.norm(lateral)), 1e-15)
    up = position(rest_world, "Bip001 Head")-position(rest_world, "Bip001 Pelvis")
    up /= max(float(np.linalg.norm(up)), 1e-15)
    result = {}
    for side, sign in (("L", 1), ("R", -1)):
        outward, flexion, drop = [], [], []
        for world in posed_worlds:
            shoulder = position(world, f"Bip001 {side} UpperArm")
            elbow = position(world, f"Bip001 {side} Forearm")
            wrist = position(world, f"Bip001 {side} Hand")
            upper, fore = elbow-shoulder, wrist-elbow
            length = float(np.linalg.norm(upper))
            if min(length, float(np.linalg.norm(fore))) < 1e-8:
                raise ValueError(f"Run {side} arm has a degenerate bone segment")
            outward.append(float(np.dot(upper, lateral*sign)/length))
            drop.append(float(-np.dot(upper, up)/length))
            flexion.append(math.degrees(math.atan2(float(np.linalg.norm(np.cross(upper, fore))),
                                                  float(np.dot(upper, fore)))))
        result[side] = {"sample_count": len(posed_worlds),
                        "max_outward_upperarm_ratio": max(outward),
                        "mean_outward_upperarm_ratio": float(np.mean(outward)),
                        "min_elbow_flex_degrees": min(flexion),
                        "max_elbow_flex_degrees": max(flexion),
                        "min_elbow_drop_upperarm_ratio": min(drop)}
    return result


def attack_fingerprint(asset, rest_world, posed_worlds):
    """Compare anatomical rotation curves independently of meshes or body size.

    This detects identical gestures after time normalization. It is deliberately
    an exact duplicate check; visual review assesses the degree of individuality.
    """
    nodes = asset.doc.get("nodes", [])
    joints = main_skin_joints(asset)
    wanted = {"Bip001 Pelvis", "Bip001 Spine", "Bip001 Spine1", "Bip001 Head",
              "Bip001 L UpperArm", "Bip001 R UpperArm", "Bip001 L Forearm",
              "Bip001 R Forearm", "Bip001 L Thigh", "Bip001 R Thigh"}
    named = sorted((nodes[index].get("name", ""), index) for index in joints
                   if nodes[index].get("name", "") in wanted)
    if len(named) < 4:
        return None
    signature = []
    for _, index in named:
        rest = rest_world[index][:3, :3]
        rest = rest/np.maximum(np.linalg.norm(rest, axis=0), 1e-15)
        for world in posed_worlds:
            rotation = world[index][:3, :3]
            rotation = rotation/np.maximum(np.linalg.norm(rotation, axis=0), 1e-15)
            signature.extend((rotation @ rest.T).ravel())
    # Rounded integers avoid float byte differences and signed-zero noise.
    payload = np.rint(np.asarray(signature)*10000).astype("<i4").tobytes()
    prefix = "|".join(name for name, _ in named).encode("utf-8")
    return hashlib.sha256(prefix+payload).hexdigest()


def run_leg_metrics(asset, rest_world, posed_worlds):
    """Measure stride around the pelvis, independent of root travel and size."""
    bones = anatomical_bones(asset)
    pelvis = bones['Bip001 Pelvis']
    result = {}
    for side in ('L', 'R'):
        thigh, calf, foot = (bones[f'Bip001 {side} {part}'] for part in ('Thigh', 'Calf', 'Foot'))
        length = (np.linalg.norm(rest_world[calf][:3,3]-rest_world[thigh][:3,3])
                  + np.linalg.norm(rest_world[foot][:3,3]-rest_world[calf][:3,3]))
        points = np.array([world[foot][:3,3]-world[pelvis][:3,3] for world in posed_worlds])
        result[side] = {'fore_aft_stride_leg_lengths': float(np.ptp(points[:,2])/length),
                        'vertical_stride_leg_lengths': float(np.ptp(points[:,1])/length)}
    return result


def check_asset(path, sheet_path=None, skip_sheets=False):
    report = {"glb": str(path), "sheet": str(sheet_path) if sheet_path else None,
              "errors": [], "warnings": [], "metrics": {}, "animations": {}}
    errors, warnings, metrics = report["errors"], report["warnings"], report["metrics"]

    def require(condition, message):
        if not condition:
            errors.append(message)

    try:
        asset = Asset(path)
    except Exception as exc:
        errors.append(f"GLB parse: {exc}")
        asset = None
    if asset:
        doc = asset.doc
        metrics.update(bytes=Path(path).stat().st_size, nodes=len(doc.get("nodes", [])),
                       meshes=len(doc.get("meshes", [])), skins=len(doc.get("skins", [])),
                       embedded_images=len(doc.get("images", [])), accessors=len(doc.get("accessors", [])))
        require(doc.get("asset", {}).get("version") == "2.0", "asset.version must be 2.0")
        for index, accessor in enumerate(doc.get("accessors", [])):
            try:
                value = asset.accessor(index)
                require(np.isfinite(value).all(), f"Accessor {index} contains nonfinite values")
                if not accessor.get("normalized") and len(value):
                    for key, actual in (("min", value.min(axis=0)), ("max", value.max(axis=0))):
                        if key in accessor:
                            require(np.allclose(accessor[key], actual, rtol=2e-5, atol=1e-6), f"Accessor {index} {key} differs from its data")
            except Exception as exc:
                errors.append(f"Accessor {index}: {exc}")
        for index, node in enumerate(doc.get("nodes", [])):
            for key, size in (("translation", 3), ("rotation", 4), ("scale", 3), ("matrix", 16)):
                if key in node:
                    require(len(node[key]) == size and np.isfinite(node[key]).all(), f"Node {index} {key} has invalid values")
            if "rotation" in node:
                require(abs(float(np.linalg.norm(node["rotation"]))-1) < 2e-4, f"Node {index} quaternion is not normalized")
            if "matrix" in node:
                require(not any(key in node for key in ("rotation", "translation", "scale")), f"Node {index} mixes matrix and TRS")
        try:
            world = asset.world()
            require(all(np.isfinite(matrix).all() for matrix in world.values()), "World transforms contain nonfinite values")
        except Exception as exc:
            errors.append(f"Node hierarchy: {exc}")
            world = {}
        for index, skin in enumerate(doc.get("skins", [])):
            try:
                joints = skin["joints"]
                require(bool(joints) and len(set(joints)) == len(joints), f"Skin {index} has empty or repeated joints")
                require(all(isinstance(joint, int) and 0 <= joint < len(doc["nodes"]) for joint in joints), f"Skin {index} has out-of-range joints")
                require("inverseBindMatrices" in skin, f"Skin {index} lacks inverse bind matrices")
                descriptor = doc["accessors"][skin["inverseBindMatrices"]]
                require(descriptor["type"] == "MAT4" and descriptor["componentType"] == 5126, f"Skin {index} inverse matrices must be float MAT4")
                inverse = asset.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
                require(len(inverse) == len(joints), f"Skin {index} inverse matrix count differs from joint count")
                require(np.isfinite(inverse).all() and np.all(np.abs(np.linalg.det(inverse)) > 1e-10), f"Skin {index} has nonfinite or singular inverse matrices")
                if world and len(inverse) == len(joints):
                    residual = max(float(np.max(np.abs(world[joint] @ inverse[slot]-np.eye(4)))) for slot, joint in enumerate(joints))
                    metrics.setdefault("skin_bind_residuals", []).append(residual)
                    if residual > 2e-4:
                        warnings.append(f"Skin {index} rest world/inverse bind residual is {residual:.6g}; verify authored bind pose")
            except Exception as exc:
                errors.append(f"Skin {index}: {exc}")
        triangles, vertices, max_weight_error, zero_normals = 0, 0, 0., 0
        for node_index, node in enumerate(doc.get("nodes", [])):
            if "mesh" not in node:
                continue
            try:
                mesh = doc["meshes"][node["mesh"]]
                for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
                    label = f"Mesh {node['mesh']} primitive {primitive_index}"
                    attrs = primitive["attributes"]
                    position = asset.accessor(attrs["POSITION"])
                    count = len(position)
                    vertices += count
                    require(position.shape[1] == 3 and count > 0, f"{label} lacks nonempty VEC3 positions")
                    for semantic, accessor_index in attrs.items():
                        require(len(asset.accessor(accessor_index)) == count, f"{label} {semantic} count differs from positions")
                    indices = asset.accessor(primitive["indices"]).ravel() if "indices" in primitive else np.arange(count)
                    if "indices" in primitive:
                        descriptor = doc["accessors"][primitive["indices"]]
                        require(descriptor["componentType"] in (5121, 5123, 5125) and descriptor["type"] == "SCALAR", f"{label} indices are not unsigned SCALAR")
                    require(bool(len(indices)) and np.all((indices >= 0) & (indices < count)), f"{label} has empty or out-of-range indices")
                    if primitive.get("mode", 4) == 4:
                        require(len(indices) % 3 == 0, f"{label} triangle index count is not divisible by three")
                        triangles += len(indices)//3
                    if "NORMAL" in attrs:
                        normals = asset.accessor(attrs["NORMAL"])
                        lengths = np.linalg.norm(normals[indices.astype(int)], axis=1)
                        zero_normals += int(np.sum(lengths < 1e-8))
                        if np.any(np.abs(lengths-1) > .02):
                            warnings.append(f"{label} has nonunit normals (maximum error {float(np.max(np.abs(lengths-1))):.4g})")
                    else:
                        warnings.append(f"{label} has no normals")
                    if "skin" in node:
                        require("JOINTS_0" in attrs and "WEIGHTS_0" in attrs, f"{label} skinned node lacks joints or weights")
                        joints = asset.accessor(attrs["JOINTS_0"])
                        weights = asset.accessor(attrs["WEIGHTS_0"])
                        require(joints.shape == weights.shape and joints.shape[1] == 4, f"{label} joint/weight shape mismatch")
                        require(np.all((joints >= 0) & (joints < len(doc["skins"][node["skin"]]["joints"]))), f"{label} joint slots exceed skin joint count")
                        require(np.all(weights >= -1e-6), f"{label} has negative skin weights")
                        combined = weights.sum(axis=1)
                        if "WEIGHTS_1" in attrs:
                            extra_weights, extra_joints = asset.accessor(attrs["WEIGHTS_1"]), asset.accessor(attrs["JOINTS_1"])
                            combined += extra_weights.sum(axis=1)
                            require(np.all((extra_joints >= 0) & (extra_joints < len(doc["skins"][node["skin"]]["joints"]))), f"{label} extra joint slots exceed skin")
                        error = float(np.max(np.abs(combined-1))) if count else 1.
                        max_weight_error = max(max_weight_error, error)
                        require(error < 5e-4, f"{label} skin weights do not sum to one (max error {error:.6g})")
                    if "material" in primitive:
                        require(0 <= primitive["material"] < len(doc.get("materials", [])), f"{label} material is out of range")
            except Exception as exc:
                errors.append(f"Mesh node {node_index}: {exc}")
        metrics.update(vertex_records=vertices, triangles=triangles, max_skin_weight_error=max_weight_error, zero_normal_records=zero_normals)
        require(triangles > 0, "No triangle geometry exists")
        require(zero_normals == 0, "Referenced normals include zero vectors")
        for index, texture in enumerate(doc.get("textures", [])):
            require(0 <= texture.get("source", -1) < len(doc.get("images", [])), f"Texture {index} source is out of range")
        for index, image in enumerate(doc.get("images", [])):
            try:
                if "uri" in image:
                    uri = image["uri"]
                    if not uri.startswith("data:"):
                        raise ValueError("external image URI is not self-contained")
                    data = base64.b64decode(uri.split(",", 1)[1])
                else:
                    data = asset.view_bytes(image["bufferView"])
                with Image.open(io.BytesIO(data)) as bitmap:
                    size, fmt = bitmap.size, bitmap.format
                    bitmap.verify()
                require(fmt == "PNG", f"Embedded image {index} is {fmt}, expected PNG")
                require(min(size) > 0, f"Embedded image {index} has invalid dimensions")
                metrics.setdefault("texture_dimensions", []).append(list(size))
            except Exception as exc:
                errors.append(f"Image {index}: {exc}")
        animations = doc.get("animations", [])
        geometry_samples = None
        if world and not errors:
            try:
                geometry_samples = sample_geometry(asset)
                ground_reference = float(pose_samples(sample_geometry(asset,None),world)[:,1].min())
                metrics['rest_geometry_floor_y'] = ground_reference
            except Exception as exc:
                errors.append(f"Geometry sampling: {exc}")
        names = [animation.get("name", "") for animation in animations]
        require(len(names) == len(set(names)), "Animation names are repeated")
        for name in REQUIRED_CLIPS:
            require(name in names, f"Required animation {name} is missing")
        sampled_poses = {}
        for animation in animations:
            name = animation.get("name", "<unnamed>")
            clip = {"channels": len(animation.get("channels", [])), "duration_seconds": 0.,
                    "moving_channels": 0, "loop_endpoints_exact": name in LOOP_CLIPS}
            if animation.get("extras", {}).get("description"):
                clip["description"] = animation["extras"]["description"]
            provenance = doc.get('extras', {}).get('motion_sources', {}).get(name)
            if provenance:
                clip['source_file'] = provenance['source_file']
                clip['source_clip'] = provenance['source_clip']
                require(provenance['source_file'] in doc.get('extras', {}).get('source_parts', []),
                        f"Animation {name} donor is missing from source_parts")
                require(doc.get('extras', {}).get('native_clips', {}).get(name) == provenance['source_clip'],
                        f"Animation {name} original clip differs from its provenance")
                if name in ('Run', 'Attack', 'Defend', 'Lose'):
                    extras = animation.get('extras', {})
                    require(extras.get('procedural') is False,
                            f"Animation {name} must use a native donor performance")
                    require(extras.get('nativeSourceClip') == provenance['source_clip'] and
                            extras.get('source_clip') == provenance['source_clip'] and
                            extras.get('source_file') == provenance['source_file'],
                            f"Animation {name} clip metadata differs from its native donor provenance")
            elif name == 'Attack':
                require(False, "Animation Attack lacks native donor provenance")
            report["animations"][name] = clip
            if name in REQUIRED_CLIPS:
                require(animation.get("extras", {}).get("loop") is (name in LOOP_CLIPS),
                        f"Animation {name} extras.loop must be {name in LOOP_CLIPS}")
            targets, maximum_quaternion_error = set(), 0.
            clip_valid = True
            try:
                for channel in animation.get("channels", []):
                    target = channel["target"]
                    key = (target["node"], target["path"])
                    require(key not in targets, f"Animation {name} repeats target {key}")
                    targets.add(key)
                    require(0 <= target["node"] < len(doc["nodes"]), f"Animation {name} target node is out of range")
                    require(target["path"] in ("rotation", "translation", "scale", "weights"), f"Animation {name} has invalid target path")
                    require("matrix" not in doc["nodes"][target["node"]], f"Animation {name} targets a matrix node")
                    sampler = animation["samplers"][channel["sampler"]]
                    times, values = asset.accessor(sampler["input"]).ravel(), asset.accessor(sampler["output"])
                    require(doc["accessors"][sampler["input"]]["type"] == "SCALAR", f"Animation {name} times must be SCALAR")
                    require(len(times) >= 2 and np.isfinite(times).all() and np.all(np.diff(times) > 0), f"Animation {name} times are not finite strictly increasing keys")
                    require(len(times) > 0 and times[0] == 0, f"Animation {name} does not start at zero")
                    interpolation = sampler.get("interpolation", "LINEAR")
                    require(interpolation in ("LINEAR", "STEP", "CUBICSPLINE"), f"Animation {name} interpolation is unsupported")
                    multiplier = 3 if interpolation == "CUBICSPLINE" else 1
                    if target["path"] != "weights":
                        require(len(values) == len(times)*multiplier, f"Animation {name} output/time count mismatch")
                    keys = values[1::3] if multiplier == 3 else values
                    require(np.isfinite(values).all(), f"Animation {name} contains nonfinite output values")
                    if target["path"] == "rotation":
                        require(keys.shape[1] == 4, f"Animation {name} rotation keys must be VEC4")
                        quaternion_error = float(np.max(np.abs(np.linalg.norm(keys, axis=1)-1)))
                        maximum_quaternion_error = max(maximum_quaternion_error, quaternion_error)
                        require(quaternion_error < 2e-4, f"Animation {name} has nonnormalized quaternions ({quaternion_error:.6g})")
                        changes = np.minimum(np.linalg.norm(keys-keys[0], axis=1), np.linalg.norm(keys+keys[0], axis=1))
                        moving = float(changes.max()) > 1e-5
                    else:
                        moving = float(np.max(np.abs(keys-keys[0]))) > 1e-6
                    clip["moving_channels"] += int(moving)
                    clip["duration_seconds"] = max(clip["duration_seconds"], float(times[-1]))
                    if name in LOOP_CLIPS and not np.array_equal(keys[0], keys[-1]):
                        clip["loop_endpoints_exact"] = False
                        errors.append(f"Animation {name} first/last key differs for target {key}")
                require(clip["duration_seconds"] > 0, f"Animation {name} has no positive duration")
                require(clip["moving_channels"] > 0, f"Animation {name} has no motion")
                clip["max_quaternion_error"] = maximum_quaternion_error
            except Exception as exc:
                errors.append(f"Animation {name}: {exc}")
                clip_valid = False
            # This is skin evaluation, not rendering. It verifies exported tracks
            # visibly move geometry and detects exploding/nonfinite deformations.
            if clip_valid and world and not errors:
                try:
                    worlds = [asset.animated_world(animation, clip["duration_seconds"]*fraction)
                              for fraction in POSE_FRACTIONS]
                    poses = [pose_samples(geometry_samples, pose_world) for pose_world in worlds]
                    first = poses[0]
                    if not len(first):
                        raise ValueError("No visible geometry samples")
                    if provenance and animation.get('extras',{}).get('geometryFloorFit'):
                        minimum_y = min(float(posed[:,1].min()) for posed in poses)
                        clip['sampled_minimum_ground_gap'] = minimum_y-ground_reference
                        require(minimum_y >= ground_reference-2e-4,
                                f"Animation {name} deformed geometry crosses the rest ground")
                    maximum_displacement = 0.
                    for posed in poses[1:]:
                        require(np.isfinite(posed).all(), f"Animation {name} deformed positions are nonfinite")
                        maximum_displacement = max(maximum_displacement, float(np.linalg.norm(posed-first, axis=1).max()))
                    clip["sampled_geometry_max_displacement"] = maximum_displacement
                    require(maximum_displacement > 1e-5, f"Animation {name} does not move visible mesh geometry")
                    rest_span = float(np.linalg.norm(np.ptp(first, axis=0)))
                    if maximum_displacement > 3*rest_span:
                        warnings.append(f"Animation {name} displacement is larger than three character spans")
                    if name in ("Walk", "Run"):
                        sampled_poses[name] = np.asarray(poses)
                    if name == "Run":
                        clip["anatomical_arms"] = run_arm_metrics(asset, world, worlds)
                        if provenance:
                            # Donors use character-specific arm carriage (staff,
                            # skirt, idol gestures). Measure it without forcing
                            # every character into the former common arm pose.
                            cycle_worlds = [asset.animated_world(animation, clip['duration_seconds']*fraction)
                                            for fraction in np.linspace(0, 1, 25)]
                            clip['anatomical_legs'] = run_leg_metrics(asset, world, cycle_worlds)
                            for side, leg in clip['anatomical_legs'].items():
                                require(leg['fore_aft_stride_leg_lengths'] > .25,
                                        f"Animation Run {side} has insufficient running stride")
                        else:
                            for side, arm in clip["anatomical_arms"].items():
                                require(arm["mean_outward_upperarm_ratio"] <= .60,
                                        f"Animation Run {side} elbow remains spread through the cycle")
                                require(arm["max_outward_upperarm_ratio"] <= .75,
                                        f"Animation Run {side} elbow spreads too far outward")
                                require(arm["min_elbow_flex_degrees"] >= 25.,
                                        f"Animation Run {side} elbow remains too straight")
                    if name in ("Walk", "Run", "Attack", "Defend", "Victory", "Lose"):
                        fingerprint = attack_fingerprint(asset, world, worlds)
                        if fingerprint:
                            clip["anatomical_motion_fingerprint"] = fingerprint
                        else:
                            warnings.append(f"{name} duplicate-gesture check lacks four named anatomical joints")
                    if name == "Lose":
                        terminal = poses[-1]
                        terminal_displacement = float(np.linalg.norm(terminal-first, axis=1).max())
                        clip["terminal_pose_displacement"] = terminal_displacement
                        require(terminal_displacement > rest_span*.01,
                                "Animation Lose returns to its starting pose instead of ending defeated")
                        end_hold = [pose_samples(geometry_samples, asset.animated_world(
                            animation, clip["duration_seconds"]*fraction)) for fraction in (.8, .9)]
                        hold_error = max(float(np.linalg.norm(held-terminal, axis=1).max()) for held in end_hold)
                        clip["terminal_pose_hold_max_error"] = hold_error
                        require(hold_error < max(rest_span*1e-5, 1e-7),
                                "Animation Lose must hold its terminal pose through the final 20 percent")
                except Exception as exc:
                    errors.append(f"Animation {name} deformation sampling: {exc}")
        if {"Walk", "Run"}.issubset(sampled_poses):
            difference = np.linalg.norm(sampled_poses["Run"]-sampled_poses["Walk"], axis=2)
            span = max(float(np.linalg.norm(np.ptp(sampled_poses["Walk"][0], axis=0))), 1e-12)
            run = report["animations"]["Run"]
            run["walk_normalized_phase_max_difference"] = float(difference.max()/span)
            run["walk_normalized_phase_rms_difference"] = float(np.sqrt(np.mean(difference**2))/span)
            require(run["walk_normalized_phase_max_difference"] > .01 and
                    run["walk_normalized_phase_rms_difference"] > .001,
                    "Animation Run is indistinguishable from a time-scaled Walk at matching phases")
    if not skip_sheets:
        try:
            if sheet_path is None:
                raise ValueError("Sheet path was not supplied")
            with Image.open(sheet_path) as bitmap:
                size, fmt = bitmap.size, bitmap.format
                bitmap.verify()
            metrics["sheet_dimensions"] = list(size)
            require(fmt == "PNG", f"Character sheet format is {fmt}, expected PNG")
            require(size == SHEET_SIZE, f"Character sheet dimensions are {size}, expected {SHEET_SIZE}")
        except Exception as exc:
            errors.append(f"Character sheet: {exc}")
    else:
        warnings.append("Character sheet check was skipped")
    report["status"] = "passed" if not errors else "failed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ids", help="Comma-separated character IDs for a partial check")
    parser.add_argument("--skip-sheets", action="store_true")
    parser.add_argument("--report", default="previews/validation.json", help="Report path relative to root, or - for stdout")
    parser.add_argument("--expected-count", type=int,
                        help="Expected total; defaults to the declared designs in tools/build_characters.py")
    args = parser.parse_args()
    root = args.root.resolve()
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "root": str(root),
              "scope": "GLB structure, accessor safety, skin bind/weights, seven clips, native motion provenance including Attack, exact loops, run/walk distinction, running stride and arm anatomy, held defeat pose, duplicate anatomical gestures/donors and PNG sheets",
              "errors": [], "warnings": [], "characters": []}
    try:
        manifest = json.loads((root/"characters"/"manifest.json").read_text(encoding="utf-8"))
        entries = manifest if isinstance(manifest, list) else manifest["characters"]
        if args.expected_count is None:
            # Read the declarative design list without executing the builder or
            # opening any external donor files. This scales when designs are added.
            expected_ids = declared_design_ids(root/"tools"/"build_characters.py")
            args.expected_count = len(expected_ids)
        else:
            expected_ids = set(range(1, args.expected_count+1))
        ids = {int(value) for value in args.ids.split(",")} if args.ids else None
        if ids:
            entries = [entry for entry in entries if int(entry["id"]) in ids]
            if {int(entry["id"]) for entry in entries} != ids:
                report["errors"].append("Some requested IDs are missing from the manifest")
        elif len(entries) != args.expected_count:
            report["errors"].append(f"Expected {args.expected_count} characters, found {len(entries)}")
        if not ids and {int(entry["id"]) for entry in entries} != expected_ids:
            report["errors"].append("Character IDs do not cover the expected numbered designs")
        if len({entry["id"] for entry in entries}) != len(entries):
            report["errors"].append("Character IDs are repeated in the manifest")
        if len({entry["glb"] for entry in entries}) != len(entries):
            report["errors"].append("Character GLB paths are repeated in the manifest")
        for entry in entries:
            path, sheet = root/entry["glb"], root/entry["sheet"]
            result = check_asset(path, sheet, args.skip_sheets)
            result.update(id=entry["id"], name=entry.get("name", ""), slug=entry.get("slug", ""))
            result["glb"], result["sheet"] = entry["glb"], entry["sheet"]
            if path.exists() and "bytes" in entry and path.stat().st_size != entry["bytes"]:
                result["errors"].append("GLB size differs from manifest bytes")
                result["status"] = "failed"
            for name, clip in result['animations'].items():
                if clip.get('source_file'):
                    provenance = entry.get('motion_sources', {}).get(name, {})
                    if (provenance.get('source_file') != clip['source_file'] or
                            provenance.get('source_clip') != clip['source_clip'] or
                            entry.get('native_clips', {}).get(name) != clip['source_clip']):
                        result['errors'].append(f"Manifest {name} native donor provenance differs from the GLB")
                        result['status'] = 'failed'
            report["characters"].append(result)
        gestures = {name: {} for name in ("Walk", "Run", "Attack", "Defend", "Victory", "Lose")}
        donor_choices = {name: {} for name in ('Run', 'Attack', 'Defend', 'Lose')}
        for character in report["characters"]:
            for name, seen in gestures.items():
                clip = character["animations"].get(name, {})
                if name in donor_choices:
                    source = clip.get('source_file')
                    require_source = source and clip.get('source_clip')
                    source_key = source.casefold() if source else None
                    if not require_source:
                        report['errors'].append(f"{character['slug']} {name} lacks original motion provenance")
                    elif source_key in donor_choices[name]:
                        report['errors'].append(f"{name} donor {source} is reused by {donor_choices[name][source_key]} and {character['slug']}")
                    else:
                        donor_choices[name][source_key] = character['slug']
                if (int(character["id"]) >= 11 or name == 'Attack') and not clip.get("description"):
                    report["errors"].append(f"{character['slug']} {name} lacks its authored motion description")
                fingerprint = clip.get("anatomical_motion_fingerprint")
                if not fingerprint:
                    continue
                earlier = seen.get(fingerprint)
                if earlier and (name in ("Run", "Attack", "Defend", "Lose") or int(character["id"]) >= 11 or int(earlier["id"]) >= 11):
                    report["errors"].append(
                        f"{name} gesture is duplicated between {earlier['slug']} and {character['slug']}")
                else:
                    seen[fingerprint] = character
    except Exception as exc:
        report["errors"].append(f"Manifest: {exc}")
    errors = len(report["errors"])+sum(len(item["errors"]) for item in report["characters"])
    warnings = len(report["warnings"])+sum(len(item["warnings"]) for item in report["characters"])
    report["summary"] = {"characters": len(report["characters"]), "passed": sum(item["status"] == "passed" for item in report["characters"]),
                         "errors": errors, "warnings": warnings, "status": "passed" if errors == 0 else "failed",
                         "sheet_checks_skipped": args.skip_sheets}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report == "-":
        print(encoded)
    else:
        target = Path(args.report)
        target = target if target.is_absolute() else root/target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded+"\n", encoding="utf-8")
        print(f"Validated {len(report['characters'])} characters: {errors} errors, {warnings} warnings. Report: {target}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
