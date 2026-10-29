# -*- coding: utf-8 -*-
"""5-J Final Gate tests: mm-review-confirm append-only decision records."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from video_studio.ops.mm_review_confirm import run_mm_review_confirm

RESULTS = []


def _setup(tmp):
    """Create minimal test env: decisions file + fake judge/truth files."""
    dp = Path(tmp) / 'decisions.json'
    jp = Path(tmp) / 'judge.json'
    tp = Path(tmp) / 'truth.json'
    jp.write_text('{"schema":"test"}', encoding='utf-8')
    tp.write_text('{"schema":"test"}', encoding='utf-8')
    return dp, jp, tp


def _write_decisions(dp, decisions):
    dp.write_text(json.dumps(decisions, ensure_ascii=False), encoding='utf-8')


def _dec(scene='S06', cid='T02', decision='accept', **kw):
    d = {'scene_id': scene, 'case_id': cid, 'decision': decision}
    d.update(kw)
    return d


T_accept = lambda tmp: _test_decision_type(tmp, 'accept')
T_replace = lambda tmp: _test_decision_type(tmp, 'replace', replacement_asset_id='a_123')
T_keep_unknown = lambda tmp: _test_decision_type(tmp, 'keep_unknown')

def _test_decision_type(tmp, decision, **kw):
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [_dec(decision=decision, **kw)])
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path=str(jp),
                              truth_set_path=str(tp), decided_by='tester')
    assert r.get('ok') is True, r
    assert r.get('appended') == 1
    # verify file
    lines = Path(r['decisions_file']).read_text(encoding='utf-8').strip().split('\n')
    rec = json.loads(lines[0])
    assert rec['decision'] == decision
    assert rec['decided_by'] == 'tester'
    assert 'input_fingerprint' in rec
    assert 'decision_id' in rec


def _test_append_only(tmp):
    """Two runs: second run appends, first run's lines unchanged."""
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [_dec(decision='accept')])
    r1 = run_mm_review_confirm(db_path=':memory:', project_id='test',
                               decisions_path=str(dp), judge_json_path=str(jp),
                               truth_set_path=str(tp), decided_by='test1')
    f = Path(r1['decisions_file'])
    lines1 = f.read_text(encoding='utf-8').strip().split('\n')
    # second run
    _write_decisions(dp, [_dec(decision='replace', replacement_asset_id='a_new')])
    r2 = run_mm_review_confirm(db_path=':memory:', project_id='test2',
                               decisions_path=str(dp), judge_json_path=str(jp),
                               truth_set_path=str(tp), decided_by='test2')
    lines2 = f.read_text(encoding='utf-8').strip().split('\n')
    assert len(lines2) > len(lines1), 'append should increase line count'
    # first run's lines must be unchanged (append-only)
    for i, ln in enumerate(lines1):
        assert lines2[i] == ln, f'line {i} changed'


def _test_fail_closed_missing_field(tmp):
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [{'scene_id': 'S06'}])  # missing case_id and decision
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path=str(jp),
                              truth_set_path=str(tp), decided_by='test')
    assert r.get('ok') is False and 'validation failed' in r.get('error', '')


def _test_fail_closed_invalid_decision(tmp):
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [_dec(decision='auto_replace')])
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path=str(jp),
                              truth_set_path=str(tp), decided_by='test')
    assert r.get('ok') is False


def _test_fail_closed_replace_no_candidate(tmp):
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [_dec(decision='replace')])  # missing replacement_asset_id
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path=str(jp),
                              truth_set_path=str(tp), decided_by='test')
    assert r.get('ok') is False


def _test_keep_unknown_not_accept(tmp):
    """keep_unknown must not be treated as accept (semantically distinct)."""
    dp, jp, tp = _setup(tmp)
    _write_decisions(dp, [_dec(decision='keep_unknown')])
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path=str(jp),
                              truth_set_path=str(tp), decided_by='test')
    f = Path(r['decisions_file'])
    rec = json.loads(f.read_text(encoding='utf-8').strip())
    assert rec['decision'] == 'keep_unknown'
    assert rec['decision'] != 'accept'


def _test_fail_closed_no_judge(tmp):
    dp, jp, tp = _setup(tmp)
    r = run_mm_review_confirm(db_path=':memory:', project_id='test',
                              decisions_path=str(dp), judge_json_path='nonexistent.json',
                              truth_set_path=str(tp), decided_by='test')
    assert r.get('ok') is False


def run_all():
    import tempfile
    tests = [(k, v) for k, v in sorted(globals().items())
             if callable(v) and (k.startswith('T_') or k.startswith('_test_'))]
    ok = True
    for name, fn in tests:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(tmp)
                print(f'  PASS {name}')
            except Exception as ex:
                ok = False
                print(f'  FAIL {name}: {ex!r}')
    print(f'mm-review-confirm tests: {sum(1 for _, s, _ in RESULTS if s == "PASS")}/{len(RESULTS)} PASS')
    return ok
