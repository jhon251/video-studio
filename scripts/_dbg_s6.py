import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import video_studio.tools.sufficiency_judge as J

claim = "人脑大约八百六十亿个神经元"
ev = {"title": "要論能效還看大腦", "snippet": "人類大腦約有860億個神經元",
      "text": "人類大腦約有860億個神經元", "url": "https://e.com/3"}
ev_norm = J.t2s(ev["title"] + ev["snippet"] + ev["text"])
print("ev_norm:", ev_norm)
print("nums claim:", J._extract_numbers(J.t2s(claim)))
print("nums ev:", J._extract_numbers(ev_norm))
print("present:", J._num_present_in_evidence("八百六十亿个", ev_norm))
prof = J._claim_profile(J.t2s(claim))
print("flags: q", prof["question"], "step", prof["step_def"], "fiction", prof["fiction"])
print("rule_ct:", J.rule_claim_type(claim))
print("quals:", J._qualifier_requirements(J.t2s(claim)))
llm = {"relevance": "RELEVANT", "claim_type": "ASSERTION", "contradiction_candidate": False,
       "subject_match": True, "object_match": True, "predicate_match": True,
       "conjunction_covered": True, "qualifiers": {}, "numbers_years": {}, "evidence_quote": ""}
d = J._decide_v6(claim, ev, "PARTIAL_SUPPORT", llm, J.DEFAULT_FLAGS)
print("decision:", d["level"], d["reason"])
print("checks:", {k: v for k, v in d.items() if k.startswith("s") or k == "claim_type"})
