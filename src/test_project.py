"""Fill Layer 생성 - 올바른 InsertPosition 사용"""
from painter_remote import PainterRemote

remote = PainterRemote()

print("=== Fill Layer 생성! ===")

py_code = """
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

active_stack = ts.get_active_stack()

# from_textureset_stack 사용해서 스택 최상단에 삽입
position = ls.InsertPosition.from_textureset_stack(active_stack)

# Fill Layer 생성
new_layer = ls.insert_fill(position)
new_layer.set_name("MCP_Test_Fill")

with open('C:/temp/sp_result.txt', 'w') as f:
    f.write(f"SUCCESS!\\n")
    f.write(f"Created: {new_layer.get_name()}\\n")
    f.write(f"UID: {new_layer.uid()}\\n")
    f.write(f"Type: {type(new_layer).__name__}\\n")
"""

try:
    remote.execute_python(py_code)
    with open('C:/temp/sp_result.txt', 'r') as f:
        print(f.read())
    print("✅ Painter 레이어 패널 확인해봐!")
except Exception as e:
    print(f"에러: {e}")
