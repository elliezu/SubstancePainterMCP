"""
Substance Painter MCP Server
Claude가 Painter를 제어할 수 있게 해주는 MCP 서버
"""

import json
import asyncio
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from painter_remote import PainterRemote


# MCP 서버 인스턴스
app = Server("substance-painter-mcp")

# Painter 연결
painter = PainterRemote()


def run_python(code: str) -> str:
    """Python 코드 실행하고 결과 파일에서 읽기"""
    # 결과를 파일로 저장하는 코드 래핑
    wrapped_code = f"""
import json
try:
{chr(10).join('    ' + line for line in code.split(chr(10)))}
    _result = {{"success": True, "data": result if 'result' in dir() else None}}
except Exception as e:
    _result = {{"success": False, "error": str(e)}}

with open('C:/temp/sp_mcp_result.json', 'w', encoding='utf-8') as f:
    json.dump(_result, f, ensure_ascii=False, default=str)
"""
    painter.execute_python(wrapped_code)
    
    with open('C:/temp/sp_mcp_result.json', 'r', encoding='utf-8') as f:
        return json.load(f)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="check_connection",
            description="Substance Painter 연결 상태 확인",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_project_info",
            description="현재 열린 프로젝트 정보 (이름, 경로, 텍스처셋 목록)",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_layer_structure",
            description="모든 텍스처셋의 레이어 구조 가져오기",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_active_layers",
            description="현재 활성 텍스처셋의 레이어 목록",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="create_fill_layer",
            description="Fill Layer 생성",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "레이어 이름"
                    },
                    "texture_set": {
                        "type": "string",
                        "description": "텍스처셋 이름 (없으면 현재 활성 텍스처셋)"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="create_group",
            description="레이어 그룹 생성",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "그룹 이름"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="set_layer_color",
            description="Fill Layer의 Base Color 설정",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "레이어 이름"
                    },
                    "color": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "RGB 색상 [R, G, B] (0-1 범위)"
                    }
                },
                "required": ["layer_name", "color"]
            }
        ),
        Tool(
            name="execute_python",
            description="Painter에서 Python 코드 직접 실행 (고급)",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "실행할 Python 코드"
                    }
                },
                "required": ["code"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """도구 실행"""
    
    try:
        if name == "check_connection":
            connected = painter.check_connection()
            if connected:
                version = painter.execute_js("alg.version.painter")
                return [TextContent(type="text", text=f"✅ 연결됨 - Painter {version}")]
            else:
                return [TextContent(type="text", text="❌ 연결 안됨")]
        
        elif name == "get_project_info":
            is_open = painter.execute_js("alg.project.isOpen()")
            if not is_open:
                return [TextContent(type="text", text="프로젝트가 열려있지 않습니다")]
            
            name = painter.execute_js("alg.project.name()")
            url = painter.execute_js("alg.project.url()")
            
            # 텍스처셋 목록
            code = """
import substance_painter.textureset as ts
result = [t.name() for t in ts.all_texture_sets()]
"""
            res = run_python(code)
            texture_sets = res.get('data', []) if res.get('success') else []
            
            info = {
                "name": name,
                "path": url,
                "texture_sets": texture_sets
            }
            return [TextContent(type="text", text=json.dumps(info, indent=2, ensure_ascii=False))]
        
        elif name == "get_layer_structure":
            structure = painter.execute_js("JSON.stringify(alg.mapexport.documentStructure(), null, 2)")
            return [TextContent(type="text", text=structure)]
        
        elif name == "get_active_layers":
            code = """
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

active_stack = ts.get_active_stack()
root_nodes = ls.get_root_layer_nodes(active_stack)

result = {
    "texture_set": active_stack.name(),
    "layers": []
}
for node in root_nodes:
    result["layers"].append({
        "name": node.get_name(),
        "type": type(node).__name__,
        "uid": node.uid()
    })
"""
            res = run_python(code)
            if res.get('success'):
                return [TextContent(type="text", text=json.dumps(res['data'], indent=2, ensure_ascii=False))]
            else:
                return [TextContent(type="text", text=f"에러: {res.get('error')}")]
        
        elif name == "create_fill_layer":
            layer_name = arguments.get("name", "New Fill Layer")
            texture_set = arguments.get("texture_set")
            
            code = f"""
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

{"stack = ts.TextureSet.from_name('" + texture_set + "').get_stack()" if texture_set else "stack = ts.get_active_stack()"}

position = ls.InsertPosition.from_textureset_stack(stack)
new_layer = ls.insert_fill(position)
new_layer.set_name("{layer_name}")

result = {{
    "name": new_layer.get_name(),
    "uid": new_layer.uid(),
    "type": type(new_layer).__name__
}}
"""
            res = run_python(code)
            if res.get('success'):
                return [TextContent(type="text", text=f"✅ 생성됨: {json.dumps(res['data'], ensure_ascii=False)}")]
            else:
                return [TextContent(type="text", text=f"❌ 에러: {res.get('error')}")]
        
        elif name == "create_group":
            group_name = arguments.get("name", "New Group")
            
            code = f"""
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

stack = ts.get_active_stack()
position = ls.InsertPosition.from_textureset_stack(stack)
new_group = ls.insert_group(position)
new_group.set_name("{group_name}")

result = {{
    "name": new_group.get_name(),
    "uid": new_group.uid()
}}
"""
            res = run_python(code)
            if res.get('success'):
                return [TextContent(type="text", text=f"✅ 그룹 생성됨: {json.dumps(res['data'], ensure_ascii=False)}")]
            else:
                return [TextContent(type="text", text=f"❌ 에러: {res.get('error')}")]
        
        elif name == "set_layer_color":
            layer_name = arguments.get("layer_name")
            color = arguments.get("color", [1, 1, 1])
            
            code = f"""
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

stack = ts.get_active_stack()
root_nodes = ls.get_root_layer_nodes(stack)

target = None
for node in root_nodes:
    if node.get_name() == "{layer_name}":
        target = node
        break

if target and hasattr(target, 'set_source'):
    # Fill Layer의 색상 설정
    # TODO: 실제 색상 설정 API 확인 필요
    result = {{"status": "found", "name": target.get_name()}}
else:
    result = {{"status": "not_found", "searched": "{layer_name}"}}
"""
            res = run_python(code)
            return [TextContent(type="text", text=json.dumps(res, ensure_ascii=False))]
        
        elif name == "execute_python":
            code = arguments.get("code", "")
            code_with_result = code + "\nresult = locals().get('result', 'executed')"
            res = run_python(code_with_result)
            return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]
        
        else:
            return [TextContent(type="text", text=f"알 수 없는 도구: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"에러: {str(e)}")]


async def main():
    """MCP 서버 시작"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
