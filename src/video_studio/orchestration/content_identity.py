"""Content identity: MD5 -> dHash perceptual clustering.

Deterministic content clustering over asset files. Identity is NEVER
material_id or filepath. Byte-equal files merge first; then perceptual
dHash distance merges (<=same_band, 7..10 suspect band controlled by config).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


def md5_of(path: str | Path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def dhash_arr(gray: np.ndarray, size: int = 8) -> np.ndarray:
    """dHash bits from an already-loaded grayscale ndarray (usable on crops)."""
    im = Image.fromarray(gray).resize((size + 1, size), Image.LANCZOS)
    px = np.asarray(im, dtype=int)
    return (px[:, :-1] > px[:, 1:]).flatten()


def dhash_of(path: str | Path, size: int = 8) -> np.ndarray:
    g = np.asarray(Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS), dtype=int)
    return (g[:, :-1] > g[:, 1:]).flatten()


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int((a != b).sum())


@dataclass
class ContentIndex:
    """path -> content cluster mapping plus cluster membership."""
    cluster_of_path: dict = field(default_factory=dict)     # path -> content_id
    members: dict = field(default_factory=dict)             # content_id -> [paths]
    md5_of: dict = field(default_factory=dict)
    suspect_links: list = field(default_factory=list)       # (path_a, path_b, dist)
    same_band: int = 6
    suspect_band: int = 10

    def content_id(self, path: str) -> str:
        return self.cluster_of_path[path]

    def all_content_ids(self) -> list:
        return sorted(self.members.keys())


def build_content_index(paths: list, same_band: int = 6, suspect_band: int = 10,
                        merge_suspect: bool = False, _dh=None, _md5=None) -> ContentIndex:
    """Cluster files into content identities.

    Deterministic: files sorted first; MD5 equality merges; then dHash bands.
    `_dh`/`_md5` injectable for tests (synthetic images without disk).
    """
    ps = sorted(str(p) for p in paths)
    idx = ContentIndex(same_band=same_band, suspect_band=suspect_band)
    idx.md5_of = {p: (_md5[p] if _md5 and p in _md5 else md5_of(p)) for p in ps}
    H = {p: (_dh[p] if _dh and p in _dh else dhash_of(p)) for p in ps}

    parent = {p: p for p in ps}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_md5 = {}
    for p in ps:
        by_md5.setdefault(idx.md5_of[p], []).append(p)
    for g in by_md5.values():
        for p in g[1:]:
            union(g[0], p)

    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            if find(a) == find(b):
                continue
            d = hamming(H[a], H[b])
            if d <= same_band:
                union(a, b)
            elif d <= suspect_band:
                idx.suspect_links.append((a, b, d))
                if merge_suspect:
                    union(a, b)

    n = 0
    for p in ps:
        r = find(p)
        if r not in idx.members:
            n += 1
            idx.members[r] = []
    rename = {r: f"C{n + 1 + i:03d}" for i, r in enumerate(sorted(idx.members))}
    idx.members = {rename[r]: ps_ for r, ps_ in idx.members.items()}
    for p in ps:
        idx.cluster_of_path[p] = rename[find(p)]
        idx.members[rename[find(p)]].append(p)
    for r in idx.members:
        idx.members[r] = sorted(idx.members[r])
    return idx
