"""3.x Phase 1.1：Windows subprocess 编码健壮性回归测试（最小但能抓真实问题）。

背景：真实运行中曾出现一次
    UnicodeDecodeError: 'gbk' codec can't decode byte 0x8c in po...
未落入数据库（非任务失败），也未复现 → 标记 ROOT_CAUSE_NOT_REPRODUCED。
但**风险类别明确**：Windows 上 `subprocess.run(..., text=True)` 未指定 `encoding=` 时，
Python 用本地编码（本机 cp936/GBK）解码子进程输出；若子进程输出 UTF-8（含中文路径/文件名），
即抛 UnicodeDecodeError，且该异常不是 ToolError → 绕过上层 `except ToolError` 降级路径。

本测试做三件事：
  1) 记录并断言本机默认编码确实是 GBK（否则该风险类别不成立，测试应随之调整）
  2) **静态守卫**：用 AST 扫描 src/video_studio 下所有 `subprocess.*(..., text=True)` 调用，
     必须同时给定 `encoding=`（新写的漏点会被立刻抓住）
  3) 运行时：FFmpegTool 对**含中文文件名**的目标探测不得抛异常；二进制无效时必须抛可诊断 ToolError

运行：python tests/subprocess_encoding_test.py
"""
import ast
import locale
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:180] if detail else ""))


# ---------- 1) 本机默认编码 ----------
enc = locale.getpreferredencoding(False)
check("本机默认编码为 GBK 族（说明该风险类别真实存在）",
      enc.lower() in ("cp936", "gbk", "gb2312", "cp950", "big5"), enc)

# 演示风险：UTF-8 中文路径字节用 GBK 解码会失败
utf8_bytes = "素材/中文文件名.jpg".encode("utf-8")
try:
    utf8_bytes.decode(enc)
    demo_failed = False
except UnicodeDecodeError as exc:
    demo_failed = True
    demo_msg = str(exc)
check("UTF-8 字节用本机编码解码确实会抛 UnicodeDecodeError", demo_failed,
      demo_msg if demo_failed else "（未抛，风险类别不成立）")

# ---------- 2) 静态守卫：所有 subprocess(text=True) 必须指定 encoding ----------
bad = []
scanned = 0
for py in sorted((ROOT / "src" / "video_studio").rglob("*.py")):
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if name not in ("run", "check_output", "Popen", "call", "check_call"):
            continue
        kw = {k.arg for k in node.keywords if k.arg}
        if "text" not in kw and "universal_newlines" not in kw:
            continue
        scanned += 1
        if "encoding" not in kw:
            bad.append("{}:{}".format(py.relative_to(ROOT).as_posix(), node.lineno))
check("src 内所有 subprocess(text=True) 均指定 encoding（静态守卫）", not bad,
      "扫描 {} 处，漏点：{}".format(scanned, bad[:8]))
check("静态守卫确实覆盖到 ffmpeg_tool（抽样>0）", scanned > 0, "scanned={}".format(scanned))

# ---------- 3) 运行时：中文文件名 + 可诊断错误 ----------
from video_studio.tools.base import ToolContext, ToolError  # noqa: E402
from video_studio.tools.ffmpeg_tool import FFmpegTool  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="enc_test_"))
media = tmp / "中文素材目录"
media.mkdir(parents=True, exist_ok=True)
target = media / "中文文件名_测试.mp4"
target.write_bytes(b"not-a-real-video")

cfg = {"tools": {"ffmpeg": {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                            "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}}}
ctx = ToolContext(role="editing", project_id="p_enc", project_dir=tmp, db=None, config=cfg)
tool = FFmpegTool()
raised = None
try:
    res = tool.execute({"op": "probe", "inputs": ["中文素材目录/中文文件名_测试.mp4"]}, ctx)
    detail = "streams={}".format(len(res.data.get("streams", [])))
except ToolError as exc:
    raised = exc
    detail = "ToolError code={}".format(exc.code)
except UnicodeDecodeError as exc:
    raised = exc
    detail = "UnicodeDecodeError: {}".format(exc)
check("含中文路径的探测不抛 UnicodeDecodeError",
      not isinstance(raised, UnicodeDecodeError), detail)
check("失败时给出可诊断错误（ToolError 或正常返回）",
      raised is None or isinstance(raised, ToolError), type(raised).__name__ if raised else "ok")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
