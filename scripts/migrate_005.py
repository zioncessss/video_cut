"""005 迁移手动入口：体检(medical) → 体验(experience) 空镜分类。

实际迁移实现统一在 backend/app/db/migrator.py::migrate_category_experience
（应用启动时也会自动执行同一实现，本脚本仅用于手动触发与试运行核对）。

惯例：
  - 默认试运行：仅打印将要执行的变更，不写任何数据；
  - --apply 才真正写回；
  - 后端服务运行中拒绝执行（SQLite 写冲突与内存缓存覆盖风险）。
"""
import argparse
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.db.migrator import migrate_category_experience  # noqa: E402


def backend_is_running() -> bool:
    try:
        # 固定本机健康检查地址，字面量内联，杜绝任何动态 URL 来源
        with urllib.request.urlopen("http://127.0.0.1:18888/api/health", timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="005: medical→experience 分类迁移（默认试运行，启动应用时也会自动执行）")
    parser.add_argument("--apply", action="store_true", help="真正写回（默认仅试运行打印变更）")
    args = parser.parse_args()

    if backend_is_running():
        print("❌ 检测到后端服务正在运行（127.0.0.1:18888），为避免 SQLite 写冲突与内存缓存覆盖，请先停止后端再执行迁移。")
        sys.exit(2)

    print(f"== 005 迁移（medical → experience）模式: {'【APPLY 实际写回】' if args.apply else '【试运行，不加 --apply 不写数据】'}==\n")

    actions = migrate_category_experience(dry_run=not args.apply)
    for a in actions:
        print(" •", a)
    print("\n完成。再次运行本脚本应全部显示 [跳过]（幂等）。")


if __name__ == "__main__":
    main()
