# Substance Painter MCP 확장 로드맵

기준 환경은 Painter 12.1.1입니다. 기능은 버전 숫자가 아니라 `get_capabilities` 결과로 활성화합니다.

## 설계 원칙

1. 읽기 도구와 변경 도구를 분리한다.
2. 레이어는 이름이 아니라 UID로 식별한다.
3. 파일 출력은 미리보기/검증 → 실행의 2단계로 나눈다.
4. 긴 작업은 Painter busy 상태, 진행률, 취소 가능성을 노출한다.
5. 테스트 산출물은 전용 폴더에 만들고 성공 여부와 파일 목록을 검증한다.
6. raw Python이 없어도 일반 작업이 가능하게 도메인 도구를 우선한다.

## P1 — 다음 자동 구현 대상

사람의 시각 판단 없이 샘플 프로젝트에서 생성·검증·정리할 수 있는 기능입니다.

### 구현 완료 (0.2.0)

- Fill/Paint/Group 생성과 UID 기반 이름·가시성·opacity·blend·선택·삭제
- 다중 uniform Fill 채널과 OpenPBR alias 정규화
- White/Black layer mask 추가·변경·제거
- 재귀 레이어 검색과 부모 경로
- 프로젝트 건강 검사
- export preset, project resource, resource query 조회
- runtime capability 탐지
- 허용 루트 기반 texture export plan/실행/파일 검증

### 레이어 구조 편집

- `move_layer(uid, position, reference_uid)`
  - `above`, `below`, `inside`, `top` 지원
  - 이동 전후 부모/순서 검증
- `create_layer_recipe(recipe)`
  - Group/Fill/Paint를 한 번에 만들되 전체 성공 전에는 rollback
- `set_active_channels(uid, channels)`
- Mask Content에 Fill/Generator/Filter effect 삽입

### 프로젝트 검사

- `snapshot_layer_tree`
  - 변경 전후 비교 가능한 JSON 스냅샷

### 리소스·프리셋

- `search_resources`의 type/usage 서버측 필터
- `inspect_export_preset(preset, texture_set)`
- `find_outdated_resources`와 명시적 교체 계획 생성

## P2 — 파일 출력 샌드박스가 필요한 기능

출력 위치 승인과 결과 파일 검증이 필요하지만 UI 조작은 필요 없습니다.

### 텍스처 내보내기

- 완료: `plan_texture_export`, `export_textures`, 충돌/허용 루트/생성 파일 크기 검증
- VRChat/Unity/Unreal/Blender용 export profile

### 프로젝트 저장과 백업

- `save_project_copy(path)`를 기본으로 제공
- 원본 덮어쓰기 `save_project`는 명시적 요청에서만 실행
- 레이어 recipe 적용 전 자동 백업 옵션

### Smart Material/Mask

- 그룹을 Smart Material/Mask 파일로 내보내기
- 파일 생성과 재검색 가능 여부 검증

## P3 — 긴 작업과 이벤트 브리지

Painter의 async API를 MCP progress/cancel과 연결해야 합니다.

### 베이크

- 선택 Texture Set의 baker/mesh map 상태 조회
- bake 설정 사전 검증
- `bake_selected_textures_async` 진행률 전달
- 12.1 Auto Rebake/Skew Map 관련 capability 조사
- 실패한 baker와 로그를 구조화해 반환

### 프로젝트 생성·메시 재로드

- 12.0.2+ `AutoUnwrapUVTilesSettings` 지원
- USD/glTF/FBX 옵션 schema
- mesh reload 후 Texture Set/레이어 영향 diff
- 변경 전 자동 백업

## P4 — 시각 QA 또는 사람 확인이 필요한 기능

이 단계에서만 사용자 호출이 필요할 수 있습니다.

- Generator/Filter/Smart Mask의 미적 결과 선택
- 베이크 아티팩트 품질 판단
- 색상/roughness 스타일 승인
- 카메라 프레이밍과 viewport 비교
- Blender ↔ Painter 왕복 결과의 메시/머티리얼 매칭 확인

가능하면 viewport 캡처와 A/B 결과를 먼저 만들어 한 번의 승인으로 끝냅니다.

## 추천 자동화 패키지

### VRChat Outfit Texture Recipe

1. Texture Set과 채널 검사
2. Base/Color Variation/Roughness/Detail 그룹 생성
3. 색상 팔레트 적용
4. AO/Curvature 기반 마스크 연결
5. Unity용 프리셋으로 내보내기
6. 생성 파일과 네이밍 규칙 검사

### Project Health Check

1. 프로젝트/Texture Set/리소스 스냅샷
2. outdated/missing 리소스 탐지
3. 중복/비표준 레이어명 리포트
4. export preset 호환성 검사
5. 수정 계획만 제시하거나 승인된 항목만 적용

### Blender Round-trip

1. Blender에서 mesh/material manifest 생성
2. Painter 프로젝트 생성 또는 mesh reload
3. Texture Set 매칭 검증
4. bake/export
5. Blender 노드 연결 및 파일 hash 검증

이 워크플로는 Painter MCP와 Blender 쪽 도구 사이의 공통 manifest schema가 먼저 필요합니다.
