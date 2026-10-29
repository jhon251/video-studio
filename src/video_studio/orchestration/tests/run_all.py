"""Test runner: fixtures -> unit tests -> regression R1-R8."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))


def main() -> int:
    from video_studio.orchestration.tests import make_fixtures
    print('== fixtures ==')
    if make_fixtures.main() != 0:
        return 1
    print('== unit tests ==')
    from video_studio.orchestration.tests import test_units
    ok1 = test_units.run_all()
    print('== regression fixtures R1-R8 ==')
    from video_studio.orchestration.tests import test_regression_R1_R8 as reg
    ok2 = reg.run_all()
    print('== TOTAL:', 'PASS' if (ok1 and ok2) else 'FAIL', '==')
    return 0 if (ok1 and ok2) else 1


if __name__ == '__main__':
    sys.exit(main())
