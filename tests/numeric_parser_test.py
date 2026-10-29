"""Stage 8C：数字解析通用测试（千分位 / 中文数量级 / 年份 / 近似数）。数据无关，无样本特例。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.sufficiency_judge import _extract_numbers_corrected  # noqa: E402


def vals(text):
    return [(v, u) for v, u, _ in _extract_numbers_corrected(text)]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    check("千分位 139,255 不拆分", vals("约139,255个神经元") == [(139255.0, "")], f"{vals('约139,255个神经元')}")
    check("5,000万 → 5000万（值含单位乘数）", (50000000.0, "万") in vals("5,000万个突触"),
          f"{vals('5,000万个突触')}")
    check("86,000,000,000 不拆分", vals("86,000,000,000") == [(86000000000.0, "")], f"{vals('86,000,000,000')}")
    check("中文 八百六十亿", (8.6e10, "亿") in vals("人脑大约八百六十亿个神经元"),
          f"{vals('人脑大约八百六十亿个神经元')}")
    check("中文 十四万", (140000.0, "万") in vals("果蝇十四万"), f"{vals('果蝇十四万')}")
    check("年份 2023 完整保留", "2023" in [r for _, _, r in _extract_numbers_corrected("2023年完成")])
    check("十几年近似数不产生精确 10", (10.0, "") not in vals("跑了十几年"), f"{vals('跑了十几年')}")
    check("数万亿被跳过", all(v != 0.0 or u == "" for v, u in vals("数万亿个突触")),
          f"{vals('数万亿个突触')}")
    check("纯数字无单位", (860.0, "") in vals("860"), f"{vals('860')}")

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
