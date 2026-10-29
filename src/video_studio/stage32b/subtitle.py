"""P0-3 字幕生成（SRT + ASS + provenance + Gate）。

设计契约：文本 100% 来自冻结稿（不改写/不增删/不遗漏）；时间来自 alignment
segment start/end；长句按原文连续文本切分并按时间比例分配；不重叠/不越界/不反序。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MAX_CHARS = 22
STYLE = {  # ASS 最简样式（集中配置）
    "PlayResX": 1920, "PlayResY": 1080,
    "Fontname": "msyh", "Fontsize": 54,
    "PrimaryColour": "&H00FFFFFF", "OutlineColour": "&H00000000",
    "BorderStyle": 1, "Outline": 2, "Shadow": 0,
    "Alignment": 2, "MarginV": 60,
}
GEN_VERSION = "3.2b-p03"


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_ass(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _split_long(text: str, start: float, end: float) -> list[dict]:
    """长句按标点切 2 段，文本拼接必须逐字等于原文；时间按字数比例分配。"""
    if len(text) <= MAX_CHARS or end - start <= 0:
        return [{"text": text, "start": start, "end": end}]
    mid = len(text) // 2
    best, best_score = -1, 10 ** 9
    for sep in ("，", "、", "。", "；", " "):
        idx = text.find(sep, max(1, mid - 6), min(len(text) - 1, mid + 6))
        if idx != -1 and abs(idx - mid) < best_score:
            best, best_score = idx, abs(idx - mid)
    if best == -1:
        best = mid
    head, tail = text[:best + 1], text[best + 1:]
    total = end - start
    w = len(head) / len(text)
    split_t = start + total * w
    return [{"text": head, "start": start, "end": split_t},
            {"text": tail, "start": split_t, "end": end}]


def build_subtitles(alignment_path: Path, narration_path: Path,
                    out_dir: Path, force: bool = False) -> dict:
    al = json.loads(alignment_path.read_text(encoding="utf-8"))
    narration_text = narration_path.read_text(encoding="utf-8")
    in_fp = hashlib.sha256(
        (alignment_path.read_text(encoding="utf-8") + narration_text)
        .encode("utf-8")).hexdigest()[:16]
    srt_path = out_dir / "subtitles.srt"
    ass_path = out_dir / "subtitles.ass"
    prov_path = out_dir / "manifests" / "subtitle_manifest.json"
    prov_path.parent.mkdir(parents=True, exist_ok=True)
    if prov_path.exists() and not force:
        m = json.loads(prov_path.read_text(encoding="utf-8"))
        if m.get("input_fingerprint") == in_fp and srt_path.exists() and ass_path.exists():
            print(f"字幕已存在（指纹一致），跳过：{prov_path}")
            return m

    entries, segs = [], []
    for sh in al["shots"]:
        for s in sh["segments"]:
            segs.append(s)
            entries += [{"segment_id": s["segment_id"], **e}
                        for e in _split_long(s["text"], s["start"], s["end"])]

    # 尾部钳制：end 不得超过实际 media 总长（只动时间边界，文字/顺序不变）
    media_total = al.get("total_duration", 0.0)
    for e in entries:
        e["end"] = round(min(e["end"], media_total), 3)
        if e["start"] >= media_total:
            e["start"] = round(media_total - 0.001, 3)
    # 连续性归一：round 后强制 后条 start = 前条 end（消灭 0.0001s 级浮点 overlap）
    for i in range(1, len(entries)):
        entries[i]["start"] = entries[i - 1]["end"]

    # SRT
    srt_lines = []
    for i, e in enumerate(entries, 1):
        srt_lines += [str(i), f"{_fmt_srt(e['start'])} --> {_fmt_srt(e['end'])}",
                      e["text"], ""]
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    # ASS
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080",
           "", "[V4+ Styles]",
           ("Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV"),
           (f"Style: Default,{STYLE['Fontname']},{STYLE['Fontsize']},"
            f"{STYLE['PrimaryColour']},{STYLE['OutlineColour']},{STYLE['BorderStyle']},"
            f"{STYLE['Outline']},{STYLE['Shadow']},{STYLE['Alignment']},20,20,"
            f"{STYLE['MarginV']}"),
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text"]
    for e in entries:
        ass.append(f"Dialogue: 0,{_fmt_ass(e['start'])},{_fmt_ass(e['end'])},"
                   f"Default,,0,0,0,{e['text']}")
    ass_path.write_text("\n".join(ass), encoding="utf-8")

    manifest = {
        "input_fingerprint": in_fp,
        "narration_sha": _sha256_text(narration_text),
        "alignment_manifest_sha": _sha256_file(alignment_path),
        "vo_manifest_sha": al.get("vo_manifest_sha", ""),
        "generator_version": GEN_VERSION,
        "entry_count": len(entries),
        "segment_count": len(segs),
        "entries": entries,
        "srt": "subtitles.srt", "ass": "subtitles.ass",
    }
    prov_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"字幕完成：{len(entries)} 条（{len(segs)} 段）-> {srt_path} / {ass_path}")
    return manifest


def gate_subtitles(manifest: dict, alignment: dict) -> dict:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    entries = manifest["entries"]
    check("20/20 VO segment 全覆盖",
          {e["segment_id"] for e in entries} ==
          {s["segment_id"] for sh in alignment["shots"] for s in sh["segments"]},
          f"({len({e['segment_id'] for e in entries})} 段)")
    check("0 overlap", all(
        entries[i]["end"] <= entries[i + 1]["start"]
        for i in range(len(entries) - 1)))
    check("0 negative duration", all(e["end"] >= e["start"] for e in entries))
    check("0 out-of-range", all(
        0 <= e["start"] <= alignment["total_duration"] and
        0 <= e["end"] <= alignment["total_duration"] for e in entries))
    # 文本逐字一致：按 segment 合并条目文本 == 原段文本
    seg_ok = True
    for s in [s for sh in alignment["shots"] for s in sh["segments"]]:
        joined = "".join(e["text"] for e in entries if e["segment_id"] == s["segment_id"])
        if joined != s["text"]:
            seg_ok = False
            check(f"文本逐字一致 {s['segment_id']}", False, f"'{joined[:20]}' vs '{s['text'][:20]}'")
            break
    check("字幕文本 100% 来自冻结稿（逐字）", seg_ok)
    check("narration 顺序一致", _order_ok(entries, alignment))
    check("provenance 完整", all(k in manifest for k in
                                 ("narration_sha", "alignment_manifest_sha",
                                  "vo_manifest_sha", "generator_version", "input_fingerprint")))
    ok = all(c[1] for c in checks)
    print(f"\nP0-3 Gate: {'PASS' if ok else 'FAIL'}")
    return {"gate": "PASS" if ok else "FAIL",
            "fails": [c[0] for c in checks if not c[1]]}


def _order_ok(entries, alignment) -> bool:
    idx = {}
    pos = 0
    for sh in alignment["shots"]:
        for s in sh["segments"]:
            idx[s["segment_id"]] = pos
            pos += 1
    last = -1
    for e in entries:
        if idx[e["segment_id"]] < last:
            return False
        last = idx[e["segment_id"]]
    return True
