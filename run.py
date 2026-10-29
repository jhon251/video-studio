"""根目录入口：python run.py <命令>"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env  # noqa: E402

load_env(ROOT / ".env")   # API 密钥只从 .env 读取，禁止硬编码

from video_studio.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
