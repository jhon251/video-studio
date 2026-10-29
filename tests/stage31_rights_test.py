"""Stage 3.1 版权安全测试（G15 用例 + 硬门槛）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage31.rights import classify, hard_gate, pool_status  # noqa: E402

CASES = [
    # (名称, url, license_text, 期望 status, 期望 commercial, 期望 attribution)
    ("电影片段", "https://www.youtube.com/watch?v=xyz", "CC BY 4.0", "UNSAFE", False, False),
    ("新闻视频", "https://v.qq.com/x/page/abc.html", "CC0", "UNSAFE", False, False),
    ("B站视频", "https://www.bilibili.com/video/BV1xx", "", "UNSAFE", False, False),
    ("YouTube视频", "https://youtu.be/abcdef", "Public Domain", "UNSAFE", False, False),
    ("小红书视频", "https://www.xiaohongshu.com/explore/123", "CC0", "UNSAFE", False, False),
    ("抖音视频", "https://www.douyin.com/video/123", "CC BY 4.0", "UNSAFE", False, False),
    ("商业图库", "https://www.shutterstock.com/image-photo/x", "CC0", "UNSAFE", False, False),
    ("无许可证图片", "https://example.com/img.jpg", "", "UNKNOWN", False, False),
    ("未知许可证文本", "https://example.com/img2.jpg", "some weird text", "UNKNOWN", False, False),
    ("CC0", "https://commons.wikimedia.org/wiki/File:A.jpg", "CC0", "SAFE", True, False),
    ("CC BY", "https://commons.wikimedia.org/wiki/File:B.jpg", "CC BY 4.0", "CONDITIONAL", True, True),
    ("CC BY-SA", "https://commons.wikimedia.org/wiki/File:C.jpg", "CC BY-SA 4.0", "CONDITIONAL", True, True),
    ("Public Domain", "https://commons.wikimedia.org/wiki/File:D.jpg", "Public domain", "SAFE", True, False),
    ("CC BY-NC", "https://commons.wikimedia.org/wiki/File:E.jpg", "CC BY-NC 4.0", "UNSAFE", False, False),
    ("CC BY-ND", "https://commons.wikimedia.org/wiki/File:F.jpg", "CC BY-ND 4.0", "UNSAFE", False, False),
    ("All Rights Reserved", "https://example.com/img3.jpg", "All rights reserved", "UNSAFE", False, False),
    ("GFDL", "https://commons.wikimedia.org/wiki/File:G.jpg", "GFDL", "CONDITIONAL", True, True),
    ("无URL且无许可证", None, None, "UNKNOWN", False, False),
]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    for name, url, lic, exp_status, exp_comm, exp_attr in CASES:
        info = classify(url, lic, source_name="test", creator="测试作者")
        check(f"{name} -> {exp_status}", info.status == exp_status,
              f"(got {info.status})")
        check(f"{name} commercial_use={exp_comm}", info.commercial_use == exp_comm,
              f"(got {info.commercial_use})")
        check(f"{name} attribution_required={exp_attr}",
              info.attribution_required == exp_attr,
              f"(got {info.attribution_required})")

    # 硬门槛：UNSAFE/UNKNOWN 不进默认池
    for name, url, lic, *_ in CASES:
        info = classify(url, lic)
        if info.status in ("UNSAFE", "UNKNOWN"):
            check(f"硬门槛淘汰 {name}", hard_gate(info) is False and
                  pool_status(info) == "EXCLUDED")
    ccby = classify("https://commons.wikimedia.org/wiki/File:B.jpg", "CC BY 4.0", creator="张三")
    check("CONDITIONAL 署名文案包含作者", "张三" in ccby.attribution_text,
          ccby.attribution_text)
    check("CONDITIONAL 署名文案包含许可证", "CC BY 4.0" in ccby.attribution_text,
          ccby.attribution_text)

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
