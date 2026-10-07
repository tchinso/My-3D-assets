"""Catalog the delivered characters and their local donor provenance.

Usage: python tools/build_catalog.py --source C:/Codex/BlueArchiveGLB
Writes models.json, model_features.json and model_features.schema.json at the
repository root. models.json retains the supplied timestamp-inventory format.
The feature catalog distinguishes authored final appearance from donor metadata;
it does not infer physical height from a shared SD rig or copy donor profile height.
No GLB, character sheet, manifest, or source-corpus file is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("C:/Codex/BlueArchiveGLB")
SOURCE_FILES = ("models.json", "model_features.json", "model_features.schema.json")
CLIPS = ("Idle", "Walk", "Run", "Attack", "Defend", "Victory", "Lose")

# These describe the fitted and repainted actual donor garments. Donor facts
# are copied separately below and are never substituted for these final features.
APPEARANCE = {
    1: dict(hair_colors=["분홍색"], length="매우 긴 머리", styles=["롤 트윈테일", "느슨한 1–2회 컬", "앞머리", "아호게", "부분 땋은 머리"],
            hair="Hatsune Miku의 긴 분홍색 트윈테일을 참고 이미지처럼 느슨한 1–2회 롤로 조정하고 Erika의 실제 휘어진 아호게를 조합. 메이드 헤드밴드와 뿌리·옆머리 땋은 디테일, 남색 리본·작은 진주·차와 숟가락 모티프 장식을 유지",
            outfit_styles=["메이드복"], outfit_colors=["흰색", "남색"],
            outfit="Momoi (Maid)의 실제 짧은 메이드 드레스와 앞치마·프릴·리본을 흰색과 남색으로 편집",
            legs=["흰색 팬티스타킹"], feet=["원본 메이드 구두"],
            features=["주름진 메이드 헤드밴드", "앞치마와 원본 프릴", "차 숟가락 모티프 레이피어", "느슨한 1–2회 롤 트윈테일", "아호게", "트윈테일 뿌리·옆머리 땋은 디테일", "남색 머리 리본", "작은 진주와 차·숟가락 머리 장식"],
            weapon="숟가락 모양 가드가 있는 리본 레이피어"),
    2: dict(hair_colors=["파란색", "보라색"], length="짧은 머리", styles=["레이어드 단발", "앞머리", "바깥으로 뒤집힌 끝", "아호게"],
            hair="Erika의 짧은 레이어드 단발과 바깥으로 뒤집힌 끝·아호게를 참고 이미지의 진한 청보라색으로 편집하고 한쪽의 커다란 파란 장미를 유지",
            outfit_styles=["사신풍 의상", "짧은 드레스", "숄"], outfit_colors=["보라색", "파란색", "진파랑"],
            outfit="Haruka (Dress)의 짧은 드레스와 비치는 어깨 숄을 파란색·보라색으로 편집하고 원본 옷 주름을 유지",
            legs=["허벅지 중간까지 오는 진파랑 사이하이", "스타킹 위로 보이는 맨 허벅지"],
            feet=["원본 스트랩 구두"],
            features=["한쪽의 큰 파란 장미", "비치는 숄", "초승달 모양 낫"],
            weapon="진한 손잡이와 파란 척추 장식이 있는 초승달 낫"),
    3: dict(hair_colors=["하늘색"], length="매우 긴 머리", styles=["레이어드 웨이브", "중앙의 뾰족한 앞머리", "한쪽 작은 땋은 머리"],
            hair="Azusa (Swimsuit)의 뾰족한 중앙 앞머리·얼굴 옆 머리와 Miyo의 묶이지 않은 긴 레이어드 웨이브를 조합해 하늘색으로 편집. 작은 옆 땋은 머리와 파란 꽃",
            outfit_styles=["블레이저", "블라우스", "타탄 주름치마"], outfit_colors=["회색", "검은색", "흰색", "빨간색"],
            outfit="Serika의 실제 허리가 들어간 블레이저를 회색으로 편집하고 라펠·주머니·소매에 검은 파이핑을 적용. 흰 칼라 블라우스, 빨강·검정 타탄 긴 넥타이와 주름치마",
            legs=["맨다리"], feet=["원본 운동화"],
            features=["중앙의 뾰족한 앞머리", "분리된 얼굴 옆 머리", "파란 머리 꽃", "작은 옆 땋은 머리", "검은 블레이저 파이핑", "빨강·검정 타탄 넥타이와 치마"],
            weapon="하늘색 참과 작은 금색 손잡이"),
    4: dict(hair_colors=["금발"], length="긴 머리", styles=["생머리", "앞머리"],
            hair="양옆과 등으로 곧게 내려오는 금발 긴 생머리",
            outfit_styles=["원피스", "드레스"], outfit_colors=["흰색", "파란색"],
            outfit="Sena (Casual)의 흰색·파란색 민소매 여름 원피스, 허리 리본과 반투명 레이스 밑단을 유지",
            legs=["흰색 팬티스타킹"], feet=["원본 흰색 구두"],
            features=["흐르는 원피스 치마", "반투명 레이스와 겹친 밑단", "파란 허리 리본", "푸른 손 참"],
            weapon="푸른 보석 모티프 손 참"),
    5: dict(hair_colors=["연한 분홍색"], length="긴 머리", styles=["생머리", "한쪽 높은 포니테일", "앞머리"],
            hair="연분홍색 긴 뒷머리와 한쪽에 묶어 포인트를 준 옆머리, 분홍색 리본",
            outfit_styles=["블레이저", "교복", "주름치마"], outfit_colors=["장미색", "흰색", "회색"],
            outfit="Reisa의 실제 교복 재킷·라펠·블라우스와 짧은 주름치마를 장미색으로 편집. 골격을 유지하며 몸통·소매·치마·다리의 단면을 슬림하게 조정",
            legs=["맨다리"], feet=["원본 분홍색·하늘색 운동화"],
            features=["한쪽 머리 리본", "블레이저 라펠과 단추", "원본 주름치마", "작은 손 참"],
            weapon="책갈피 모티프의 작은 손 참"),
    6: dict(hair_colors=["흰색"], length="짧은 머리", styles=["단발", "앞머리", "삐친 머리"],
            hair="바깥쪽으로 끝이 뻗치는 흰색 짧은 머리",
            outfit_styles=["날개 없는 요정풍", "호박팬츠"], outfit_colors=["연두색", "흰색", "녹색"],
            outfit="Ibuki의 실제 프릴 호박팬츠와 상의를 흰색·연두색으로 편집하고 긴 코트·날개·부츠를 제거",
            legs=["맨다리"], feet=["맨발", "원본 해부학 발 메시"],
            features=["날개 없음", "잎사귀 칼라", "원본 프릴 호박팬츠", "클로버 지팡이"],
            weapon="세 장의 클로버 잎이 달린 지팡이"),
    7: dict(hair_colors=["분홍색"], length="매우 긴 머리", styles=["레이어드 웨이브", "앞머리", "양쪽 땋은 번"],
            hair="참고 이미지의 긴 분홍 레이어드 머리와 얼굴을 감싸는 앞머리, 양쪽 땋은 번을 원본 머리 파츠 조합과 수정으로 표현. 분홍색 고양이 귀 유지",
            outfit_styles=["현대 캐주얼", "크롭 재킷", "반바지"], outfit_colors=["흰색", "분홍색", "검은색"],
            outfit="Saori (Swimsuit)의 짧은 재킷·크롭 상의와 반바지를 흰색·분홍색 계열로 편집하고 배꼽 부분을 노출",
            legs=["검은색 팬티스타킹"], feet=["원본 캐주얼 신발"],
            features=["뾰족한 고양이 귀", "긴 분홍 레이어드 머리", "양쪽 땋은 번", "부드러운 얼굴", "노출된 배꼽", "휘어진 분홍색 고양이 꼬리", "원본 재킷 봉제선"],
            weapon="별도 무기 없이 주먹 공격"),
    8: dict(hair_colors=["연한 분홍색", "민트색", "아쿠아색"], length="중간 길이", styles=["롤 트윈테일", "넓은 2회 컬", "앞머리", "중앙 앞머리 컬"],
            hair="Reisa (Magical)의 정수리·앞머리·얼굴 옆 머리를 유지하고 Hatsune Miku의 실제 긴 트윈테일 파츠를 어깨 부근의 두 개의 넓은 C 컬로 조합. 연분홍색 뿌리에서 민트색·아쿠아색 끝으로 이어지는 그라데이션과 중앙 앞머리 컬을 추가",
            outfit_styles=["인형 드레스", "프릴 의상"], outfit_colors=["빨간색", "흰색", "분홍색"],
            outfit="Reisa (Magical)의 원래 리본·레이스·프릴 드레스를 빨간색·흰색으로 편집하고 실제 드릴 트윈테일을 유지",
            legs=["흰색 팬티스타킹"], feet=["원본 리본 구두"],
            features=["어깨 부근의 넓은 2회 롤 트윈테일", "민트색·아쿠아색 머리 끝 그라데이션", "중앙 앞머리 컬", "원본 프릴과 레이스", "큰 리본", "등 뒤 작은 태엽"],
            weapon="작은 흰색 인형 참"),
    9: dict(hair_colors=["검은색에 가까운 갈색"], length="매우 긴 머리", styles=["트윈테일", "생머리", "앞머리"],
            hair="참고 이미지처럼 아래까지 충분한 볼륨이 이어지는 검갈색 긴 트윈테일과 앞머리. 묶는 부분에 빨강 리본과 금색 장식 추가",
            outfit_styles=["치파오", "중국 전통풍", "짧은 치마"], outfit_colors=["빨간색", "금색"],
            outfit="Kisaki의 긴 겉옷을 제거한 실제 짧은 치파오. 양쪽 옆트임과 등 트임, 높은 칼라·금색 용무늬를 유지하고 빨간색으로 편집",
            legs=["맨다리", "양쪽 치마 옆트임으로 드러나는 다리"],
            feet=["원본 굽 있는 구두"],
            features=["양쪽 옆트임", "등 트임", "금색 용무늬와 매듭", "풍성한 긴 트윈테일", "빨강·금색 머리묶음 장식", "빨간 접이식 부채"],
            weapon="금색 부챗살이 있는 펼친 빨간 부채"),
    10: dict(hair_colors=["흰색"], length="긴 머리", styles=["풍성한 웨이브", "양쪽 번", "앞머리"],
             hair="흰색으로 바꾼 풍성한 긴 웨이브와 머리 양끝의 둥근 번",
             outfit_styles=["짧은 드레스", "퍼 볼레로"], outfit_colors=["흰색", "아주 연한 보라색"],
             outfit="Mutsuki (Dress)의 실제 짧은 프릴 드레스와 풍성한 퍼 볼레로를 흰색으로 편집하며 옷 주름과 털 가장자리를 유지",
             legs=["흰색 팬티스타킹"], feet=["원본 스트랩 구두"],
             features=["양끝의 번", "풍성한 퍼 칼라", "원본 프릴 치맛단", "흰색 손 참"],
             weapon="작은 구름색 참"),
    11: dict(hair_colors=["갈색"], length="매우 긴 머리", styles=["트윈테일", "느슨한 웨이브", "앞머리"],
             hair="Shizuko (Swimsuit)의 긴 부분 트윈테일과 얼굴 옆 머리를 갈색으로 편집. 트윈테일 뿌리를 두피에 맞춰 피팅하고 양쪽 뿌리의 앞 표면에 붉은 리본을 부착",
             outfit_styles=["모험가 의상", "크롭 재킷", "프릴 치마"], outfit_colors=["갈색", "크림색", "금색"],
             outfit="Sakurako (Idol)의 실제 프릴 드레스·넓은 소매·허리 파츠를 갈색 모험가 의상으로 편집하고 크림색 크라바트, 가죽 허리 벨트·옆 가방·긴 부츠를 추가",
             legs=["맨다리"], feet=["갈색 부츠"],
             features=["붉은 트윈테일 리본", "크림색 가슴 프릴", "가죽색 허리 벨트", "크로스백", "쌍단검"],
             weapon="양손에 장착한 짧은 쌍단검"),
    12: dict(hair_colors=["금발"], length="짧은 머리", styles=["단발", "한쪽 작은 포니테일", "앞머리"],
             hair="Izuna (Swimsuit)의 단발·작은 옆 포니테일·여우 귀를 황금색으로 편집하고 원본 수영 머리띠를 별 장식으로 교체",
             outfit_styles=["아이돌 의상", "크롭 재킷", "분리형 소매", "분할 롱스커트"],
             outfit_colors=["크림색", "주황색", "청록색", "노란색"],
             outfit="Seia의 실제 흰색·주황색 의상과 넓은 소매를 크롭 실루엣으로 편집하고 Hina (Swimsuit)의 해부학 복부 메시로 노출된 허리를 조합. 청록색 짧은 주름치마·노랑 체크 분할 패널·주황색 가장자리를 추가",
             legs=["맨다리"], feet=["원본 구두"],
             features=["황금색 여우 귀", "크롭 상의", "노출된 복부", "넓은 분리형 소매", "주황색·청록색 목 리본", "긴 분할 치마 패널", "별과 방울 장식"],
             weapon="별과 방울이 달린 공연용 배턴"),
    13: dict(hair_colors=["적갈색"], length="매우 긴 머리", styles=["풍성한 웨이브", "긴 컬", "앞머리"],
             hair="Yuzu (Maid)의 매우 긴 웨이브를 적갈색으로 편집하고 Eri의 실제 뾰족한 모자에 꽃과 하늘색 리본을 추가",
             outfit_styles=["마녀 의상", "프릴 드레스", "망토"], outfit_colors=["분홍색", "크림색", "남색", "금색"],
             outfit="Reisa (Magical)의 실제 프릴 드레스를 분홍색·크림색으로 편집하고 넓은 소매, 금색 별무늬의 남색 망토·분홍 안감과 꽃 달린 마녀 모자를 추가",
             legs=["흰색 팬티스타킹"], feet=["원본 리본 구두"],
             features=["꽃 달린 뾰족한 마녀 모자", "긴 적갈색 컬", "별무늬 망토", "꽃 지팡이", "마법책"],
             weapon="꽃 장식의 긴 지팡이와 허리에 매단 작은 마법책"),
    14: dict(hair_colors=["연한 금발"], length="매우 긴 머리", styles=["긴 컬", "웨이브", "앞머리"],
             hair="Seia (Swimsuit)의 연한 금발 옆 컬을 느슨하게 조정하고 반대쪽에도 반사해 풍성한 긴 컬로 구성. 여우 귀·선캡을 제거하고 작은 보석 왕관을 추가",
             outfit_styles=["웨딩 드레스", "겹프릴 드레스", "하이로 드레스"], outfit_colors=["흰색", "아주 연한 보라색", "금색"],
             outfit="Saori (Dress) (Cafe)의 실제 코르셋·가슴 레이스·큰 리본과 골격을 유지하고 긴 치마를 흰색·연보라색 여러 겹의 하이로 프릴로 편집. Hina (Swimsuit)의 연속된 다리·맨발 메시를 조합",
             legs=["맨다리"], feet=["맨발", "원본 해부학 발 메시"],
             features=["보석 작은 왕관", "긴 연금발 컬", "흰색 겹프릴", "뒤로 흐르는 드레스 자락", "흰 장미 부케", "맨발"],
             weapon="흰 장미와 잎을 묶은 부케"),
}


def schema_document(design_ids=None):
    design_ids = sorted(APPEARANCE if design_ids is None else design_ids)
    count = len(design_ids)
    strings = {"type": "array", "items": {"type": "string"}, "uniqueItems": True}

    def obj(properties, required=None):
        return {"type": "object", "properties": properties,
                "required": list(properties) if required is None else required, "additionalProperties": False}

    ref = lambda name: {"$ref": f"#/$defs/{name}"}
    hair = obj({"colors": ref("strings"), "color_hex": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "length": {"enum": ["짧은 머리", "중간 길이", "긴 머리", "매우 긴 머리"]},
                "styles": ref("strings"), "description": {"type": "string"}})
    outfit = obj({"styles": ref("strings"), "colors": ref("strings"), "description": {"type": "string"},
                  "legwear": ref("strings"), "footwear": ref("strings")})
    body = obj({"build": {"type": "null"}, "proportions": {"const": "SD"}, "description": {"type": "string"}})
    rig = obj({"name": {"type": "string"}, "skin_count": {"type": "integer", "minimum": 1},
               "joint_count": {"type": "integer", "minimum": 1}, "up_axis": {"const": "+Y"},
               "front_axis": {"const": "+Z"}, "physical_height_inferred": {"const": False}})
    native = {"oneOf": [
        obj({name: {"type": "string", "minLength": 1} for name in ("Idle", "Walk", "Victory")}),
        {"const": {}},
    ]}
    head_fit = obj({name: {"type": "number"} for name in ("neck_top", "chin_target", "vertical_adjustment")})
    source_roles = {"type": "object", "minProperties": 3,
                    "required": ["costume_and_rig", "hair", "face"],
                    "propertyNames": {"pattern": "^[a-z][a-z0-9_]*$"},
                    "additionalProperties": {"type": "string", "pattern": "\\.glb$"}}
    model = obj({
        "id": {"type": "integer", "enum": design_ids}, "character": {"type": "string"},
        "name_ko": {"type": "string"}, "slug": {"type": "string"}, "filename": {"type": "string", "pattern": "\\.glb$"},
        "glb": {"type": "string", "pattern": "^characters/.+\\.glb$"},
        "sheet": {"type": "string", "pattern": "^characters/.+_sheet\\.png$"},
        "bytes": {"type": "integer", "minimum": 1}, "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "variants": ref("strings"), "height": {"type": "null"}, "body": ref("body"),
        "hair": ref("hair"), "outfit": ref("outfit"), "features": ref("strings"), "tags": ref("strings"),
        "palette": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}},
        "design_brief": {"type": "string"}, "weapon": {"type": "string"},
        "animations": {"type": "array", "items": {"enum": list(CLIPS)},
                       "minItems": 7, "maxItems": 7, "uniqueItems": True},
        "animation_duration_seconds": obj({name: {"type": "number", "exclusiveMinimum": 0}
                                             for name in CLIPS}),
        "native_source_clips": native, "attack_motion": {"const": "custom skeletal animation"},
        "attack_description": {"type": "string", "minLength": 1},
        "walk_description": {"type": "string", "minLength": 1},
        "victory_description": {"type": "string", "minLength": 1},
        "animation_playback": obj({name: {"const": "loop" if name in ("Idle", "Walk", "Run") else
                                          "once_hold" if name == "Lose" else "once"} for name in CLIPS}),
        "build_revision": {"type": "integer", "minimum": 2}, "head_fit": head_fit,
        "rig": ref("rig"), "mesh_count": {"type": "integer", "minimum": 1},
        "triangle_count": {"type": "integer", "minimum": 1},
        "source_parts": ref("strings"),
        "source_roles": source_roles,
        "evidence": obj({"manifest": {"const": "characters/manifest.json"},
                         "builder": {"const": "tools/build_characters.py"}, "character_sheet": {"type": "string"},
                         "appearance_method": {"type": "string"}, "height_method": {"type": "string"}}),
        "review_notes": ref("strings"),
    })
    # Older delivered characters retain their existing fields; these descriptions
    # are recorded when the final clip carries authored motion metadata.
    model["required"] = [key for key in model["required"]
                         if key not in ("walk_description", "victory_description")]
    donor_hair = obj({"colors": ref("strings"), "length": {"type": ["string", "null"]},
                      "styles": ref("strings"), "description": {"type": ["string", "null"]}})
    donor_outfit = obj({"styles": ref("strings"), "colors": ref("strings"),
                        "description": {"type": ["string", "null"]}, "legwear": ref("strings"), "footwear": ref("strings")})
    donor = obj({"character": {"type": "string"}, "source_timestamp": {"type": "integer"},
                 "original_hair": ref("donor_hair"), "original_outfit": ref("donor_outfit"),
                 "original_features": ref("strings"),
                 "source_confidence": obj({field: {"enum": ["높음", "보통", "낮음", "미확인"]}
                                           for field in ("hair", "outfit", "features")}),
                 "evidence": obj({"local_glb": {"type": "string"},
                                  "preview_front": {"type": ["string", "null"]}, "preview_back": {"type": ["string", "null"]}})})
    source_catalog = obj({"root": {"type": "string"}, "inspected_files": {"type": "array", "items": {"enum": list(SOURCE_FILES)},
                                                                             "minItems": 3, "maxItems": 3, "uniqueItems": True},
                          "catalog_model_count": {"type": "integer", "minimum": 1},
                          "timestamp_inventory_count": {"type": "integer", "minimum": 1},
                          "source_schema_title": {"type": "string"}, "source_schema_uri": {"type": "string"},
                          "donor_height_policy": {"type": "string"}})
    guide = obj({key: {"type": "string"} for key in ("appearance", "height", "body", "legwear", "provenance", "animations")})
    schema = obj({
        "schema_version": {"const": "1.0"}, "analyzed_on": {"type": "string", "format": "date"},
        "model_count": {"const": count}, "classification_guide": guide, "source_catalog": ref("source_catalog"),
        "donors": {"type": "object", "minProperties": 1, "propertyNames": {"pattern": "\\.glb$"}, "additionalProperties": ref("donor")},
        "models": {"type": "object", "minProperties": count, "maxProperties": count,
                   "propertyNames": {"pattern": "^characters/.+\\.glb$"}, "additionalProperties": ref("model")},
    })
    schema.update({"$schema": "https://json-schema.org/draft/2020-12/schema",
                   "title": "My-3D-assets generated SD character appearance catalog",
                   "$defs": {"strings": strings, "hair": hair, "outfit": outfit, "body": body,
                             "rig": rig, "model": model, "donor_hair": donor_hair,
                             "donor_outfit": donor_outfit, "donor": donor, "source_catalog": source_catalog}})
    return schema


def glb_metadata(path):
    data = path.read_bytes()
    if len(data) < 20 or struct.unpack_from("<4sII", data) != (b"glTF", 2, len(data)):
        raise ValueError(f"Invalid GLB header: {path}")
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise ValueError(f"GLB first chunk is not JSON: {path}")
    doc = json.loads(data[20:20+length].decode("utf-8"))
    durations = {}
    for clip in doc.get("animations", []):
        durations[clip.get("name", "")] = max(
            float(doc["accessors"][sampler["input"]]["max"][0]) for sampler in clip["samplers"])
    return doc, durations, hashlib.sha256(data).hexdigest(), len(data)


def load_designs():
    path = ROOT/"tools"/"build_characters.py"
    spec = importlib.util.spec_from_file_location("catalog_character_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {int(design["id"]): design for design in module.DESIGNS}, module.COSTUME_SOURCES


def validate_catalog(catalog, schema, inventory, design_ids=None):
    # Always enforce cross-file relationships, even when jsonschema is absent.
    design_ids = set(APPEARANCE if design_ids is None else design_ids)
    if (len(catalog["models"]) != len(design_ids) or catalog["model_count"] != len(design_ids)
            or set(catalog["models"]) != set(inventory)):
        raise ValueError("Final feature keys and count must match all declared designs and timestamp inventory paths")
    if {record["id"] for record in catalog["models"].values()} != design_ids:
        raise ValueError("Catalog IDs must cover exactly the declared numbered designs")
    for key, record in catalog["models"].items():
        if key != record["glb"] or Path(key).name != record["filename"]:
            raise ValueError(f"Filename/path mismatch: {key}")
        if record["height"] is not None or record["rig"]["physical_height_inferred"]:
            raise ValueError(f"Physical height must not be inferred: {key}")
        if set(record["source_parts"]) != set(record["source_roles"].values()):
            raise ValueError(f"Donor role mismatch: {key}")
        if not set(record["source_parts"]).issubset(catalog["donors"]):
            raise ValueError(f"Donor provenance missing: {key}")
        if set(record["animations"]) != set(CLIPS):
            raise ValueError(f"Seven named clips are required: {key}")
        if record["outfit"]["legwear"] != APPEARANCE[record["id"]]["legs"]:
            raise ValueError(f"Legwear specification mismatch: {key}")
        if record["build_revision"] < 2:
            raise ValueError(f"Actual-costume revision >= 2 is required: {key}")
        if record["id"] <= 10 and set(record["native_source_clips"]) != {"Idle", "Walk", "Victory"}:
            raise ValueError(f"Three native clips are required for the original characters: {key}")
        if record["id"] >= 11 and record["native_source_clips"] != {}:
            raise ValueError(f"The new reference characters use seven authored clips rather than native motion: {key}")
    try:
        import jsonschema
    except ImportError:
        return "structural and cross-file checks (jsonschema is not installed)"
    validator = jsonschema.Draft202012Validator
    validator.check_schema(schema)
    validator(schema, format_checker=jsonschema.FormatChecker()).validate(catalog)
    return "JSON Schema Draft 2020-12 and cross-file checks"


def build(source):
    source = source.resolve()
    source_inventory = json.loads((source/SOURCE_FILES[0]).read_text(encoding="utf-8"))
    source_features = json.loads((source/SOURCE_FILES[1]).read_text(encoding="utf-8"))
    source_schema = json.loads((source/SOURCE_FILES[2]).read_text(encoding="utf-8"))
    manifest = json.loads((ROOT/"characters"/"manifest.json").read_text(encoding="utf-8"))
    designs, costume_sources = load_designs()
    if (len(manifest) != len(designs) or {int(entry["id"]) for entry in manifest} != set(designs)
            or any(entry.get("revision", 0) < 2 for entry in manifest)):
        raise ValueError("Catalog generation requires every declared actual-costume manifest entry (revision >= 2)")
    if not set(designs).issubset(APPEARANCE):
        raise ValueError("Every declared design needs final appearance metadata")
    inventory, models, donor_names = {}, {}, set()
    for entry in sorted(manifest, key=lambda item: int(item["id"])):
        number = int(entry["id"])
        config, appearance = designs[number], APPEARANCE[number]
        glb_path = ROOT/entry["glb"]
        doc, durations, sha256, size = glb_metadata(glb_path)
        roles = entry.get("source_roles")
        if roles is None:
            roles = {"costume_and_rig": costume_sources[number]+".glb", "hair": config["hair"]+".glb", "face": config["face"]+".glb"}
            if number == 3 and "Miyo.glb" in entry["source_parts"]:
                roles["back_hair"] = "Miyo.glb"
            if number in (3, 6):
                anatomy_donors = set(entry["source_parts"])-set(roles.values())
                if len(anatomy_donors) != 1:
                    raise ValueError(f"Character {number} must declare its one continuous bare-leg anatomy donor")
                roles["bare_legs_and_feet"] = anatomy_donors.pop()
        if entry.get("costume_source") != roles["costume_and_rig"]:
            raise ValueError(f"Manifest and builder wardrobe choices differ for character {number}")
        parts = list(dict.fromkeys(entry["source_parts"]))
        if set(parts) != set(roles.values()):
            raise ValueError(f"Manifest and builder donor choices differ for character {number}")
        extras = doc.get("extras", {})
        if (entry["bytes"] != size or entry["revision"] != extras.get("revision")
                or set(parts) != set(extras.get("source_parts", []))
                or entry["native_clips"] != extras.get("native_clips")
                or entry.get("sha256", sha256) != sha256):
            raise ValueError(f"Manifest and delivered GLB metadata differ for character {number}")
        donor_names.update(parts)
        inventory[entry["glb"]] = int(glb_path.stat().st_mtime)
        models[entry["glb"]] = {
            "id": number, "character": entry["name"], "name_ko": entry["name_ko"], "slug": entry["slug"],
            "filename": glb_path.name, "glb": entry["glb"], "sheet": entry["sheet"], "bytes": size, "sha256": sha256,
            "variants": [], "height": None,
            "body": {"build": None, "proportions": "SD", "description":
                     "원본 SD 머리 크기와 골격을 유지하고 몸통·허리·팔다리·의상 메시의 단면을 슬림하게 조정" if number == 5 else
                     "각 의상 원본의 SD 골격과 해부학 메시를 유지하며 머리 파츠를 턱·목에 맞춰 조합; 실제 체격이나 신장은 추정하지 않음"},
            "hair": {"colors": appearance["hair_colors"], "color_hex": config["hair_color"], "length": appearance["length"],
                     "styles": appearance["styles"], "description": appearance["hair"]},
            "outfit": {"styles": appearance["outfit_styles"], "colors": appearance["outfit_colors"],
                       "description": appearance["outfit"], "legwear": appearance["legs"], "footwear": appearance["feet"]},
            "features": appearance["features"],
            "tags": list(dict.fromkeys(["SD", *appearance["hair_colors"], *appearance["styles"],
                                         *appearance["outfit_styles"], *appearance["legs"]])),
            "palette": list(config["palette"]), "design_brief": config["design"], "weapon": appearance["weapon"],
            "animations": [clip["name"] for clip in doc.get("animations", [])], "animation_duration_seconds": durations,
            "native_source_clips": entry["native_clips"], "attack_motion": "custom skeletal animation",
            "attack_description": next((clip.get("extras", {}).get("description", "")
                                         for clip in doc["animations"] if clip["name"] == "Attack"), ""),
            "animation_playback": {name: "loop" if name in ("Idle", "Walk", "Run") else
                                   "once_hold" if name == "Lose" else "once" for name in CLIPS},
            "build_revision": entry["revision"], "head_fit": entry["head_fit"],
            "rig": {"name": doc["skins"][0].get("name", "Unified SD character rig"), "skin_count": len(doc["skins"]),
                    "joint_count": len(doc["skins"][0]["joints"]), "up_axis": "+Y", "front_axis": "+Z", "physical_height_inferred": False},
            "mesh_count": len(doc.get("meshes", [])), "triangle_count": entry["triangles"], "source_parts": parts, "source_roles": roles,
            "evidence": {"manifest": "characters/manifest.json", "builder": "tools/build_characters.py",
                         "character_sheet": entry["sheet"],
                         "appearance_method": "실제 원본 의상 파츠·선택적 텍스처 색상 편집·내보낸 GLB 메타데이터를 기준으로 최종 외형 기록; 시트는 해당 GLB를 렌더한 결과",
                         "height_method": "각 원본 SD 골격의 좌표를 실제 신장으로 환산하지 않음"},
            "review_notes": ["원본 캐릭터의 프로필 키와 체형 분류는 새 캐릭터에 전달하지 않음",
                             "의상의 실제 주름·프릴·레이스·골격을 유지하고 선택적 색상 편집을 적용",
                             ("Idle·Walk·Victory는 의상 원본 모션; Run·Attack·Defend·Lose는 캐릭터에 맞춰 별도 제작한 골격 모션. Lose는 마지막 패배 자세를 유지; 실시간 옷감 물리는 포함하지 않음"
                              if number <= 10 else
                              "일곱 모션 모두 성격과 소품에 맞춰 별도 제작한 골격 모션이며 native_source_clips는 비어 있음. 원본 골격과 의상 스킨을 유지. Lose는 마지막 패배 자세를 유지; 실시간 옷감 물리는 포함하지 않음")],
        }
        for clip_name, field in (("Walk", "walk_description"), ("Victory", "victory_description")):
            description = next((clip.get("extras", {}).get("description", "")
                                for clip in doc["animations"] if clip["name"] == clip_name), "")
            if number >= 11 and description:
                models[entry["glb"]][field] = description
    donors = {}
    for name in sorted(donor_names):
        if name not in source_inventory or name not in source_features["models"]:
            raise ValueError(f"Used donor is absent from the supplied source catalogs: {name}")
        record = source_features["models"][name]
        evidence = record["evidence"]
        donors[name] = {"character": record["character"], "source_timestamp": int(source_inventory[name]),
                        "original_hair": {key: record["hair"][key] for key in ("colors", "length", "styles", "description")},
                        "original_outfit": {key: record["outfit"][key] for key in ("styles", "colors", "description", "legwear", "footwear")},
                        "original_features": record["features"],
                        "source_confidence": {key: record["confidence"][key] for key in ("hair", "outfit", "features")},
                        "evidence": {"local_glb": name, "preview_front": evidence.get("preview_front"), "preview_back": evidence.get("preview_back")}}
    catalog = {
        "schema_version": "1.0", "analyzed_on": datetime.now(timezone(timedelta(hours=9))).date().isoformat(), "model_count": len(models),
        "classification_guide": {
            "appearance": "실제 원본 의상·머리·얼굴의 조합과 색상 편집 후 최종 외형을 기록; design_brief는 제작 목표이며 구체적 최종 파츠는 outfit·features에 기록",
            "height": "전체 캐릭터는 SD 비율. height는 null이며 실제 신장 수치를 제공하지 않음",
            "body": "의상 원본별 SD 골격과 메시를 사용하며 실제 인물의 체형 분류를 추정하지 않음",
            "legwear": "팬티스타킹·사이하이·맨다리를 개별 캐릭터별로 명시함",
            "provenance": "donors는 사용한 원본 항목만 간결하게 보존하고 최종 모델의 외형과 별도로 기록함",
            "animations": "Idle·Walk·Run은 제자리 반복. Run은 걷기 배속이 아닌 독립된 달리기. Attack·Defend·Victory는 1회 재생 후 복귀, Lose는 패배 자세를 유지. 원본 기반 모션과 캐릭터별 추가 골격 동작의 설명은 각 모션 description 및 GLB extras에 기록",
        },
        "source_catalog": {"root": str(source), "inspected_files": list(SOURCE_FILES),
                           "catalog_model_count": int(source_features["model_count"]), "timestamp_inventory_count": len(source_inventory),
                           "source_schema_title": source_schema.get("title", ""), "source_schema_uri": source_schema.get("$schema", ""),
                           "donor_height_policy": "원본의 실제 프로필 키는 최종 캐릭터에 복사하거나 추정하지 않음"},
        "donors": donors, "models": models,
    }
    schema = schema_document(designs)
    method = validate_catalog(catalog, schema, inventory, designs)
    for filename, value in (("models.json", inventory), ("model_features.json", catalog), ("model_features.schema.json", schema)):
        (ROOT/filename).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return len(models), len(donors), method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    count, donors, method = build(args.source)
    print(f"Cataloged {count} generated characters and {donors} donor entries; validated with {method}.")


if __name__ == "__main__":
    main()
