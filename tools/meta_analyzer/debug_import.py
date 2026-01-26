import sys
import os
import traceback

# 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.dirname(os.path.dirname(current_dir))
backend_dir = os.path.join(tools_dir, "backend")

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

print(f"Added to sys.path: {backend_dir}")

try:
    import app
    print("Successfully imported app package")
    import app.core.config
    print("Successfully imported app.core.config")
except Exception as e:
    print("Import failed:")
    traceback.print_exc()
