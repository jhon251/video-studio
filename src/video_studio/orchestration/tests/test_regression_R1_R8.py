"""Regression fixtures R1-R8 (EXP-VG implementation acceptance, section 七)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[3]))
from video_studio.orchestration import (
    AssetRef, BeatSpec, Candidate, CropLayout, ContentIndex,
    IntegrityGateConfig, NamespacePolicy, ReusePolicyConfig,
    build_content_index, check_namespace, evaluate_asset, evaluate_crop,
    run_reuse_policy, GateVerdict, DisplayKind,
)
FIX = Path(__file__).parent / 'fixtures'
RESULTS = []


def fixture(name):
    p = FIX / name
    if not p.exists():
        raise FileNotFoundError(f'fixture missing: {p} (run make_fixtures.py)')
    return str(p)


def _beat(bid, route, ch, s, e, cands):
    return BeatSpec(beat_id=bid, route=route, chapter_id=ch, start=s, end=e, candidates=cands)


def _cand(mid, cid, path, usable='USABLE', fit=0.95):
    return Candidate(material_id=mid, content_id=cid, path=path, eligible=True,
                     cv2_usability=usable, cv2_fit=fit)


# R1: S10-B02 crop failure -> crop recheck must capture (vis<0.55, shift>14, DEMOTE)
def R1():
    risk = evaluate_crop(fixture('r2_S10-B02_4.img.jpg'), 'S10-B02', 'r2_S10-B02_4',
                         layout=CropLayout(fit_mode='cover'))
    assert risk.verdict == GateVerdict.DEMOTE, f'expected DEMOTE, got {risk.verdict}'
    assert risk.visible_frac < 0.55 and risk.dhash_shift > 14
    return f'vis={risk.visible_frac} shift={risk.dhash_shift}'


# R2: viz3 malformed chart -> deterministic BLOCK via G2 + G8
def R2():
    p = fixture('viz3_bandwidth_gap.png')
    idx = build_content_index([p])
    a = AssetRef(material_id='viz3', path=p, beat_id='S20-B01', asset_type='CHART',
                 namespace='exp225', artifact_status='experimental', production_authorized=False)
    rep = evaluate_asset(a, IntegrityGateConfig(content_index=idx))
    gates = {r.gate: r for r in rep.results}
    assert gates['G2'].verdict == GateVerdict.BLOCK, 'viz3 1011x512 must BLOCK on G2'
    assert gates['G8'].verdict == GateVerdict.BLOCK, 'viz3 must BLOCK on G8 (experiment)'
    assert gates['G6'].verdict in (GateVerdict.DEMOTE, GateVerdict.ADVISORY)
    assert rep.final == GateVerdict.BLOCK
    return 'G2+G8 BLOCK, G6 advisory/demote'


# R3: NullSpace extreme aspect -> G3 DEMOTE (contain), not BLOCK
def R3():
    p = fixture('r2_S10-B02_4.img.jpg')
    idx = build_content_index([p])
    a = AssetRef(material_id='ns', path=p, beat_id='S10-B02', asset_type='PHOTO',
                 namespace='fixtures', artifact_status='production', production_authorized=True)
    rep = evaluate_asset(a, IntegrityGateConfig(content_index=idx,
                                                provenance={'ns': {'beat': 'S10-B02', 'title': 'NullSpace VR Mk 2', 'url': 'x'}}))
    g3 = next(r for r in rep.results if r.gate == 'G3')
    assert g3.verdict == GateVerdict.DEMOTE and 'force_contain' in g3.reason
    assert rep.final == GateVerdict.DEMOTE
    return 'AR 0.688 -> DEMOTE contain'


# R4: 3 byte-identical material pairs -> merge to 3 contents; second occurrence G4 BLOCK
def R4():
    pairs = [('r2_S10-B01_4.img.jpg', 'r2_S10-B02_4.img.jpg'),
             ('r2_S11-B01_2.img.jpg', 'r2_S11-B02_3.img.jpg'),
             ('r2_S16-B03_2.img.jpg', 'r2_S18-B01_3.img.jpg')]
    paths = [fixture(n) for pr in pairs for n in pr]
    idx = build_content_index(paths)
    for a, b in pairs:
        assert idx.content_id(fixture(a)) == idx.content_id(fixture(b)), f'{a}~{b} must share content'
    assert len(idx.members) == 3, f'6 files must cluster into 3 contents, got {len(idx.members)}'
    blocked = 0
    for pr in pairs:
        cid = idx.content_id(fixture(pr[0]))
        a = AssetRef(material_id='x', path=fixture(pr[1]), beat_id='T', asset_type='PHOTO',
                     namespace='fixtures', artifact_status='production', production_authorized=True)
        # candidate stage (nothing displayed): G4 passes, twin noted
        rep0 = evaluate_asset(a, IntegrityGateConfig(content_index=idx))
        g40 = next(r for r in rep0.results if r.gate == 'G4')
        assert g40.verdict == GateVerdict.PASS, 'candidate stage must not block pool twins'
        # display stage (content already shown): G4 BLOCK safety net
        rep = evaluate_asset(a, IntegrityGateConfig(content_index=idx, displayed_contents={cid}))
        g4 = next(r for r in rep.results if r.gate == 'G4')
        assert g4.verdict == GateVerdict.BLOCK
        blocked += 1
    return f'3 contents merged; {blocked} display-level G4 BLOCKs; candidate-level advisory'


# R5: S29 A?A pattern (two non-evidence beats flanking one evidence beat) -> no A?A in decisions
def R5():
    pe = fixture('r2_S30-B02_3.img.jpg')
    po = fixture('r2_S02-B02_0.img.jpg')
    pf = fixture('r2_S25-B01_0.img.jpg')
    pg = fixture('r2_S11-B01_2.img.jpg')
    beats = [
        _beat('S29-B01', 'EVIDENCE', 4, 360, 365, [_cand('m_e1', 'CE', po)]),
        _beat('S29-B02', 'EVIDENCE', 4, 365, 370, [_cand('m_e2', 'CE', pe)]),  # same content only -> falls back
        _beat('S29-B03', 'HN', 4, 370, 375, []),
        _beat('S29-B04', 'HN', 4, 375, 380, []),
        _beat('S30-B02', 'EVIDENCE', 4, 380, 385, [_cand('m_e3', 'CE', pe)]),
        _beat('S31-B01', 'EVIDENCE', 4, 600, 605, [_cand('m_f', 'CF', pf)]),
        _beat('S31-B02', 'EVIDENCE', 4, 605, 610, [_cand('m_g', 'CG', pg)]),
    ]
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=60.0))
    starts = {b.beat_id: b.start for b in beats}
    seq = sorted([(d.beat_id, d.content_id) for d in r['decisions']], key=lambda x: starts[x[0]])
    contents = [c for _, c in seq]
    a2 = sum(1 for i in range(len(contents) - 2)
             if contents[i] == contents[i + 2] and not contents[i].startswith('BLANK'))
    assert a2 == 0, f'A?A pattern present: {seq}'
    adj = sum(1 for i in range(len(contents) - 1) if contents[i] == contents[i + 1])
    assert adj == 0, f'adjacent same present: {seq}'
    return f'seq={seq}'


# R6: Run02 ABAB window (chart/photo/chart/photo) -> policy must not reproduce ABAB
def R6():
    pchart = fixture('viz2_five_level_ladder.png')
    pphoto = fixture('r2_S02-B02_0.img.jpg')
    pglove = fixture('r2_S11-B01_2.img.jpg')
    beats = [
        _beat('S02-B01', 'VIZ', 1, 17.3, 21.7, [_cand('viz2', 'V2', pchart)]),
        _beat('S02-B02', 'EVIDENCE', 1, 21.7, 25.6, [_cand('ph', 'PH', pphoto)]),
        _beat('S02-B03', 'VIZ', 1, 25.6, 30.5, [_cand('viz2b', 'V2', pchart)]),   # same chart, same chapter
        _beat('S02-B04', 'HN', 1, 30.5, 35.2, []),
        _beat('S03-B01', 'EVIDENCE', 1, 100, 105, [_cand('gl', 'GL', pglove)]),
    ]
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=60.0))
    contents = [d.content_id for d in r['decisions']]
    abab = sum(1 for i in range(len(contents) - 3)
               if contents[i] == contents[i + 2] and contents[i + 1] == contents[i + 3]
               and contents[i] != contents[i + 1])
    assert abab == 0, f'ABAB reproduced: {contents}'
    d = {x.beat_id: x for x in r['decisions']}
    assert d['S02-B03'].action != DisplayKind.VIZ or d['S02-B03'].content_id != 'V2', \
        'same-chapter chart reuse must cascade'
    return f'contents={contents}'


# R7: stage22 exp225 namespace leakage -> hard BLOCK, never warning
def R7():
    pol = NamespacePolicy(run_namespace='c:/run/prod02')
    r = check_namespace('c:/run/output/stage22_visual_quality/exp225/viz/viz3_bandwidth_gap.png', pol)
    assert r['verdict'] == 'BLOCK' and any('experimental_marker' in x for x in r['reasons'])
    r2 = check_namespace('c:/run/prod02/asset_cache/files/r2_S01-B01_2.img.jpg', pol)
    assert r2['verdict'] == 'PASS'
    return 'exp path BLOCK / own namespace PASS'


# R8: S33B narrative anchor callback — without registration: no silent repeat; with registration: legal +1
def R8():
    plad = fixture('viz2_five_level_ladder.png')
    po = fixture('r2_S02-B02_0.img.jpg')
    palt = fixture('r2_S25-B01_0.img.jpg')
    pf = fixture('r2_S11-B01_2.img.jpg')
    beats = [
        _beat('S02-B01', 'VIZ', 1, 17.3, 21.7, [_cand('v_a', 'LAD', plad), _cand('v_alt', 'ALT', palt)]),
        _beat('SP1', 'EVIDENCE', 3, 200, 205, [_cand('sp1', 'SP', po)]),
        _beat('S33B-B01', 'VIZ', 5, 511.7, 515.4, [_cand('v_b', 'LAD', plad), _cand('v_alt2', 'ALT2', pf)]),
        _beat('S33B-B02', 'VIZ', 5, 515.4, 521.2, [_cand('v_c', 'LAD', plad), _cand('v_alt3', 'ALT3', po)]),
    ]
    # strict: no callback registered -> same-chapter LAD reuse must cascade (pool switch), no silent repeat
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=1.0))
    d = {x.beat_id: x for x in r['decisions']}
    assert d['S02-B01'].content_id == 'LAD'
    assert d['S33B-B01'].content_id != 'LAD' or d['S33B-B01'].action == DisplayKind.BORROW, \
        'unregistered reuse must cascade'
    # registered: LAD is anchor callback of S02-B01 -> S33B-B01 may reuse once (>=60s satisfied)
    beats2 = [
        _beat('S02-B01', 'VIZ', 1, 17.3, 21.7, [_cand('v_a', 'LAD', plad)]),
        _beat('SP1', 'EVIDENCE', 3, 200, 205, [_cand('sp1', 'SP', po)]),
        _beat('S33B-B01', 'VIZ', 5, 511.7, 515.4, [_cand('v_b', 'LAD', plad)]),
    ]
    r2 = run_reuse_policy(beats2, ReusePolicyConfig(min_display_gap_s=1.0, callbacks={'LAD': 'S02-B01'}))
    d2 = {x.beat_id: x for x in r2['decisions']}
    assert d2['S33B-B01'].action in (DisplayKind.ANCHOR_CALLBACK, DisplayKind.VIZ), \
        f'registered callback must allow legal reuse, got {d2["S33B-B01"].action}'
    assert r2['ledger'].use_count('LAD') == 2
    return 'strict: cascade; registered: legal +1 (ledger=2)'


def run_all() -> bool:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('R') and k[1].isdigit() and callable(v)]
    ok = True
    for name, fn in tests:
        try:
            msg = fn()
            RESULTS.append((name, 'PASS', msg))
            print(f'  PASS {name}: {msg}')
        except AssertionError as ex:
            ok = False
            RESULTS.append((name, 'FAIL', str(ex)))
            print(f'  FAIL {name}: {ex}')
        except Exception as ex:  # noqa: BLE001
            ok = False
            RESULTS.append((name, 'ERROR', repr(ex)))
            print(f'  ERROR {name}: {ex!r}')
    print(f'regression fixtures: {sum(1 for _, s, _ in RESULTS if s == "PASS")}/{len(RESULTS)} PASS')
    return ok


if __name__ == '__main__':
    sys.exit(0 if run_all() else 1)
