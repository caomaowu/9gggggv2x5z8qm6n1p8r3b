import os
import shutil
import pathlib

def clean_pycache(root_dir):
    """
    Recursively find and remove all __pycache__ directories and their contents.
    """
    root_path = pathlib.Path(root_dir)
    print(f"Starting cleanup in: {root_path.absolute()}")
    
    count = 0
    
    # Walk through the directory tree
    for current_path, dirs, files in os.walk(root_dir):
        if "__pycache__" in dirs:
            pycache_path = os.path.join(current_path, "__pycache__")
            try:
                shutil.rmtree(pycache_path)
                print(f"Removed: {pycache_path}")
                count += 1
            except Exception as e:
                print(f"Error removing {pycache_path}: {e}")
                
    print(f"Cleanup finished. Removed {count} __pycache__ folders.")

if __name__ == "__main__":
    # Use the directory where the script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    clean_pycache(current_dir)
