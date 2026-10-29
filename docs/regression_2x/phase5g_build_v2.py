"""EXP-5G step D: build mm_truth_set_v2.json + per-project subset files.

v2 = v1's 14 cases (byte-copied) + 12 p_ab2b multi-shot scenes (dual-pass labeled)
     + 6 p_8f05 solid-color UNKNOWN cases.
Schema mm-truth-set-v2 (extends v1: projects[] + coverage matrix v2 incl. motion LIMITATION).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent          # docs/regression_2x
OUT = HERE.parents[1] / 'output' / 'audit_20260910_ds1'
ROOT = HERE.parents[1]
V1 = json.load(open(ROOT / 'tests/fixtures/mm_truth_set_v1.json', encoding='utf-8'))

# ---------- human pass-1 labels (from contact sheets, see ss2_ab2b_labels_p1.json) ----------
LAB = json.load(open(OUT / 'ss2_ab2b_labels_p1.json', encoding='utf-8'))
p_ab2b_labels = LAB['labels']
p_ab2b_expected = LAB['expected']

RENDER_AB2B = 'a_25dbe50ce44a'
RENDER_8F05 = 'a_0a65c33909e3'

NARR_AB2B = json.load(open(OUT / 'ss_ab2b_film.json', encoding='utf-8'))['narration']
SEG_8F05 = json.load(open(OUT / 'ss_8f05_segments.json', encoding='utf-8'))['segments']

cases = []
# ---- v1: 14 cases byte-copied (in-memory) with project tag added for v2 matrix ----
import copy as _copy
for c in V1['cases']:
    cc = _copy.deepcopy(c)
    cc['covers'] = list(cc.get('covers') or []) + ['project:p_f4b466a4a024']
    cases.append(cc)
# ---- p_ab2b: 12 multi-shot scenes ----
for sid in sorted(p_ab2b_labels):
    lab = p_ab2b_labels[sid]
    exp = p_ab2b_expected[sid]
    narr = (NARR_AB2B.get(sid) or {}).get('text', '')
    cl = lab['label']
    if cl == 'MISMATCH':
        e5 = {'allow': ['MISMATCH', 'UNKNOWN'], 'must_not': ['MATCH']}
        e4 = {'allow': ['MATCH', 'UNKNOWN', 'MISMATCH']}
    else:
        e5 = {'allow': ['MATCH', 'UNKNOWN'], 'must_not': ['MISMATCH']}
        e4 = {'allow': ['MATCH', 'UNKNOWN'], 'must_not': ['MISMATCH']}
    cases.append({
        'id': f'G01_pab2b_{sid}_{cl.lower()}',
        'kind': 'real_artifact',
        'source': {'artifact_id': RENDER_AB2B, 'scene_id': sid,
                   'role': '真实链路成片（12 段旁白 438s；看图双轮标注）'},
        'content_label': cl,
        'content_label_provenance': ('5-G 看图双轮标注（7 帧 contact sheet ×2 轮）：画面=' + lab['img']
                                     + '；旁白域=' + lab['nar_dom'] + '；' + lab['note']),
        'expect': {'4b': e4, '5a': e5, '5d': e5},
        'covers': [f'scene:{sid}', f'content:{cl}', 'project:p_ab2b352e06b8',
                   'dim:multi_shot', 'dim:domain_boundary' if cl == 'MISMATCH' else 'dim:domain_match'],
        'narration_excerpt': narr[:80],
    })

# ---- p_8f05: 6 solid-color UNKNOWN/fail-closed cases ----
for seg in SEG_8F05:
    i = seg['i']; sid = f'S{i}'
    cases.append({
        'id': f'G02_p8f05_{sid}_unknown',
        'kind': 'real_artifact',
        'source': {'artifact_id': RENDER_8F05, 'scene_id': sid,
                   'role': '真实链路成片（纯色底+字幕，素材装配 PENDING——零视觉证据 fail-closed 类）'},
        'content_label': 'UNCERTAIN',
        'content_label_provenance': ('5-G 看图标注：纯色底+字幕，无任何视觉证据对象；'
                                     '人类判定=无法从画面确认语义（fail-closed UNKNOWN 类）'),
        'expect': {'5a': {'allow': ['UNKNOWN'], 'must_not': ['MATCH', 'MISMATCH']},
                   '5d': {'allow': ['UNKNOWN'], 'must_not': ['MATCH', 'MISMATCH']}},
        'covers': [f'scene:{sid}', 'content:UNKNOWN', 'project:p_8f054c227bd4',
                   'dim:fail_closed', 'dim:solid_color_no_referent'],
        'narration_excerpt': seg['narration'][:80],
    })

v2 = {
    'schema': 'mm-truth-set-v2',
    'name': '多模态真值集 v2（多项目 × 多镜头 × 边界类；运动素材=LIMITATION）',
    'frozen_at': '2026-09-19',
    'frozen_note': ('v1 14 例原样并入（project p_f4b466a4a024）；新增 p_ab2b352e06b8 12 段多镜头旁白成片'
                    '（7 域一致 + 5 域边界错配）与 p_8f054c227bd4 6 段纯色底 UNKNOWN fail-closed 用例。'
                    '运动素材覆盖 = 0（全库 1592 项目 0 视频资产）——如实 LIMITATION，未虚构。'),
    'project_id': 'p_f4b466a4a024',
    'projects': ['p_f4b466a4a024', 'p_ab2b352e06b8', 'p_8f054c227bd4'],
    'label_axes': V1['label_axes'],
    'cases': cases,
    'coverage_requirements': {
        'min_cases': 30,
        'projects_min': 3,
        'multi_shot_min': 10,
        'content_labels': ['MATCH', 'MISMATCH', 'UNCERTAIN'],
        'dimensions': ['multi_shot', 'domain_boundary', 'domain_match', 'fail_closed',
                       'solid_color_no_referent'],
        'motion_footage': {'covered': False, 'limitation': '全库 0 视频素材（如实 LIMITATION，见 EXP-SS1）'},
        'unknown_boundary_min': 6,
    },
    'frozen_policy': {
        'thresholds_frozen': True,
        'signoff': {'authorized_by': 'user (project owner) — 5-G execution authorization',
                    'authorized_at': '2026-09-19',
                    'authorization_ref': 'PHASE5G_PLAN.md A→G'},
        'note': ('5-G 只做评估与解释：不修改评分/判定逻辑与阈值，不接生产判定链，不自动换材/选材/redo。'
                 'v1 文件原样保留。')},
}
out = ROOT / 'tests/fixtures/mm_truth_set_v2.json'
out.write_text(json.dumps(v2, ensure_ascii=False, indent=1), encoding='utf-8')
print('v2 written:', out, '| cases:', len(cases))
kinds = json.dumps([c['covers'] for c in cases], ensure_ascii=False)
import collections
cnt = collections.Counter(c['content_label'] for c in cases)
print('labels:', dict(cnt), '| projects:', len(v2['projects']))

# ---------- per-project subset files (for calibration_report runs) ----------
import hashlib
proj_cases = {'p_f4b466a4a024': [c for c in V1['cases']],
              'p_ab2b352e06b8': [c for c in cases if (c.get('source') or {}).get('artifact_id') == RENDER_AB2B],
              'p_8f054c227bd4': [c for c in cases if (c.get('source') or {}).get('artifact_id') == RENDER_8F05]}
for pid, cs in proj_cases.items():
    sub = dict(v2)
    sub['cases'] = cs
    sub['name'] = v2['name'] + f' — 子集 {pid}'
    sub['coverage_requirements'] = {'min_cases': 1, 'scope': 'subset',
                                    'motion_footage': dict(v2['coverage_requirements'].get('motion_footage') or {}),
                                    'note': 'per-project subset; full matrix enforced on master v2'}
    sp = ROOT / 'tests/fixtures' / f'mm_truth_set_v2_{pid}.json'
    sp.write_text(json.dumps(sub, ensure_ascii=False, indent=1), encoding='utf-8')
    print('subset:', sp.name, len(cs), 'cases | sha16', hashlib.sha256(sp.read_bytes()).hexdigest()[:16])
print('master sha256:', hashlib.sha256(out.read_bytes()).hexdigest())
