import asyncio
import os
import time
from pathlib import Path
from datetime import datetime

# 尝试导入 playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("错误: 未安装 playwright 库。")
    print("请运行以下命令安装:")
    print("pip install playwright")
    print("playwright install chromium")
    exit(1)

# 配置
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = PROJECT_ROOT / "exports"

async def convert_html_to_pdf(html_path: Path, pdf_path: Path):
    """
    使用 Playwright 将 HTML 转换为 PDF
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # 使用 file:// 协议加载本地文件
        file_url = f"file://{html_path.absolute()}"
        
        print(f"正在加载: {html_path.name} ...")
        await page.goto(file_url, wait_until="networkidle")
        
        # 生成 PDF
        # format="A4" 是标准纸张大小
        # print_background=True 确保背景色和图片被打印
        print(f"正在生成 PDF: {pdf_path.name} ...")
        await page.pdf(path=str(pdf_path), format="A4", print_background=True, margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
        
        await browser.close()
        print(f"完成: {pdf_path}")

async def scan_and_convert():
    """
    扫描目录并转换新文件
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始扫描: {EXPORTS_DIR}")
    
    if not EXPORTS_DIR.exists():
        print(f"警告: 目录 {EXPORTS_DIR} 不存在。")
        return

    # 递归遍历所有 .html 文件
    for root, dirs, files in os.walk(EXPORTS_DIR):
        for file in files:
            if file.lower().endswith(".html"):
                html_path = Path(root) / file
                # PDF 路径：同名但后缀为 .pdf
                pdf_path = html_path.with_suffix(".pdf")
                
                # 如果 PDF 不存在，或者 HTML 比 PDF 新，则转换
                if not pdf_path.exists() or html_path.stat().st_mtime > pdf_path.stat().st_mtime:
                    try:
                        await convert_html_to_pdf(html_path, pdf_path)
                    except Exception as e:
                        print(f"转换失败 {file}: {e}")

async def main():
    print("=" * 50)
    print("HTML to PDF 自动转换工具")
    print("=" * 50)
    print(f"监控目录: {EXPORTS_DIR}")
    print("模式: 持续监控 (每 30 秒扫描一次)")
    print("按 Ctrl+C 停止")
    print("-" * 50)

    while True:
        try:
            await scan_and_convert()
            # 每 30 秒扫描一次
            await asyncio.sleep(30)
        except KeyboardInterrupt:
            print("\n停止监控。")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
