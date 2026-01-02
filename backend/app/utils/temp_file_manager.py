import os
import time
import glob

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
