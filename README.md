# Substance Painter MCP

MCP 클라이언트가 로컬 Adobe Substance 3D Painter를 조회하고 레이어를 편집할 수 있게 해주는 서버입니다.

## 현재 상태

- 버전: **0.2.0**
- 라이브 검증: **Substance 3D Painter 12.1.1 / Python API 0.3.5**
- MCP SDK: 안정판 **1.x** (`mcp>=1.28,<2`)
- 전송: MCP stdio → Painter HTTP remote scripting (`localhost:60041`)
- 지원 Python: 3.10+

Painter가 보고하는 Python API 버전과 실제 capability가 어긋날 수 있어서, 버전 문자열 대신
`get_capabilities`로 런타임 기능을 탐지합니다.

## 도구

### 조회

- `painter_status`: 연결, Painter/API 버전, 프로젝트 상태
- `get_project_info`: 프로젝트 경로와 Texture Set
- `get_capabilities`: 채널, 블렌딩 모드, 버전별 기능
- `audit_project`: 해상도/채널/레이어 위생/outdated resource 감사
- `list_layers`: UID 기반 재귀 레이어 트리
- `find_layers`: 이름/타입/가시성 기반 검색과 부모 경로
- `list_export_presets`: 내장/선반 내보내기 프리셋
- `plan_texture_export`: 파일을 쓰기 전 정확한 출력 목록/충돌 검증
- `export_textures`: 허용 루트 안에 내보내고 생성 파일/크기 검증
- `list_project_resources`: 프로젝트가 참조하는 리소스
- `search_resources`: 리소스 타입/usage/URL 검색

### 편집

- `create_fill_layer`, `create_paint_layer`, `create_group`
- `set_fill_base_color`: sRGB 입력을 Painter 작업 색공간으로 변환
- `set_fill_channels`: Roughness/Metallic/Emission 등 다중 uniform 채널
- `set_layer_mask`: White/Black 마스크 추가·변경·제거
- `set_layer_properties`: 가시성, 채널별 opacity/blend mode
- `rename_layer`, `select_layers`, `delete_layer`

레이어 이름은 중복될 수 있으므로 편집 도구는 `list_layers`가 반환한 UID를 사용합니다.

### 고급

- `execute_python`: 임의 Painter Python 실행. 기본 비활성화이며 명시적으로
  `SP_MCP_ALLOW_EXECUTE_PYTHON=1`을 설정해야 합니다.

## 설치

```powershell
git clone https://github.com/elliezu/SubstancePainterMCP.git
cd SubstancePainterMCP
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

개발/테스트 의존성까지 설치하려면:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest
```

## Painter 실행

Painter는 반드시 새 프로세스로 다음 옵션과 함께 실행해야 합니다.

```powershell
"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe" --enable-remote-scripting
```

바로가기의 **대상** 예시:

```text
"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe" --enable-remote-scripting
```

이미 옵션 없이 실행된 Painter가 있으면 바로가기를 눌러도 기존 창만 활성화될 수 있습니다.
Painter를 완전히 종료한 다음 이 바로가기로 다시 실행하세요. 포트는 별도 설정 없이 자동으로
`localhost:60041`에 열립니다.

확인 명령:

```powershell
Get-NetTCPConnection -LocalPort 60041
```

## MCP 클라이언트 설정

Claude Desktop 예시:

```json
{
  "mcpServers": {
    "substance-painter": {
      "command": "E:\\SubstanceMCP\\SubstacePainterMCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "substance_painter_mcp"],
      "env": {
        "SP_MCP_TIMEOUT": "120",
        "SP_MCP_EXPORT_ROOTS": "E:\\SubstanceExports"
      }
    }
  }
}
```

경로는 실제 설치 위치에 맞게 바꾸세요. 설치 후 생성되는
`.venv\Scripts\substance-painter-mcp.exe`를 `command`로 직접 지정해도 됩니다.

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---:|---|
| `SP_MCP_HOST` | `localhost` | Painter remote host |
| `SP_MCP_PORT` | `60041` | Painter remote port |
| `SP_MCP_TIMEOUT` | `30` | HTTP timeout(초) |
| `SP_MCP_ALLOW_EXECUTE_PYTHON` | 미설정 | `1`일 때만 raw Python 허용 |
| `SP_MCP_EXPORT_ROOTS` | 미설정 | 내보내기를 허용할 루트. Windows에서는 `;`로 복수 지정 |

`plan_texture_export`는 파일을 만들지 않고 정확한 출력 목록과 기존 파일 충돌을 반환합니다.
`export_textures`는 plan을 다시 검증하며, 기존 파일이 있으면 `overwrite=true` 없이는 중단합니다.

## 안전 설계

- 이름·색상·UID 등은 Python 코드 문자열에 직접 삽입하지 않고 base64 JSON으로 전달합니다.
- 고정 `C:\temp` 결과 파일을 사용하지 않아 동시 요청과 오래된 결과 충돌을 피합니다.
- 연결 실패 시 1시간 대기하지 않고 설정된 짧은 timeout으로 종료합니다.
- 원격 오류는 연결/HTTP/스크립트 오류로 구분합니다.
- raw Python은 opt-in입니다.

## 테스트

```powershell
.venv\Scripts\python.exe -m pytest
```

현재 자동 테스트는 연결 인코딩, 오류 타입, timeout 실패, 입력 격리, 색상/opacity 검증을 다룹니다.
Painter 라이브 테스트에서는 조회 → 생성 → 색상/속성/선택 → 삭제 왕복을 사용합니다.

```powershell
# 읽기 전용
.venv\Scripts\python.exe scripts\live_smoke.py

# 임시 레이어 생성 후 항상 정리하는 변경 왕복
.venv\Scripts\python.exe scripts\live_smoke.py --write
```

## 다음 기능

구현 순서와 안전 게이트는 [docs/ROADMAP.md](docs/ROADMAP.md)에 정리되어 있습니다.

## 라이선스

MIT
