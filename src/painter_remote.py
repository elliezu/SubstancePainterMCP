"""
Substance Painter Remote API 연결 모듈
HTTP를 통해 Painter와 통신
"""

import json
import base64
import http.client
from typing import Any, Optional


class PainterRemote:
    """Substance Painter Remote Scripting 연결 클래스"""
    
    def __init__(self, host: str = 'localhost', port: int = 60041):
        self.host = host
        self.port = port
        self.route = '/run.json'
        self.headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
    
    def check_connection(self) -> bool:
        """Painter 연결 상태 확인"""
        try:
            result = self.execute_js("alg.version.painter")
            return result is not None
        except Exception as e:
            print(f"연결 실패: {e}")
            return False
    
    def execute_python(self, code: str) -> Any:
        """Python 코드 실행"""
        return self._send_request(code, "python")
    
    def execute_js(self, code: str) -> Any:
        """JavaScript 코드 실행"""
        return self._send_request(code, "js")
    
    def _send_request(self, code: str, lang: str) -> Any:
        """HTTP POST 요청 전송"""
        try:
            connection = http.client.HTTPConnection(
                self.host, self.port, timeout=3600
            )
            
            # 코드를 base64로 인코딩
            encoded_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
            
            body = json.dumps({lang: encoded_code})
            
            connection.request('POST', self.route, body, self.headers)
            response = connection.getresponse()
            data = response.read()
            connection.close()
            
            # JSON 파싱
            result = json.loads(data.decode('utf-8'))
            
            # 에러 체크 (dict인 경우만)
            if isinstance(result, dict) and 'error' in result:
                raise ExecuteScriptError(result['error'])
            
            return result
                    
        except ConnectionRefusedError:
            raise ConnectionError(
                "Painter에 연결할 수 없습니다. "
                "--enable-remote-scripting 옵션으로 실행했는지 확인하세요."
            )
        except json.JSONDecodeError as e:
            # JSON 아닌 응답 (Python print 등)
            return data.decode('utf-8') if data else None
        except Exception as e:
            raise Exception(f"요청 실패: {e}")


class ExecuteScriptError(Exception):
    """스크립트 실행 오류"""
    pass


# 테스트용
if __name__ == "__main__":
    remote = PainterRemote()
    
    if remote.check_connection():
        print("✅ Painter 연결 성공!")
        
        # 버전 확인
        version = remote.execute_js("alg.version.painter")
        print(f"Painter 버전: {version}")
    else:
        print("❌ Painter 연결 실패")
