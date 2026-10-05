# Original SD character collection

요청한 10개 디자인을 `C:\Codex\BlueArchiveGLB`의 실제 의상·헤어·얼굴·골격 파츠로 조합했습니다. 의상의 원래 주름, 프릴, 레이스, 봉제선과 텍스처를 유지하면서 색을 바꾸고 소품을 추가했습니다. 턱과 목의 표면을 맞춰 머리 간격을 줄였습니다. 원본의 **SD 비율**을 유지합니다.

각 캐릭터 폴더에 텍스처가 내장된 **GLB**, 실제 GLB에서 렌더한 **PNG 캐릭터 시트**가 있습니다. 시트에는 정면·3/4·측면·후면과 모션 포즈가 들어 있습니다. GLB는 Y-up, 정면 +Z이며 실제 신장으로 환산한 단위는 아닙니다.

| 번호 | 캐릭터 | 디자인 | 폴더 |
| --- | --- | --- | --- |
| 01 | 마린 / Marin | 분홍 트윈테일 메이드, 남색·흰색, 흰 팬티스타킹 | `characters/01_marine_maid` |
| 02 | 비올라 / Viola | 보라 머리, 큰 파란 장미, 낫, 파랑 사이하이 | `characters/02_azure_reaper` |
| 03 | 소라 / Sora | 하늘색 긴 레이어드 웨이브·작은 땋은 머리·파란 꽃, 회색 블레이저·검정 파이핑·빨강/검정 타탄 넥타이와 치마, 맨다리 | `characters/03_sky_cardigan` |
| 04 | 엘리제 / Elise | 금발 긴 생머리, 물결 원피스, 흰 팬티스타킹 | `characters/04_tidal_dress` |
| 05 | 리나 / Rina | 연분홍 한쪽 묶음, 블레이저 교복, 맨다리 | `characters/05_rosy_blazer` |
| 06 | 페넬 / Fennel | 흰 짧은 머리, 날개 없는 요정, 호박팬츠, 맨발 | `characters/06_clover_sprite` |
| 07 | 모모 / Momo | 분홍 고양이 귀, 배꼽을 드러낸 현대 의상, 검정 팬티스타킹 | `characters/07_neon_cat` |
| 08 | 로제트 / Rosette | 진분홍 롤 트윈테일, 빨강 인형 드레스, 흰 팬티스타킹 | `characters/08_carmine_doll` |
| 09 | 메이린 / Meilin | 검갈색 트윈테일, 옆트임 빨강 치파오, 맨다리 | `characters/09_crimson_qipao` |
| 10 | 네비아 / Nevia | 흰 긴 웨이브와 양쪽 번, 구름 의상, 흰 팬티스타킹 | `characters/10_snow_buns` |

`characters/manifest.json`에 파일 경로·색·디자인·원본 파츠가 기록되어 있습니다. 저장소 루트의 `models.json`, `model_features.json`, `model_features.schema.json`은 새 10명의 카탈로그입니다. 원본의 동일 이름 데이터와 렌더 자료로 파츠를 선정했습니다. 원본 폴더는 수정하지 않습니다.

소라는 추가로 전달한 머리·교복 참고 이미지에 맞춰 변경했습니다. Azusa (Swimsuit)의 뾰족한 중앙 앞머리와 얼굴 옆 머리, Miyo의 묶이지 않은 긴 웨이브, Serika의 실제 라펠·주머니·주름치마를 조합했습니다. 기존 폴더 이름 `03_sky_cardigan`은 파일 경로 호환을 위해 유지했습니다.

## 미리보기

`previews/lineup.png`는 전체 캐릭터 연락판입니다. `previews/motion_grid.gif`와 걷기·공격·승리 포즈 연락판도 제공됩니다.

로컬 3D 뷰어는 저장소 루트에서 아래 명령을 실행한 뒤 `http://localhost:8000/viewer/`를 열면 됩니다. GLB 선택, 회전·확대 및 애니메이션 재생을 지원하며 외부 네트워크 없이 동작합니다.

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

## 애니메이션

각 GLB에 `Idle`, `Walk`, `Attack`, `Victory`가 포함됩니다. 대기·걷기·승리는 원본 의상 골격의 모션을 활용해 옷자락과 몸의 움직임을 함께 유지합니다. 걷기는 제자리 반복입니다. 공격은 소품을 쥔 손목과 팔, 몸통, 발을 맞춰 만든 별도 모션입니다. 머리·의상·소품은 골격을 따라 움직이며, 실시간 옷감·머리카락 물리 시뮬레이션은 포함하지 않습니다.

## 재생성 및 검사

```powershell
python -m pip install -r requirements.txt
python tools/build_characters.py --source C:\Codex\BlueArchiveGLB
python tools/build_catalog.py --source C:\Codex\BlueArchiveGLB
python tools/render_characters.py --root .
python tools/validate_characters.py --root .
node tools/validate_gltf.cjs
```

제작 스크립트만 원본 파츠 폴더가 필요합니다. 제공된 GLB·시트·뷰어·검사 도구는 그 폴더 없이 사용 가능합니다. `previews/gltf_validation.json`에는 Khronos 검증 결과, `previews/validation.json`에는 파일·스킨·애니메이션·시트 검사 결과가 저장됩니다.

## 출처

의상·머리·얼굴·해부학 메시, 기존 골격과 원본 모션의 출처는 제공된 Blue Archive GLB입니다. 이 파일들의 원저작권은 해당 권리자에게 남아 있습니다. 저장소 코드의 기존 LICENSE가 원본 게임 아트의 권리를 새로 부여하지 않습니다. 파츠 조합·색상 편집·추가 소품·공격 모션의 제작 내역은 각 GLB의 `extras`와 manifest에 기록합니다.

뷰어의 Three.js는 MIT, Khronos glTF Validator는 Apache-2.0이며 각 vendor 폴더에 라이선스를 함께 보관합니다.
