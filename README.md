# Original SD character collection

의상의 원래 주름, 프릴, 레이스, 봉제선과 텍스처를 유지하면서 색을 바꾸고 소품을 추가했습니다. 턱과 목의 표면을 맞춰 머리 간격을 줄였습니다. 원본의 **SD 비율**을 유지합니다.

각 캐릭터 폴더에 텍스처가 내장된 **GLB**, 실제 GLB에서 렌더한 **PNG 캐릭터 시트**가 있습니다. 시트에는 정면·3/4·측면·후면과 모션 포즈가 들어 있습니다. GLB는 Y-up, 정면 +Z이며 실제 신장으로 환산한 단위는 아닙니다.

| 번호 | 캐릭터 | 디자인 | 폴더 |
| --- | --- | --- | --- |
| 01 | 마린 / Marin | 분홍 트윈테일 메이드, 남색·흰색, 흰 팬티스타킹 | `characters/01_marine_maid` |
| 02 | 비올라 / Viola | 보라 머리, 큰 파란 장미, 낫, 파랑 사이하이 | `characters/02_azure_reaper` |
| 03 | 소라 / Sora | 하늘색 긴 레이어드 웨이브·작은 땋은 머리·파란 꽃, 회색 블레이저·검정 파이핑·빨강/검정 타탄 넥타이와 치마, 맨다리 | `characters/03_sky_cardigan` |
| 04 | 엘리제 / Elise | 금발 긴 생머리, 물결 원피스, 흰 팬티스타킹 | `characters/04_tidal_dress` |
| 05 | 리나 / Rina | 연분홍 한쪽 묶음, 슬림한 블레이저 교복, 맨다리 | `characters/05_rosy_blazer` |
| 06 | 페넬 / Fennel | 흰 짧은 머리, 날개 없는 요정, 호박팬츠, 맨발 | `characters/06_clover_sprite` |
| 07 | 모모 / Momo | 분홍 고양이 귀, 긴 레이어드 머리·양쪽 땋은 번, 배꼽을 드러낸 현대 의상, 검정 팬티스타킹 | `characters/07_neon_cat` |
| 08 | 로제트 / Rosette | 진분홍 롤 트윈테일, 빨강 인형 드레스, 흰 팬티스타킹 | `characters/08_carmine_doll` |
| 09 | 메이린 / Meilin | 풍성한 검갈색 트윈테일·빨강/금색 머리 장식, 옆트임 빨강 치파오, 맨다리 | `characters/09_crimson_qipao` |
| 10 | 네비아 / Nevia | 흰 긴 웨이브와 양쪽 번, 구름 의상, 흰 팬티스타킹 | `characters/10_snow_buns` |

`characters/manifest.json`에 파일 경로·색·디자인·원본 파츠가 기록되어 있습니다. 저장소 루트의 `models.json`, `model_features.json`, `model_features.schema.json`은 새 10명의 카탈로그입니다. 원본의 동일 이름 데이터와 렌더 자료로 파츠를 선정했습니다. 원본 폴더는 수정하지 않습니다.

소라는 추가로 전달한 머리·교복 참고 이미지에 맞춰 변경했습니다. Azusa (Swimsuit)의 뾰족한 중앙 앞머리와 얼굴 옆 머리, Miyo의 묶이지 않은 긴 웨이브, Serika의 실제 라펠·주머니·주름치마를 조합했습니다. 기존 폴더 이름 `03_sky_cardigan`은 파일 경로 호환을 위해 유지했습니다.

앞으로의 수정도 원본 `BlueArchiveGLB`의 `models.json`, `model_features.json`, `model_features.schema.json`에서 의상·얼굴·머리·골격 파츠를 선정한 뒤 조합·색상 편집·필요한 비율 수정을 적용합니다. 새 파츠와 변형은 생성 코드 및 GLB/manifest의 출처 기록에 반영하고, 최종 GLB를 기준으로 저장소 카탈로그와 미리보기를 다시 생성합니다.

Momo는 Miyo의 앞머리·얼굴·원본 미소 입, Kirara의 긴 웨이브·양쪽 번, Kazusa의 고양이 귀를 조합하고 눈을 연보라색으로 편집했습니다. Meilin은 Serika (Swimsuit)의 트윈테일 단면을 넓히고 실제 묶음 위치에 붉은 꽃리본·금색 줄과 펜던트를 추가했습니다. Rina는 머리 크기와 관절 위치를 유지하며 몸통 폭을 20%, 몸통 두께를 14%, 팔다리 단면을 17–18% 줄였습니다. `previews/appearance_changes.png`에서 세 캐릭터의 전후 모습을 비교할 수 있습니다.

## 미리보기

`previews/lineup.png`는 전체 캐릭터 연락판입니다. `previews/motion_grid.gif`와 7종 모션별 포즈 연락판도 제공됩니다. `previews/run_grid.gif`는 10명의 달리기만 연속 반복해서 보여 줍니다.

로컬 3D 뷰어는 저장소 루트에서 아래 명령을 실행한 뒤 `http://localhost:8000/viewer/`를 열면 됩니다. GLB 선택, 회전·확대 및 애니메이션 재생을 지원하며 외부 네트워크 없이 동작합니다.

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

## 애니메이션

각 GLB에 `Idle`, `Walk`, `Run`, `Attack`, `Defend`, `Victory`, `Lose`가 포함됩니다. 대기·걷기·승리는 원본 의상 골격의 모션을 활용해 옷자락과 몸의 움직임을 함께 유지합니다. 대기·걷기·달리기는 제자리 반복입니다. 달리기는 별도의 보폭, 무릎 굽힘, 공중 구간과 상체 기울기를 사용합니다. 팔꿈치는 몸 옆에서 약 90도로 굽히고 실제 무릎 움직임과 반대로 앞뒤로 흔듭니다. 손은 안쪽을 향해 자연스럽게 쥐며, 소품은 운반 자세로 유지합니다. 공격·방어는 캐릭터의 소품과 성격에 맞춘 별도 모션이며, 비올라는 낫의 안쪽 날이 진행 방향을 향하는 베기 동작을 사용합니다. 패배는 마지막 자세를 유지합니다. 뷰어에서 공격·방어·승리·패배는 1회 재생하고, 모션 버튼을 다시 누르면 재생을 시작합니다. 머리·의상·소품은 골격을 따라 움직이며, 실시간 옷감·머리카락 물리 시뮬레이션은 포함하지 않습니다.

| 캐릭터 | 공격 동작 |
| --- | --- |
| Marin | 레이피어를 겨누고 한 발 내딛는 펜싱 찌르기 |
| Viola | 양손으로 낫을 들어 안쪽 날로 내려 베기 |
| Sora | 옆으로 큰 물결을 그리고 손바닥으로 방출 |
| Elise | 머리 위로 둥근 소환 궤적을 그리는 물결 동작 |
| Rina | 짧고 정확한 두 차례 참 방출 |
| Fennel | 클로버 지팡이를 나선으로 올린 뒤 씨앗을 튕기는 동작 |
| Momo | 앞손 고양이 잽에 이은 뒷손 크로스 |
| Rosette | 좌우로 각진 태엽 인형 타격과 고개 움직임 |
| Meilin | 몸 앞을 가로지르는 부채 베기와 손목 회전 |
| Nevia | 양손으로 눈 결정을 모아 들어 올리고 방출 |

위 설명은 골격 동작을 뜻하며 별도의 투사체·마법 VFX는 포함하지 않습니다. `model_features.json`에는 최종 공격 설명과 모션별 반복/1회 재생 방식도 기록합니다.

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

의상·머리·얼굴·해부학 메시, 기존 골격과 원본 모션의 원저작권은 해당 권리자에게 남아 있습니다. 저장소 코드의 기존 LICENSE가 원본 게임 아트의 권리를 새로 부여하지 않습니다. 파츠 조합·색상 편집·추가 소품·공격 모션의 제작 내역은 각 GLB의 `extras`와 manifest에 기록합니다.

뷰어의 Three.js는 MIT, Khronos glTF Validator는 Apache-2.0이며 각 vendor 폴더에 라이선스를 함께 보관합니다.
