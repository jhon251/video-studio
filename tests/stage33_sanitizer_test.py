"""stage33 sanitizer 测试（脚本式）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33.sanitizer import build_whitelist, parse_narration, _norm_text  # noqa: E402


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    all_shots = json.loads((ROOT / "output" / "stage31_realworld" / "coral" /
                            "material_pkg_real" / "shot_mapping" / "all_shots.json")
                           .read_text(encoding="utf-8"))
    wl, registry = build_whitelist(all_shots)

    check("白名单 20 镜齐全", set(wl.keys()) == {f"S{i:02d}" for i in range(1, 21)})
    check("registry 无 UNKNOWN/UNSAFE", all(
        v["rights_status"] in ("SAFE", "CONDITIONAL") for v in registry.values()))
    check("registry 全部 sem>=50", all(v["semantic_match"] >= 50 for v in registry.values()))
    check("S01/S02 无白名单候选（coral 事实）",
          all(wl[k] == [] for k in ("S01", "S02")))
    # S03：3.2b 只看 primary（45.2 拒绝）；3.3 白名单含 alternatives，M-S03-162 sem=50.0 达标（阈值未变）
    s03 = wl.get("S03", [])
    check("S03 含 sem=50.0 的 SAFE 候选（alternatives 纳入，阈值未降）",
          any(c["material_id"] == "M-S03-162" and c["semantic_match"] == 50.0
              and c["rights_status"] == "SAFE" for c in s03))
    check("S04 有白名单候选（sem 64.2 素材）", any(
        c["material_id"] == "M-S04-224" for c in wl.get("S04", [])))
    # S02 的 46.8 分 primary 必须被滤掉（sem<50）
    s02_ids = {c["material_id"] for c in wl.get("S02", [])}
    check("S02 的 46.8 分候选被滤除", "M-S02-102" not in s02_ids and not s02_ids)
    # 候选字段无 URL / HTML / 路径（直接检查字段值，不受 JSON 转义干扰）
    all_c = [c for cs in wl.values() for c in cs]
    def _clean_fields(c):
        vals = [str(c.get(k, "")) for k in c]
        return not any("http" in v or "<" in v or ">" in v or "\\" in v for v in vals)
    check("候选字段不含 URL/HTML/路径", all(_clean_fields(c) for c in all_c))
    # 口播解析
    nar = _norm_text(ROOT / "output" / "stage31_realworld" / "coral" / "V2_FINAL_SCRIPT_JARVIS.md")
    shots = parse_narration(nar)
    check("口播解析 20 镜", len(shots) == 20)
    check("S01 文本逐字", shots[0]["text"] == "在海水下面，有一座正在慢慢褪色的城市。")
    check("S20 文本逐字", shots[-1]["text"] == "那是一座会呼吸的城市，而它正在等待降温。")

    print(f"\nsanitizer test: {'FAIL' if fails else 'ALL PASS'} ({len(fails)} fails)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
