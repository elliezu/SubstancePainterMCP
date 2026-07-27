# Changelog

## 0.2.0 - 2026-07-28

- Painter 12.1.1 라이브 검증
- MCP Python SDK 1.28 FastMCP 기반으로 전환
- 설치 가능한 표준 `src` 패키지와 정상 동작하는 console entry point 추가
- timeout과 연결/HTTP/스크립트 오류 타입 추가
- 고정 `C:\temp` 결과 파일 제거
- base64 JSON 파라미터 전달로 문자열 삽입 취약점 제거
- UID 기반 재귀 레이어 조회와 Fill/Paint/Group 생성 추가
- Fill Base Color, 이름, 가시성, opacity, blend mode, 선택, 삭제 추가
- OpenPBR/버전별 runtime capability 탐지 추가
- export preset과 project resource 조회 추가
- 프로젝트 감사, 재귀 레이어 검색, 리소스 검색 추가
- Roughness/Metallic 등 다중 Fill 채널과 OpenPBR alias 대응
- White/Black layer mask 추가·변경·제거
- 허용 루트와 overwrite 게이트를 적용한 texture export plan/실행 추가
- export 결과 파일 존재와 크기 검증 추가
- raw Python 실행을 opt-in으로 변경
- 단위 테스트와 Painter 생성-검증-삭제 라이브 테스트 추가
