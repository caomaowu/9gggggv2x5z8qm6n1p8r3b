import subprocess
import sys
import os
import threading
import time
import shlex
from pathlib import Path
from dotenv import load_dotenv

# 全局进程列表，用于退出时清理
processes = []

def run_service(command_str, cwd, prefix, color_code, env_vars=None):
    """
    运行服务并实时打印输出到当前终端
    """
    print(f"🚀 正在启动 {prefix}...")
    
    # Windows 下通常需要 shell=True 来解析 npm 等命令
    is_windows = sys.platform == "win32"
    
    if is_windows:
        use_shell = True
        cmd_args = command_str
    else:
        # Linux/Mac 下使用 shell=False 并拆分参数，以便能正确获取 PID 进行关闭
        use_shell = False
        cmd_args = shlex.split(command_str)

    # 环境变量，强制 Python 不缓存输出，保证日志实时性
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # 启动进程
        process = subprocess.Popen(
            cmd_args,
            cwd=str(cwd),
            shell=use_shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 将错误输出合并到标准输出
            bufsize=1, # 行缓冲
            text=True, # 文本模式处理流
            encoding='utf-8', # 强制使用 utf-8
            errors='replace', # 忽略编码错误
            env=env
        )
        
        processes.append(process)
        
        # 简单的 ANSI 颜色封装
        def colored(text):
            return f"\033[{color_code}m{text}\033[0m"

        # 实时读取输出
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                # 打印格式：[服务名] | 日志内容
                print(f"{colored(prefix)} | {line.rstrip()}")
                
        print(f"🛑 {prefix} 已停止 (代码: {process.returncode})")
        
    except Exception as e:
        print(f"❌ {prefix} 启动出错: {e}")

def kill_all_processes():
    """清理所有子进程"""
    print("\n正在停止所有服务...")
    for p in processes:
        if p.poll() is None: # 如果进程还在运行
            try:
                if sys.platform == "win32":
                    # Windows: 使用 taskkill 强制杀死进程树 (/T)
                    # 仅 terminate() 在 Windows 下可能杀不掉 shell=True 启动的子进程
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                else:
                    # Linux/Mac
                    p.terminate()
            except Exception as e:
                print(f"关闭进程失败: {e}")

def main():
    # 启用 Windows 终端颜色支持
    os.system('') 
    
    project_root = Path(__file__).resolve().parent
    print("="*60)
    print(f" 🚀 QuantAgent 集成启动脚本 (VS Code 模式)")
    print(f" 📂 根目录: {project_root}")
    print(f" ⌨️  请在下方终端查看日志。按 Ctrl+C 停止所有服务。")
    print("="*60)

    # 定义要启动的服务
    services = [
        # 后端 (Cyan - 青色)
        {
            "name": "[Backend ]", 
            "cmd": "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
            "cwd": project_root / "backend",
            "color": "36" 
        },
        # 前端 (Green - 绿色)
        {
            "name": "[Frontend]", 
            "cmd": "npm run dev",
            "cwd": project_root / "frontend",
            "color": "32" 
        },
        # PDF 工具 (Yellow - 黄色)
        # {
        #     "name": "[PDF-Tool]", 
        #     "cmd": "python tools/auto_pdf.py",
        #     "cwd": project_root,
        #     "color": "33" 
        # }
    ]

    # 使用线程并发启动所有服务
    threads = []
    
    # 预先加载 backend/.env 到一个字典中
    backend_env_path = project_root / "backend" / ".env"
    backend_env_vars = {}
    if backend_env_path.exists():
        print(f"Loading env from {backend_env_path}")
        # 使用 python-dotenv 解析，但不污染当前进程的 os.environ
        from dotenv import dotenv_values
        backend_env_vars = dotenv_values(backend_env_path)
        # 过滤掉 None 值
        backend_env_vars = {k: v for k, v in backend_env_vars.items() if v is not None}
        print(f"Loaded {len(backend_env_vars)} env vars for backend service")

    for svc in services:
        # 仅为 Backend 服务注入特定的环境变量
        env_to_pass = backend_env_vars if svc["name"] == "[Backend ]" else None
        
        t = threading.Thread(
            target=run_service,
            args=(svc["cmd"], svc["cwd"], svc["name"], svc["color"], env_to_pass),
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(0.5) # 稍微错开启动时间，避免日志瞬间刷屏太乱

    # 主线程循环，等待 Ctrl+C
    try:
        while True:
            time.sleep(1)
            # 如果所有服务都挂了，脚本也自动退出
            if processes and all(p.poll() is not None for p in processes):
                print("所有服务已退出。")
                break
    except KeyboardInterrupt:
        print("\n\n⚠️  接收到停止指令 (Ctrl+C)")
    finally:
        kill_all_processes()
        print("👋 Bye!")

if __name__ == "__main__":
    main()
