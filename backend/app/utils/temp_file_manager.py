import os
import time
import glob
import shutil

def cleanup_old_temp_files(temp_dir="temp_charts", max_age_hours=24):
    """清理超过指定时间的临时文件"""
    try:
        if not os.path.exists(temp_dir):
            return
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        # 获取所有临时文件
        pattern_files = glob.glob(os.path.join(temp_dir, "pattern_*.txt"))
        trend_files = glob.glob(os.path.join(temp_dir, "trend_*.txt"))
        result_files = glob.glob(os.path.join("temp_results", "*.json"))
        
        all_files = pattern_files + trend_files + result_files
        
        for file_path in all_files:
            try:
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    print(f"清理过期临时文件: {file_path}")
            except OSError as e:
                print(f"删除临时文件失败 {file_path}: {e}")
                
    except Exception as e:
        print(f"清理临时文件时出错: {e}")

def cleanup_on_startup():
    """应用启动时清理所有临时文件"""
    try:
        temp_dir = "temp_charts"
        if os.path.exists(temp_dir):
            pattern_files = glob.glob(os.path.join(temp_dir, "pattern_*.txt"))
            trend_files = glob.glob(os.path.join(temp_dir, "trend_*.txt"))
            result_files = glob.glob(os.path.join("temp_results", "*.json"))

            all_files = pattern_files + trend_files + result_files
            
            for file_path in all_files:
                try:
                    os.remove(file_path)
                    print(f"启动清理临时文件: {file_path}")
                except OSError as e:
                    print(f"删除临时文件失败 {file_path}: {e}")
                    
    except Exception as e:
        print(f"启动清理临时文件时出错: {e}")

def cleanup_all_temp_files():
    """强制清理所有临时文件（API调用）"""
    try:
        temp_dir = "temp_charts"
        cleaned_count = 0
        
        if os.path.exists(temp_dir):
            # 扩展清理范围，包含图片和CSV
            files_to_clean = []
            files_to_clean.extend(glob.glob(os.path.join(temp_dir, "*.png")))
            files_to_clean.extend(glob.glob(os.path.join(temp_dir, "*.csv")))
            files_to_clean.extend(glob.glob(os.path.join(temp_dir, "*.txt")))
            files_to_clean.extend(glob.glob(os.path.join("temp_results", "*.json")))
            
            for file_path in files_to_clean:
                try:
                    os.remove(file_path)
                    cleaned_count += 1
                    print(f"手动清理临时文件: {file_path}")
                except OSError as e:
                    print(f"删除临时文件失败 {file_path}: {e}")
                    
        return cleaned_count
    except Exception as e:
        print(f"手动清理临时文件时出错: {e}")
        return 0

def cleanup_exports_files():
    """
    清理 exports 文件夹下的所有内容
    """
    try:
        # 定位到 exports 文件夹 (假设后端运行在 backend/ 目录)
        # 向上两级找到项目根目录 (app -> backend -> root) ? 不，是运行目录 backend/ 的上一级
        # start_all.py 中 backend 的 cwd 是 project_root / "backend"
        # 所以 exports 目录应该是 ../exports
        
        # 使用绝对路径更安全
        backend_dir = os.getcwd()
        project_root = os.path.dirname(backend_dir)
        exports_dir = os.path.join(project_root, "exports")
        
        # 如果当前不是在 backend 目录下运行（比如在 app 目录下），可能需要调整
        if not os.path.exists(exports_dir):
            # 尝试另一种路径假设：假设当前是在项目根目录运行
            if os.path.exists("exports"):
                exports_dir = os.path.abspath("exports")
            else:
                # 尝试相对于此文件的路径
                # 此文件在 backend/app/utils/temp_file_manager.py
                # exports 在 backend/../../exports
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
                exports_dir = os.path.abspath(os.path.join(current_file_dir, "..", "..", "..", "exports"))

        if not os.path.exists(exports_dir):
            print(f"未找到 exports 目录: {exports_dir}")
            return 0
            
        cleaned_count = 0
        print(f"准备清理 exports 目录: {exports_dir}")
        
        # 遍历删除所有文件和子目录
        for item in os.listdir(exports_dir):
            item_path = os.path.join(exports_dir, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    cleaned_count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    cleaned_count += 1
                print(f"清理导出项: {item_path}")
            except Exception as e:
                print(f"删除导出项失败 {item_path}: {e}")
                
        return cleaned_count
    except Exception as e:
        print(f"清理导出目录时出错: {e}")
        return 0
