import os
import sys
from pathlib import Path

def clean_outputs_directory():
    outputs_dir = Path("storage/outputs")
    if not outputs_dir.exists():
        print(f"Directory {outputs_dir} does not exist.")
        return

    removed_count = 0
    total_bytes = 0

    for item in outputs_dir.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_file():
                size = item.stat().st_size
                item.unlink(missing_ok=True)
                removed_count += 1
                total_bytes += size
            elif item.is_dir():
                # recursively delete subfolder
                import shutil
                shutil.rmtree(item, ignore_errors=True)
                removed_count += 1
        except Exception as e:
            print(f"Error removing {item.name}: {e}")

    # Ensure .gitkeep exists
    gitkeep = outputs_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    mb = round(total_bytes / (1024 * 1024), 2)
    print(f"Cleaned {removed_count} files/directories from {outputs_dir} (freed {mb} MB).")

if __name__ == "__main__":
    clean_outputs_directory()
