"""One-time fixture builder: copies the real Run02 anomaly assets (READ-ONLY
source) into the test fixture directory so regression tests are hermetic.

Run once:  python -m video_studio.orchestration.tests.make_fixtures
Also generates small synthetic images for unit tests.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r'C:\mp4agent\video-studio')
SRC = ROOT / 'output/prod02/asset_cache/files'
VIZ = ROOT / 'output/stage22_visual_quality/exp225/viz'
FIX = Path(__file__).parent / 'fixtures'

PHOTOS = [
    'r2_S10-B02_4.img.jpg',   # NullSpace portrait 0.688 (R1 crop / R3 aspect)
    'r2_S10-B01_4.img.jpg',   # byte-dup twin (R4)
    'r2_S11-B01_2.img.jpg',   # byte-dup group 2 (R4)
    'r2_S11-B02_3.img.jpg',   # byte-dup group 2 twin (R4)
    'r2_S16-B03_2.img.jpg',   # byte-dup group 3 (R4)
    'r2_S18-B01_3.img.jpg',   # byte-dup group 3 twin (R4)
    'r2_S25-B01_0.img.jpg',   # UI screenshot (G5 true positive)
    'r2_S09-B02_4.img.jpg',   # grayscale micrograph (G7 advisory false-positive sample)
    'r2_S30-B02_3.img.jpg',   # EEG cap photo (S29 A?A source, R5)
    'r2_S02-B02_0.img.jpg',   # ABAB window photo (R6)
]
CHARTS = ['viz2_five_level_ladder.png', 'viz3_bandwidth_gap.png']  # R2/R7

SYNTH = {   # small deterministic synthetic photos for unit tests
    'syn_landscape.jpg': (1280, 720, 10),
    'syn_portrait.jpg': (720, 1280, 11),
    'syn_lowres.jpg': (400, 300, 12),
    'syn_a.jpg': (960, 540, 13),
    'syn_b.jpg': (960, 540, 14),
}


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    copied = []
    for n in PHOTOS:
        s = SRC / n
        if not s.exists():
            print('MISSING source', s)
            return 1
        shutil.copy2(s, FIX / n)
        copied.append(n)
    for n in CHARTS:
        s = VIZ / n
        if not s.exists():
            print('MISSING source', s)
            return 1
        shutil.copy2(s, FIX / n)
        copied.append(n)
    for name, (w, h, seed) in SYNTH.items():
        rng = np.random.default_rng(seed)
        arr = (rng.random((h, w, 3)) * 255).astype('uint8')
        Image.fromarray(arr).save(FIX / name, quality=90)
        copied.append(name)
    print('fixtures ready:', len(copied))
    return 0


if __name__ == '__main__':
    sys.exit(main())
