"""stage33 executor 分层回归测试（F1：素材不被底色覆盖；z-order）。"""
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33.executor import _render_beat  # noqa: E402
from video_studio.stage33.visual_qc import _rgb_frame  # noqa: E402


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    style = {"palette": {"bg": "#0E2A33", "surface": "#16404F", "accent": "#4FC3F7",
                         "text": "#F4F8F9", "highlight": "#FFB74D"},
             "typography": {"anchor": 128, "small_anchor": 84, "tag": 30}}
    meta = {"materials": []}
    tmp = Path(tempfile.mkdtemp(prefix="v3_layer_test_"))
    n = 50

    def mk_spec(kinds):
        return {"beat_id": "T1", "n_frames": n, "duration": 2.0, "layers": kinds}

    # 1) material beat：素材真实可见（luma/std 不退化为底色）
    mat_spec = mk_spec([
        {"kind": "color", "color": "#0E2A33", "alpha_frames": [255] * n},
        {"kind": "material", "material_id": "M-S04-224",
         "alpha_frames": [255] * n, "rects": None},
        {"kind": "anchor_text", "text": "测试锚点", "font_size": 128,
         "color": "#FFB74D", "stroke": 0, "anchor": (960, 540),
         "alpha_frames": [255] * n}])
    out1 = tmp / "mat.mp4"
    _render_beat(mat_spec, out1, style, meta, tmp, {"start": 0.0, "end": 2.0})
    f1 = _rgb_frame(out1, 1.0)
    y = 0.299 * f1[..., 0].astype(float) + 0.587 * f1[..., 1].astype(float) + \
        0.114 * f1[..., 2].astype(float)
    check("material beat 素材纹理可见（std>30 且 luma>50）",
          float(y.std()) > 30 and float(y.mean()) > 50,
          f"luma={y.mean():.1f} std={y.std():.1f}")
    r, g, b = f1[..., 0].astype(int), f1[..., 1].astype(int), f1[..., 2].astype(int)
    orange = float(((r > 200) & (g > 130) & (g < 215) & (b < 130)).mean())
    check("锚点文字在素材之上可见（橙色像素存在）", orange > 0.0005,
          f"orange={orange:.5f}")

    # 2) color-only beat：纯底色（无素材时行为不变）
    col_spec = mk_spec([
        {"kind": "color", "color": "#0E2A33", "alpha_frames": [255] * n},
        {"kind": "anchor_text", "text": "测试锚点", "font_size": 128,
         "color": "#F4F8F9", "stroke": 0, "anchor": (960, 540),
         "alpha_frames": [255] * n}])
    out2 = tmp / "col.mp4"
    _render_beat(col_spec, out2, style, meta, tmp, {"start": 0.0, "end": 2.0})
    f2 = _rgb_frame(out2, 1.0)
    y2 = 0.299 * f2[..., 0].astype(float) + 0.587 * f2[..., 1].astype(float) + \
        0.114 * f2[..., 2].astype(float)
    check("color-only beat 仍为底色（luma≈34.6 附近）", abs(float(y2.mean()) - 34.6) < 3.0,
          f"luma={y2.mean():.1f}")
    white = float((y2 > 218).mean())
    check("color-only beat 文字可见（白色像素）", white > 0.0005, f"white={white:.5f}")

    # 3) z-order：color 层必须在素材之下（等价断言：素材可见性不受 color 层存在影响）
    check("z-order 断言（素材+color 并存时素材仍可见）",
          float(y.std()) > 30)

    print(f"\nexecutor layers test: {'FAIL' if fails else 'ALL PASS'} ({len(fails)} fails)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
