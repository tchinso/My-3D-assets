"""Small, self-contained glTF renderer used to document the delivered assets.

Only embedded glTF 2.0 GLBs are required. Geometry, textures, skinning and glTF
animation channels are evaluated from the actual exported file, not a surrogate.
"""
from __future__ import annotations

import base64
import io
import json
import struct
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

DTYPES = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def quaternion_matrix(q):
    x, y, z, w = np.asarray(q, dtype="f8") / max(np.linalg.norm(q), 1e-12)
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
        [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
    ], dtype="f8")


def slerp(a, b, weight):
    a, b = np.asarray(a, dtype="f8"), np.asarray(b, dtype="f8")
    a /= max(np.linalg.norm(a), 1e-12)
    b /= max(np.linalg.norm(b), 1e-12)
    dot = float(np.dot(a, b))
    if dot < 0:
        b, dot = -b, -dot
    if dot > 0.9995:
        result = a + weight * (b-a)
        return result / max(np.linalg.norm(result), 1e-12)
    theta = np.arccos(np.clip(dot, -1, 1))
    return (np.sin((1-weight)*theta)*a + np.sin(weight*theta)*b) / np.sin(theta)


class GLB:
    def __init__(self, path):
        self.path = Path(path)
        data = self.path.read_bytes()
        if len(data) < 12 or data[:4] != b"glTF":
            raise ValueError(f"Not a GLB: {path}")
        magic, version, length = struct.unpack_from("<4sII", data)
        if version != 2 or length != len(data):
            raise ValueError(f"Invalid GLB header: {path}")
        self.doc, self.bin = None, b""
        offset = 12
        while offset < len(data):
            length, kind = struct.unpack_from("<II", data, offset)
            chunk = data[offset+8:offset+8+length]
            if kind == 0x4E4F534A:
                self.doc = json.loads(chunk)
            elif kind == 0x004E4942:
                self.bin = chunk
            offset += 8+length
        if self.doc is None:
            raise ValueError(f"Missing GLB JSON: {path}")
        self.cache, self.image_cache = {}, {}
        self.global_mats, self.active_nodes = {}, []
        self.evaluate()

    def accessor(self, index):
        if index in self.cache:
            return self.cache[index]
        accessor = self.doc["accessors"][index]
        count, components = accessor["count"], COMPONENTS[accessor["type"]]
        dtype = np.dtype(DTYPES[accessor["componentType"]])
        if "bufferView" in accessor:
            view = self.doc["bufferViews"][accessor["bufferView"]]
            offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            array = np.ndarray((count, components), dtype=dtype, buffer=self.bin, offset=offset,
                               strides=(view.get("byteStride", dtype.itemsize*components), dtype.itemsize)).copy()
        else:
            array = np.zeros((count, components), dtype=dtype)
        if "sparse" in accessor:
            sparse = accessor["sparse"]
            iv = self.doc["bufferViews"][sparse["indices"]["bufferView"]]
            ids = np.frombuffer(self.bin, DTYPES[sparse["indices"]["componentType"]], sparse["count"],
                                iv.get("byteOffset", 0)+sparse["indices"].get("byteOffset", 0))
            vv = self.doc["bufferViews"][sparse["values"]["bufferView"]]
            values = np.frombuffer(self.bin, dtype, sparse["count"]*components,
                                   vv.get("byteOffset", 0)+sparse["values"].get("byteOffset", 0)).reshape(-1, components)
            array[ids] = values
        if accessor.get("normalized") and dtype.kind in "iu":
            array = array.astype("f4") / np.iinfo(dtype).max
            if dtype.kind == "i":
                array = np.maximum(array, -1)
        self.cache[index] = array
        return array

    def image(self, index):
        if index not in self.image_cache:
            source = self.doc["images"][index]
            if "bufferView" in source:
                view = self.doc["bufferViews"][source["bufferView"]]
                encoded = self.bin[view.get("byteOffset", 0):view.get("byteOffset", 0)+view["byteLength"]]
            elif source["uri"].startswith("data:"):
                encoded = base64.b64decode(source["uri"].split(",", 1)[1])
            else:
                encoded = (self.path.parent/source["uri"]).read_bytes()
            self.image_cache[index] = Image.open(io.BytesIO(encoded)).convert("RGBA")
        return self.image_cache[index]

    @property
    def animations(self):
        return [animation.get("name", f"Animation {index+1}")
                for index, animation in enumerate(self.doc.get("animations", []))]

    def animation(self, name):
        if name is None:
            return None
        if isinstance(name, int):
            return self.doc["animations"][name]
        for animation in self.doc.get("animations", []):
            if animation.get("name", "").lower() == name.lower():
                return animation
        return None

    def duration(self, name):
        animation = self.animation(name)
        if animation is None:
            return 0.0
        return max(float(self.accessor(s["input"])[-1, 0]) for s in animation["samplers"])

    def sample(self, sampler, time, path):
        times = self.accessor(sampler["input"]).ravel()
        output = self.accessor(sampler["output"])
        interpolation = sampler.get("interpolation", "LINEAR")
        if path == "weights":
            # glTF represents all morph weights at a frame as concatenated SCALARs.
            divisor = 3 if interpolation == "CUBICSPLINE" else 1
            output = output.reshape(len(times)*divisor, -1)
        if interpolation == "CUBICSPLINE":
            output = output.reshape(len(times), 3, -1)
        if len(times) == 1 or time <= times[0]:
            value = output[0, 1] if interpolation == "CUBICSPLINE" else output[0]
        elif time >= times[-1]:
            value = output[-1, 1] if interpolation == "CUBICSPLINE" else output[-1]
        else:
            right = int(np.searchsorted(times, time, side="right"))
            left = right-1
            delta = float(times[right]-times[left])
            weight = float((time-times[left])/delta)
            if interpolation == "STEP":
                value = output[left]
            elif interpolation == "CUBICSPLINE":
                p0, p1 = output[left, 1], output[right, 1]
                m0, m1 = delta*output[left, 2], delta*output[right, 0]
                t2, t3 = weight*weight, weight*weight*weight
                value = (2*t3-3*t2+1)*p0 + (t3-2*t2+weight)*m0 + (-2*t3+3*t2)*p1 + (t3-t2)*m1
            elif path == "rotation":
                value = slerp(output[left], output[right], weight)
            else:
                value = output[left]*(1-weight) + output[right]*weight
        if path == "rotation":
            value = value/max(np.linalg.norm(value), 1e-12)
        return value

    def evaluate(self, animation=None, time=0, loop=False):
        clip = self.animation(animation)
        overrides = {}
        if clip is not None:
            duration = self.duration(animation)
            if loop and duration > 0:
                time %= duration
            for channel in clip["channels"]:
                target = channel["target"]
                if "node" in target:
                    overrides.setdefault(target["node"], {})[target["path"]] = self.sample(
                        clip["samplers"][channel["sampler"]], time, target["path"])
        self.overrides = overrides
        self.global_mats, self.active_nodes = {}, []
        roots = self.doc["scenes"][self.doc.get("scene", 0)]["nodes"]
        for node in roots:
            self._walk(node, np.eye(4))

    def _walk(self, index, parent):
        node = self.doc["nodes"][index]
        override = self.overrides.get(index, {})
        if "matrix" in node and not override:
            local = np.asarray(node["matrix"], dtype="f8").reshape(4, 4).T
        else:
            local = np.eye(4)
            rotation = override.get("rotation", node.get("rotation", [0, 0, 0, 1]))
            scale = override.get("scale", node.get("scale", [1, 1, 1]))
            local[:3, :3] = quaternion_matrix(rotation) @ np.diag(scale)
            local[:3, 3] = override.get("translation", node.get("translation", [0, 0, 0]))
        self.global_mats[index] = parent @ local
        self.active_nodes.append(index)
        for child in node.get("children", []):
            self._walk(child, self.global_mats[index])

    def meshes(self, animation=None, time=0, loop=False):
        self.evaluate(animation, time, loop)
        result, first_mouth = [], None
        for node_index in self.active_nodes:
            node = self.doc["nodes"][node_index]
            if "mesh" not in node:
                continue
            name = node.get("name", "")
            if name.lower().startswith("mouth_"):
                if first_mouth is None:
                    first_mouth = node_index
                elif node_index != first_mouth:
                    continue
            mesh = self.doc["meshes"][node["mesh"]]
            skin_matrices = None
            if "skin" in node:
                skin = self.doc["skins"][node["skin"]]
                inverse = (self.accessor(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
                           if "inverseBindMatrices" in skin else np.tile(np.eye(4), (len(skin["joints"]), 1, 1)))
                skin_matrices = np.array([self.global_mats[joint] @ inverse[i] for i, joint in enumerate(skin["joints"])])
            for primitive in mesh["primitives"]:
                if primitive.get("mode", 4) != 4:
                    continue
                attrs = primitive["attributes"]
                position = self.accessor(attrs["POSITION"]).astype("f4").copy()
                normal = (self.accessor(attrs["NORMAL"]).astype("f4").copy() if "NORMAL" in attrs
                          else np.tile([0, 0, 1], (len(position), 1)).astype("f4"))
                uv = (self.accessor(attrs["TEXCOORD_0"]).astype("f4") if "TEXCOORD_0" in attrs
                      else np.zeros((len(position), 2), dtype="f4"))
                morph_weights = self.overrides.get(node_index, {}).get("weights", node.get("weights", mesh.get("weights", [])))
                for weight, target in zip(morph_weights, primitive.get("targets", [])):
                    if "POSITION" in target:
                        position += weight*self.accessor(target["POSITION"])
                    if "NORMAL" in target:
                        normal += weight*self.accessor(target["NORMAL"])
                v4 = np.column_stack((position, np.ones(len(position), dtype="f4")))
                if skin_matrices is not None and "JOINTS_0" in attrs:
                    joints = self.accessor(attrs["JOINTS_0"]).astype(int)
                    weights = self.accessor(attrs["WEIGHTS_0"]).astype("f4")
                    blend = (skin_matrices[joints] * weights[:, :, None, None]).sum(axis=1)
                    position = np.einsum("nij,nj->ni", blend, v4)[:, :3]
                    normal = np.einsum("nij,nj->ni", blend[:, :3, :3], normal)
                else:
                    matrix = self.global_mats[node_index]
                    position = (v4 @ matrix.T)[:, :3]
                    normal = normal @ np.linalg.inv(matrix[:3, :3])
                indices = (self.accessor(primitive["indices"]).ravel().astype("u4") if "indices" in primitive
                           else np.arange(len(position), dtype="u4"))
                if not len(indices):
                    continue
                used = position[np.unique(indices)]
                result.append({"name": name, "material": primitive.get("material"), "pos": position.astype("f4"),
                               "normals": normal.astype("f4"), "uv": uv, "indices": indices,
                               "min": used.min(axis=0), "max": used.max(axis=0)})
        return result


def mesh_bounds(meshes):
    return np.min([m["min"] for m in meshes], axis=0), np.max([m["max"] for m in meshes], axis=0)


class Renderer:
    def __init__(self, width=500, height=900, context=None):
        self.width, self.height = width, height
        self.owns_context = context is None
        self.ctx = context if context is not None else moderngl.create_standalone_context()
        self.fbo = self.ctx.simple_framebuffer((width, height), components=4)
        self.program = self.ctx.program(vertex_shader="""
            #version 330
            uniform mat4 mvp;
            in vec3 in_pos; in vec3 in_normal; in vec2 in_uv;
            out vec3 vnormal; out vec2 uv;
            void main(){gl_Position=mvp*vec4(in_pos,1);vnormal=in_normal;uv=in_uv;}
        """, fragment_shader="""
            #version 330
            uniform sampler2D tex; uniform vec4 color; uniform float cutoff;
            uniform int mode; uniform int unlit;
            in vec3 vnormal; in vec2 uv; out vec4 frag;
            void main(){
                vec4 c=texture(tex,uv)*color;
                if(mode==1 && c.a<cutoff)discard;
                if(mode==0)c.a=1;
                if(c.a<0.01)discard;
                float light=unlit==1 ? 1.0 : 0.82+0.18*abs(dot(normalize(vnormal),normalize(vec3(-0.3,0.6,1))));
                frag=vec4(c.rgb*light,c.a);
            }
        """)
        self.texture_cache = {}
        self.white = self.ctx.texture((1, 1), 4, b"\xff\xff\xff\xff")

    def render(self, glb, meshes, angle=0, bounds=None, padding=1.10, background=(0.94, 0.96, 0.97, 1), camera_half_height=None):
        """Orthographic render; +Z is front and positive angle shows right side."""
        if not meshes:
            raise ValueError(f"No active triangle meshes in {glb.path}")
        ctx = self.ctx
        if str(glb.path) not in self.texture_cache:
            textures = []
            for texture in glb.doc.get("textures", []):
                im = glb.image(texture["source"])
                gpu = ctx.texture(im.size, 4, im.tobytes())
                gpu.filter = (moderngl.LINEAR, moderngl.LINEAR)
                textures.append(gpu)
            self.texture_cache[str(glb.path)] = textures
        textures = self.texture_cache[str(glb.path)]
        renderables = []
        for mesh in meshes:
            buffer = ctx.buffer(np.column_stack((mesh["pos"], mesh["normals"], mesh["uv"])).astype("f4").tobytes())
            index_buffer = ctx.buffer(mesh["indices"].tobytes())
            vao = ctx.vertex_array(self.program, [(buffer, "3f 3f 2f", "in_pos", "in_normal", "in_uv")],
                                   index_buffer, index_element_size=4)
            material = glb.doc.get("materials", [])[mesh["material"]] if mesh["material"] is not None else {}
            renderables.append((vao, buffer, index_buffer, material, mesh))
        low, high = mesh_bounds(meshes) if bounds is None else bounds
        center = (low+high)/2
        span = high-low
        radians = np.deg2rad(angle)
        view = np.array([[np.cos(radians), 0, -np.sin(radians), 0], [0, 1, 0, 0],
                         [np.sin(radians), 0, np.cos(radians), 0], [0, 0, 0, 1]], dtype="f4")
        # Fit the rotated bounding box, with the same vertical scale across views.
        view_width = abs(np.cos(radians))*span[0] + abs(np.sin(radians))*span[2]
        half_height = (max(span[1]/2, view_width/2*self.height/self.width, 1e-3)*padding
                       if camera_half_height is None else camera_half_height)
        half_width = half_height*self.width/self.height
        far = max(span.max()*4, 0.1)
        ortho = np.array([[1/half_width, 0, 0, 0], [0, 1/half_height, 0, 0],
                          [0, 0, -1/far, 0], [0, 0, 0, 1]], dtype="f4")
        view[:3, 3] = -view[:3, :3]@center
        self.program["mvp"].write((ortho@view).T.astype("f4").tobytes())
        self.fbo.use()
        self.fbo.clear(*background, depth=1)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.CULL_FACE)
        # Transparent primitives sort from farthest to nearest camera-space center.
        renderables.sort(key=lambda item: float((view @ np.r_[((item[4]["min"]+item[4]["max"])/2), 1])[2]))
        for blending in [False, True]:
            if blending:
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
                ctx.depth_mask = False
            else:
                ctx.disable(moderngl.BLEND)
                ctx.depth_mask = True
            for vao, _, _, material, _ in renderables:
                mode = material.get("alphaMode", "OPAQUE")
                if (mode == "BLEND") != blending:
                    continue
                pbr = material.get("pbrMetallicRoughness", {})
                (textures[pbr["baseColorTexture"]["index"]] if "baseColorTexture" in pbr else self.white).use(0)
                self.program["color"].value = tuple(pbr.get("baseColorFactor", [1, 1, 1, 1]))
                self.program["mode"].value = {"OPAQUE": 0, "MASK": 1, "BLEND": 2}[mode]
                self.program["cutoff"].value = material.get("alphaCutoff", 0.5)
                self.program["unlit"].value = int("KHR_materials_unlit" in material.get("extensions", {}))
                vao.render()
        ctx.depth_mask = True
        im = Image.frombytes("RGBA", (self.width, self.height), self.fbo.read(components=4)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        for vao, buffer, index_buffer, _, _ in renderables:
            vao.release()
            buffer.release()
            index_buffer.release()
        return im.convert("RGB")

    def close(self):
        for textures in self.texture_cache.values():
            for texture in textures:
                texture.release()
        self.white.release()
        self.fbo.release()
        self.program.release()
        if self.owns_context:
            self.ctx.release()
