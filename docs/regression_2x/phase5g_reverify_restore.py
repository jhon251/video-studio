# -*- coding: utf-8 -*-
"""Re-execute the battery's restore verification step and refresh the summary."""
import json, hashlib
from pathlib import Path

BASE = Path(r'C:\mp4agent\video-studio\docs\regression_2x')
LOGS = BASE / 'logs'
BAK = BASE / 'logs_5e_frozen'

def build_manifest(d):
    out = {}
    for p in sorted(d.rglob('*')):
        if p.is_file():
            rel = p.relative_to(d).as_posix()
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out

pre = build_manifest(BAK)
pre.pop('MANIFEST.json', None)   # backup's own meta-file, not evidence
post2 = build_manifest(LOGS)
frozen_restored = all(post2.get(k) == v for k, v in pre.items())
missing = [k for k in pre if k not in post2]
drift = [k for k in pre if k in post2 and post2[k] != pre[k]]
print('re-executed restore verification: frozen_restored =', frozen_restored)
print('missing:', len(missing), '| drift:', len(drift))

sm_p = LOGS / 'phase5f_regression_summary.json'
sm = json.loads(sm_p.read_text(encoding='utf-8'))
sm['frozen_logs_restored'] = frozen_restored
sm['frozen_restore_reverified_at'] = '2026-09-19 (same code path as battery restore)'
sm_p.write_text(json.dumps(sm, ensure_ascii=False, indent=1), encoding='utf-8')
print('summary refreshed: frozen_logs_restored =', frozen_restored)
