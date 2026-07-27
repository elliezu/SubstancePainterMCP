# Substance Painter MCP Server

Claude가 Substance Painter를 제어할 수 있게 해주는 MCP(Model Context Protocol) 서버입니다.

## 주요 기능

- 프로젝트 정보 조회 (텍스처셋 목록 등)
- 레이어 구조 확인
- Fill Layer, Group 생성
- Python 코드 직접 실행 (고급 기능)
- 여러 텍스처셋에 일괄 레이어 적용

## 요구사항

- **Substance Painter 2021.1+** (Remote Scripting 지원 버전)
- **Python 3.9+**
- **MCP 패키지**

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/elliezu/SubstancePainterMCP.git
cd SubstancePainterMCP
```

### 2. MCP 패키지 설치

```bash
pip install mcp
```

또는 전체 의존성 설치:

```bash
pip install -e .
```

### 3. Substance Painter 설정

Painter를 **Remote Scripting 활성화** 상태로 실행해야 합니다.

#### Windows:
```bash
"C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe" --enable-remote-scripting
```

#### 바로가기 만들기 (권장):
1. Substance Painter 바로가기 복사
2. 속성 → 대상에 `--enable-remote-scripting` 추가
3. 예: `"...\Adobe Substance 3D Painter.exe" --enable-remote-scripting`

### 4. Claude Desktop 설정

`%APPDATA%\Claude\claude_desktop_config.json` 파일에 추가:

```json
{
  "mcpServers": {
    "substance-painter": {
      "command": "python",
      "args": ["C:\\path\\to\\SubstancePainterMCP\\src\\server.py"],
      "cwd": "C:\\path\\to\\SubstancePainterMCP\\src"
    }
  }
}
```

> ⚠️ 경로를 본인 환경에 맞게 수정하세요!

### 5. Claude Desktop 재시작

설정 후 Claude Desktop을 완전히 종료했다가 다시 실행하세요.

## 사용법

### 기본 도구들

Claude에게 다음과 같이 요청할 수 있습니다:

- `"Painter 연결 확인해줘"` - 연결 상태 체크
- `"프로젝트 정보 알려줘"` - 텍스처셋 목록 등
- `"레이어 구조 보여줘"` - 전체 레이어 구조
- `"Fill Layer 만들어줘"` - 새 레이어 생성

### 고급 사용 (execute_python)

`execute_python` 도구로 Painter Python API를 직접 실행할 수 있습니다:

```python
# 예: 모든 텍스처셋에 Fill Layer 생성
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

for tex_set in ts.all_texture_sets():
    stack = tex_set.get_stack()
    pos = ls.InsertPosition.from_textureset_stack(stack)
    layer = ls.insert_fill(pos)
    layer.set_name("My_Layer")
```

### 실제 워크플로우 예시

```
"모든 텍스처셋에 Hair_Base 레이어 만들고 베이지색으로 설정해줘"

"Hair_Gradient 레이어에 Position Generator 마스크 추가해줘"

"LightSetup 레이어 Multiply 85%로 설정해줘"
```

## 파일 구조

```
SubstancePainterMCP/
├── src/
│   ├── server.py          # MCP 서버 메인
│   ├── painter_remote.py  # Painter HTTP 통신 모듈
│   └── test_project.py    # 테스트용 스크립트
├── pyproject.toml
└── README.md
```

## 문제 해결

### "연결 안됨" 오류

1. Painter가 `--enable-remote-scripting` 옵션으로 실행됐는지 확인
2. 포트 60041이 사용 가능한지 확인
3. 방화벽 설정 확인

### "MCP 모듈 없음" 오류

```bash
pip install mcp
```

### Claude에서 도구가 안 보임

1. `claude_desktop_config.json` 경로/문법 확인
2. Claude Desktop 완전 재시작 (트레이 아이콘까지 종료)

## 참고 자료

- [Substance Painter Python API](https://substance3d.adobe.com/documentation/ptpy)
- [Remote Scripting 문서](https://substance3d.adobe.com/documentation/ptpy/plugins/remote-scripting)
- [MCP Protocol](https://modelcontextprotocol.io/)

## 라이선스

MIT License
