"""Unit tests for the Visual Orchestration Layer (plain-assert runner)."""
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[3]))
from video_studio.orchestration import (
    AssetRef, BeatSpec, Candidate, CropLayout, ContentIndex,
    IntegrityGateConfig, NamespacePolicy, ReusePolicyConfig,
    build_content_index, check_namespace, evaluate_asset, evaluate_crop,
    run_reuse_policy, GateVerdict, DisplayKind,
)
from video_studio.orchestration.global_reuse_policy import b2_beatid  # noqa: F401  (import stability)
FIX = Path(__file__).parent / 'fixtures'
RESULTS = []


def img(w, h, seed, tmp):
    rng = np.random.default_rng(seed)
    p = Path(tmp) / f'u_{w}x{h}_{seed}.jpg'
    if not p.exists():
        Image.fromarray((rng.random((h, w, 3)) * 255).astype('uint8')).save(p, quality=90)
    return str(p)


def test_content_identity_merges_md5_dups(tmp):
    p1 = img(300, 200, 1, tmp)
    p2 = Path(tmp) / 'u_copy.jpg'
    p2.write_bytes(Path(p1).read_bytes())
    idx = build_content_index([str(p1), str(p2)])
    assert idx.content_id(str(p1)) == idx.content_id(str(p2)), 'md5 dups must merge'
    assert len(idx.members) == 1


def test_content_identity_keeps_distinct(tmp):
    a = img(300, 200, 2, tmp)
    b = img(300, 200, 3, tmp)
    idx = build_content_index([a, b])
    assert idx.content_id(a) != idx.content_id(b), 'distinct random images must not merge'


def test_ledger_counts_and_answers_query(tmp):
    from video_studio.orchestration import GlobalReuseLedger
    from video_studio.orchestration.schemas import DisplayKind
    led = GlobalReuseLedger()
    led.record(content_id='C1', material_id='m1', beat_id='B1', chapter_id=1,
               ts_start=0, ts_end=5, asset_type='PHOTO', function=DisplayKind.EVIDENCE, source='wikimedia')
    led.record(content_id='C1', material_id='m1', beat_id='B5', chapter_id=1,
               ts_start=120, ts_end=125, asset_type='PHOTO', function=DisplayKind.BORROW, source='m1')
    assert led.use_count('C1') == 2
    assert led.borrow_count('C1') == 1
    assert led.min_gap_violation('C1', 59, 65, 60.0) is True     # 59s from first display
    assert led.min_gap_violation('C1', 61, 65, 60.0) is True
    assert not led.min_gap_violation('C1', 200, 205, 60.0)
    rep = led.content_report('C1')
    assert rep['times'] == 2 and rep['functions'] == ['BORROW', 'EVIDENCE']


def _beat(bid, route, ch, s, e, cands):
    return BeatSpec(beat_id=bid, route=route, chapter_id=ch, start=s, end=e, candidates=cands)


def _cand(mid, cid, path, usable='USABLE', fit=0.9, eligible=True):
    return Candidate(material_id=mid, content_id=cid, path=path, eligible=eligible,
                     cv2_usability=usable, cv2_fit=fit)


def test_policy_unique_selection_and_adjacent(tmp):
    pa, pb, pc = img(320, 180, 4, tmp), img(320, 180, 5, tmp), img(320, 180, 6, tmp)
    beats = [
        _beat('B1', 'EVIDENCE', 1, 0, 5, [_cand('m1', 'CA', pa)]),
        _beat('B2', 'EVIDENCE', 1, 5, 10, [_cand('m2', 'CA', pa)]),   # only same content
        _beat('B3', 'EVIDENCE', 1, 10, 15, [_cand('m3', 'CB', pb)]),
        _beat('B4', 'HN', 1, 15, 20, []),
    ]
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=1.0))
    d = {x.beat_id: x for x in r['decisions']}
    assert d['B1'].action == DisplayKind.EVIDENCE and d['B1'].content_id == 'CA'
    assert d['B2'].cls == 'FALLBACK', 'content reuse without callback must not be EVIDENCE'
    assert d['B3'].action == DisplayKind.EVIDENCE


def test_policy_cascade_no_blank_when_borrow_possible(tmp):
    pa, pb = img(320, 180, 7, tmp), img(320, 180, 8, tmp)
    beats = [
        _beat('B1', 'EVIDENCE', 1, 0, 5, [_cand('m1', 'CA', pa)]),
        _beat('B2', 'EVIDENCE', 1, 5, 10, [_cand('m2', 'CA', pa)]),   # falls back
        _beat('B3', 'EVIDENCE', 1, 200, 205, [_cand('m3', 'CB', pb)]),
    ]
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=1.0))
    d = {x.beat_id: x for x in r['decisions']}
    assert d['B2'].cls == 'FALLBACK' and d['B2'].borrow_from == 'B1', 'borrow ledger should serve B2 from B1'
    # 60s gap violated between B1(0-5) and B2(5-10)? B2 start 5 is <60s from B1 -> illegal -> must NOT borrow B1


def test_policy_respects_60s_gap(tmp):
    pa, pb = img(320, 180, 9, tmp), img(320, 180, 10, tmp)
    beats = [
        _beat('B1', 'EVIDENCE', 1, 0, 5, [_cand('m1', 'CA', pa)]),
        _beat('B2', 'EVIDENCE', 1, 5, 10, [_cand('m2', 'CA', pa)]),   # wants CA, 5s later -> illegal
        _beat('B3', 'EVIDENCE', 1, 200, 205, [_cand('m3', 'CB', pb)]),
    ]
    r = run_reuse_policy(beats, ReusePolicyConfig(min_display_gap_s=60.0))
    d = {x.beat_id: x for x in r['decisions']}
    assert not (d['B2'].borrow_from == 'B1'), 'borrow at +5s violates 60s gap'


def test_callback_allows_one_extra(tmp):
    pa, pb = img(320, 180, 14, tmp), img(320, 180, 15, tmp)
    beats = [
        _beat('B1', 'EVIDENCE', 1, 0, 5, [_cand('m1', 'CA', pa)]),
        _beat('BM', 'EVIDENCE', 1, 150, 155, [_cand('mx', 'CB', pb)]),   # spacer: B2 not adjacent to B1
        _beat('B2', 'EVIDENCE', 2, 300, 305, [_cand('m1b', 'CA', pa)]),  # callback to B1
        _beat('B3', 'EVIDENCE', 3, 600, 605, [_cand('m1c', 'CA', pa)]),  # third display -> must not
    ]
    cfg = ReusePolicyConfig(min_display_gap_s=60.0, callbacks={'CA': 'B1'})
    r = run_reuse_policy(beats, cfg)
    d = {x.beat_id: x for x in r['decisions']}
    assert d['B1'].action == DisplayKind.EVIDENCE
    assert d['B2'].action == DisplayKind.ANCHOR_CALLBACK and d['B2'].callback_of == 'B1'
    assert d['B3'].action == DisplayKind.BORROW and d['B3'].cls == 'FALLBACK', 'callback allows only +1'


def test_gate_deterministic_block_and_advisory_only(tmp):
    pl = str(FIX / 'r2_S10-B02_4.img.jpg')
    idx = build_content_index([pl])
    a = AssetRef(material_id='ns', path=pl, beat_id='S10-B02', asset_type='PHOTO',
                 namespace='fixtures', artifact_status='production', production_authorized=True)
    cfg = IntegrityGateConfig(content_index=idx,
                              provenance={'ns': {'beat': 'S10-B02', 'title': 'NullSpace VR Mk 2', 'url': 'x'}})
    rep = evaluate_asset(a, cfg)
    g3 = next(r for r in rep.results if r.gate == 'G3')
    assert g3.verdict == GateVerdict.DEMOTE, 'portrait 0.688 must demote to contain'
    g5 = next(r for r in rep.results if r.gate == 'G5')
    assert g5.verdict in (GateVerdict.ADVISORY, GateVerdict.PASS), 'G5 must never BLOCK/DEMOTE alone'
    # final verdict from deterministic gates only
    assert rep.final in (GateVerdict.PASS, GateVerdict.DEMOTE)


def test_gate_g5_g7_never_sole_block(tmp):
    # texture micrograph: deterministic gates all pass, G7 fires ADVISORY -> final must not be BLOCK
    pl = str(FIX / 'r2_S09-B02_4.img.jpg')
    idx = build_content_index([pl])
    a = AssetRef(material_id='tex', path=pl, beat_id='S09-B02', asset_type='PHOTO',
                 namespace='fixtures', artifact_status='production', production_authorized=True)
    rep = evaluate_asset(a, IntegrityGateConfig(content_index=idx,
                                                provenance={'tex': {'beat': 'S09-B02', 'title': 't', 'url': 'u'}}))
    assert rep.block_gates == [], 'no deterministic gate may block a legal photo'
    assert rep.final != GateVerdict.BLOCK, 'G5/G7 advisory must not produce a standalone BLOCK'


def test_crop_recheck_s10_fixture(tmp):
    pl = str(FIX / 'r2_S10-B02_4.img.jpg')
    risk = evaluate_crop(pl, 'S10-B02', 'ns', layout=CropLayout(fit_mode='cover'))
    assert risk.verdict == GateVerdict.DEMOTE, f'S10 fixture must demote, got {risk.verdict} {risk.reasons}'
    assert risk.visible_frac < 0.55 and risk.dhash_shift > 14


def test_crop_recheck_landscape_pass(tmp):
    pl = str(FIX / 'syn_landscape.jpg')
    risk = evaluate_crop(pl, 'T', 'syn', layout=CropLayout(fit_mode='cover'))
    assert risk.verdict == GateVerdict.PASS and risk.visible_frac == 1.0


def test_namespace_guard_blocks_experiments(tmp):
    pol = NamespacePolicy(run_namespace=str(Path(tmp) / 'prod02'))
    r1 = check_namespace('C:/x/output/stage22_visual_quality/exp225/viz/viz3.png', pol)
    assert r1['verdict'] == 'BLOCK'
    r2 = check_namespace(str(Path(tmp) / 'prod02/asset_cache/files/a.jpg'), pol)
    assert r2['verdict'] == 'PASS'
    r3 = check_namespace(str(Path(tmp) / 'other/a.jpg'), pol)
    assert r3['verdict'] == 'BLOCK'
    r4 = check_namespace('C:/x/output/stage22_visual_quality/exp225/viz/viz3.png',
                         NamespacePolicy(run_namespace='x', allow_registry=frozenset({'C:/x/output/stage22_visual_quality/exp225/viz/viz3.png'})))
    assert r4['verdict'] == 'PASS', 'explicit authorization registry overrides'


def run_all() -> bool:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in tests:
            try:
                fn(tmp)
                RESULTS.append((name, 'PASS', ''))
                print(f'  PASS {name}')
            except AssertionError as ex:
                ok = False
                RESULTS.append((name, 'FAIL', str(ex)))
                print(f'  FAIL {name}: {ex}')
            except Exception as ex:  # noqa: BLE001
                ok = False
                RESULTS.append((name, 'ERROR', repr(ex)))
                print(f'  ERROR {name}: {ex!r}')
    print(f'unit tests: {sum(1 for _, s, _ in RESULTS if s == "PASS")}/{len(RESULTS)} PASS')
    return ok


if __name__ == '__main__':
    sys.exit(0 if run_all() else 1)
