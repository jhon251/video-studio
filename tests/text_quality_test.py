"""Stage 8D：evidence_text_quality 检测 gold set 测试（5 类状态 + js_shell 内容打捞）。"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.evidence_text_quality import (  # noqa: E402
    quality, extract_body, decode_bytes,
)

gold = json.loads((ROOT / "tests" / "data" / "text_quality_dev.json").read_text(encoding="utf-8"))["entries"]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    ok = 0
    conf = Counter()
    errors = []
    for e in gold:
        got = quality(e["text"])["status"]
        if got == e["expected"]:
            ok += 1
        else:
            errors.append((e["id"], e["expected"], got))
        conf[(e["expected"], got)] += 1
    print(f"text_quality gold 准确率: {ok}/{len(gold)} = {ok/len(gold):.3f}")
    print(f"  错误案例: {errors}")
    for cls in ("valid", "js_shell", "empty", "encoding_error", "low_content"):
        tp = conf[(cls, cls)]
        pred = sum(v for (t, p), v in conf.items() if p == cls)
        truth = sum(v for (t, p), v in conf.items() if t == cls)
        print(f"  {cls}: precision={tp/pred if pred else None} recall={tp/truth if truth else None}")

    # 编码解码
    gbk = "中国脑科学计划进展".encode("gb18030")
    txt, enc = decode_bytes(gbk)
    check("GBK 字节解码为正确中文", txt == "中国脑科学计划进展" and enc == "gb18030",
          f"({enc})")
    utf8 = "中国脑科学计划进展".encode("utf-8")
    check("UTF-8 字节解码正确", decode_bytes(utf8)[0] == "中国脑科学计划进展")
    check("BOM 处理", decode_bytes(b"\xef\xbb\xbf" + utf8)[1] == "utf-8-sig")

    # js_shell 内容打捞：meta description 在标签属性中，plain_text 不含其内容，
    # 命中 "just a moment" 判为 js_shell；打捞应取回 ≥40 字符的真实描述。
    shell_html = (
        "<html><head><title>Just a moment...</title>"
        '<meta name="description" content="这是一段超过四十个字的真实正文描述内容，'
        '用于测试 js shell 内容打捞功能是否能够正确提取隐藏在元数据里的可用信息。">'
        "</head><body>Enable JavaScript and cookies to continue</body></html>"
    )
    res = extract_body(shell_html)
    check("js_shell 打捞 salvaged=True", res["salvaged"] is True, f"(status={res['status']})")
    check("打捞正文长度 ≥40", len(res["text"]) >= 40, f"(len={len(res['text'])})")
    check("打捞正文含关键描述词", "内容打捞" in res["text"], f"({res['text'][:20]}...)")

    # 无内容可打捞的 js_shell 保持原状
    bare = "<html><title>Just a moment...</title></html>"
    res2 = extract_body(bare)
    check("无内容 js_shell 不误判打捞", res2["salvaged"] is False and res2["status"] == "js_shell",
          f"(status={res2['status']}, salvaged={res2['salvaged']})")

    checks.append(("text_quality gold 全对", ok == len(gold)))
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
