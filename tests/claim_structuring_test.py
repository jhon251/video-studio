"""Stage 8G：Claim Structuring 拆解 gold set 测试。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.claim_structuring import decompose_claim  # noqa: E402

gold = json.loads((ROOT / "tests" / "data" / "claim_structuring_gold.json").read_text(encoding="utf-8"))["entries"]


def set_pr(pred, truth):
    p, t = set(pred), set(truth)
    tp = len(p & t)
    return (tp / len(p) if p else 1.0), (tp / len(t) if t else 1.0)


def main() -> int:
    ct_ok = sub_ok = 0
    q_prec = q_rec = n_prec = n_rec = 0.0
    for e in gold:
        d = decompose_claim(e["text"])
        ct_ok += d["claim_type"] == e["claim_type"]
        sub_ok += len(d["sub_claims"]) == e["sub_count"]
        p, r = set_pr(d["qualifiers"], e["qualifiers"])
        q_prec += p; q_rec += r
        p, r = set_pr(d["numbers_years"], e["numbers_years"])
        n_prec += p; n_rec += r
    n = len(gold)
    checks = {
        "claim_type 全对": ct_ok == n,
        "sub_count 全对": sub_ok == n,
        "qualifier P≥0.95": q_prec / n >= 0.95,
        "qualifier R≥0.95": q_rec / n >= 0.95,
        "number P≥0.95": n_prec / n >= 0.95,
        "number R≥0.95": n_rec / n >= 0.95,
    }
    for name, cond in checks.items():
        print(f"{'PASS' if cond else 'FAIL'}  {name}")
    print(f"claim_type {ct_ok}/{n} | sub_count {sub_ok}/{n} | "
          f"qualifier P={q_prec/n:.3f} R={q_rec/n:.3f} | number P={n_prec/n:.3f} R={n_rec/n:.3f}")
    failed = [k for k, v in checks.items() if not v]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
