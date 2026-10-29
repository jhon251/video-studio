"""特征转储：对指定样本输出判定过程细节，供规则迭代。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import video_studio.tools.semantic_judge as J  # noqa: E402

data = json.loads((ROOT / "tests" / "data" / "evidence_regression_r1.json").read_text(encoding="utf-8"))
want = set(sys.argv[1:])
for s in data["samples"]:
    if want and s["id"] not in want:
        continue
    ev = s["evidence"]
    ev_plain = ev.get("title", "") + ev.get("snippet", "") + ev.get("text", "")
    prof = J._claim_profile(s["claim_text"])
    matched, conflict = J._matched_core(prof, ev)
    print("=" * 60)
    print(s["id"], s["category"], "truth=", s["truth_label"], "got=", J.judge_support(s["claim_text"], ev))
    print("claim:", s["claim_text"][:70])
    print("flags: question=%s step_def=%s gloss=%s fiction=%s rhet=%s neg=%s" % (
        prof["question"], prof["step_def"], prof["gloss_def"], prof["fiction"],
        prof["rhetorical"], prof["neg"]))
    print("claim_domains:", prof["domains"], "| dom_words:", list(prof["dom_words"]))
    print("latin:", prof["latin"], "| numbers:", prof["numbers"], "| quals:", prof["qualifiers"])
    print("matched_core:", matched, "| conflict:", conflict)
    print("ev_domains:", J._ev_domains(ev), "| generic_overlap:", J._generic_overlap(s["claim_text"], ev_plain))
    print("ev_neg_scoped:", J._scoped_negation(ev.get("text", "") or ev_plain, matched, prof["feasible"]))
    print("neg_span_affirmed:", J._negated_span_affirmed(s["claim_text"], ev_plain))
    print("quantified:", {w: J._quantified_word_relation(s["claim_text"], w) for w in prof["dom_words"]})
    print("title:", (ev.get("title") or "")[:60])
    print("text:", (ev.get("text") or "")[:200].replace("\n", " "))
