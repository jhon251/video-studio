"""Phase 2-D 单测（免费、确定性）：Provider 契约 + 下载/校验边界 + 许可证 + 安全资源限制 + 10 类故障。

不访问网络：传输层用可编程的假 transport；文件用真实图片/真实损坏文件，校验走真实 ffprobe/ffmpeg/PIL。

覆盖：
  A. local_ingest 兼容实现（与旧链路同分同序，不复制不下载）
  B. Provider 契约：标准化字段完整、provider/source/license/sha256/bytes 可追溯
  C. 10 类故障：超时 / 404 / 500 / 空响应 / 文件损坏 / 非媒体伪装 / 超大小 / 缺许可证 /
     路径穿越·危险文件名 / ffprobe 或解码失败
  D. 安全与资源：大小上限、并发上限、重复下载去重、缓存上限、可执行扩展名拒绝、不执行下载内容
  E. 失败可降级：外部失败不影响本地候选；外部候选仍走 Phase 2-C 分类学

用法：python tests/material_provider_test.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import (DEFAULT_POLICY, LocalCatalogProvider,  # noqa: E402
                                                 LocalIngestProvider, MaterialQuery,
                                                 ProviderCandidate, TransportError,
                                                 UrllibTransport, fetch_many,
                                                 provider_from_config, safe_filename,
                                                 sniff_media_type, verify_material)

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
WORK = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\provider_test")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def cfg():
    return {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}


def make_ctx(project_dir: Path):
    return ToolContext(role="retrieval", project_id="p_test", project_dir=project_dir,
                       db=None, config=cfg())


def prep():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "media").mkdir(parents=True, exist_ok=True)
    (WORK / "catalog").mkdir(parents=True, exist_ok=True)
    return make_ctx(WORK)


class FakeTransport:
    """可编程假传输：按 URL 返回预置响应或抛出预置错误。"""

    def __init__(self, plan: dict):
        self.plan = plan
        self.calls = []

    def get(self, url, max_bytes, timeout_s):
        self.calls.append(url)
        r = self.plan.get(url)
        if r is None:
            raise TransportError("PROVIDER_HTTP_404", "no plan for {}".format(url))
        if isinstance(r, TransportError):
            raise r
        if isinstance(r, tuple):
            kind, payload = r
            if kind == "bytes":
                if len(payload) > max_bytes:
                    raise TransportError("ASSET_OVERSIZE", ">{}".format(max_bytes))
                if not payload:
                    raise TransportError("PROVIDER_EMPTY_RESPONSE", "0 字节响应")
                return payload
        raise TransportError("PROVIDER_DOWNLOAD_FAILED", "bad plan")


def write_catalog(items, sub="catalog"):
    d = WORK / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / "catalogue.json").write_text(json.dumps({"items": items}, ensure_ascii=False),
                                      encoding="utf-8")
    return d


def provider_for(items, policy=None, transport=None, sub="catalog"):
    pol = {**DEFAULT_POLICY, "provider": "local_catalog", **(policy or {})}
    d = write_catalog(items, sub)
    return LocalCatalogProvider(pol, transport=transport, catalog_dir=d)


KW = {"皮肤", "界面", "截图", "鲸鱼", "娘"}


def query(text="皮肤界面截图展示鲸鱼娘皮肤。"):
    from video_studio.agents.retrieval.agent import kw_tokens
    return MaterialQuery(text=text, keywords=kw_tokens(text))


# ---------------- A. local_ingest 兼容实现 ----------------
ctx = prep()
media = WORK / "media"
shutil.copy2(REAL_JPG, media / "皮肤界面截图_01.jpg")
sha_local = hashlib.sha256((media / "皮肤界面截图_01.jpg").read_bytes()).hexdigest()
index_files = [{"path": "皮肤界面截图_01.jpg", "name": "皮肤界面截图_01.jpg", "ext": ".jpg",
                "size": (media / "皮肤界面截图_01.jpg").stat().st_size, "sha256": sha_local[:16],
                "license": "unchecked"}]
ctx.inputs = {"index_files": index_files}                     # type: ignore[attr-defined]
lp = LocalIngestProvider({**DEFAULT_POLICY, "license_required": False})
found = lp.search(query(), ctx)
check("A1 local_ingest provider 能检索到本地素材", len(found) == 1 and found[0].name.endswith(".jpg"),
      [c.name for c in found])
lp2 = LocalIngestProvider({**DEFAULT_POLICY, "license_required": False})
fetched = lp2.fetch(found, ctx)
check("A2 local_ingest 就地校验通过（不下载不复制）",
      fetched[0].status == "VERIFIED" and fetched[0].download_status == "ALREADY_LOCAL"
      and fetched[0].downloaded_path == "皮肤界面截图_01.jpg", fetched[0].status)
check("A3 local_ingest 记录 sha256/bytes/media_type/probe",
      fetched[0].sha256 == sha_local and fetched[0].bytes > 0
      and fetched[0].media_type == "jpeg" and fetched[0].probe_result, fetched[0].to_record())
from video_studio.agents.retrieval.agent import kw_tokens, score  # noqa: E402
legacy = score("皮肤界面截图_01.jpg .jpg", kw_tokens(query().text))
check("A4 provider 打分与旧链路一致（兼容实现）", found[0].match_score == legacy,
      "{} vs {}".format(found[0].match_score, legacy))

# ---------------- B. Provider 契约 ----------------
ctx = prep()
p = provider_for([{"source_id": "ext-1", "name": "皮肤界面截图_ext.jpg", "file": str(REAL_JPG),
                   "license": "CC BY 4.0", "attribution": "Example Studio",
                   "usage_restrictions": "需署名"}])
found = p.search(query(), ctx)
check("B1 外部 provider 返回候选", len(found) == 1, [c.name for c in found])
got = p.fetch(found, ctx)[0]
need = {"provider", "source_id", "source_url", "name", "ext", "license", "attribution",
        "usage_restrictions", "bytes", "sha256", "downloaded_path", "download_status",
        "probe_result", "decodable", "status", "error_code", "needs_hitl", "license_cleared"}
check("B2 标准化字段完整", need <= set(got.to_record()), sorted(need - set(got.to_record())))
check("B3 校验通过且落盘到内容寻址路径",
      got.status == "VERIFIED" and got.download_status == "DOWNLOADED"
      and got.downloaded_path.startswith("external/") and got.downloaded_path.endswith(".jpg"),
      got.downloaded_path)
check("B4 provider/source/license/sha256/bytes 可追溯",
      got.provider == "local_catalog" and got.source_id == "ext-1"
      and got.license == "CC BY 4.0" and got.attribution == "Example Studio"
      and got.usage_restrictions == "需署名" and len(got.sha256) == 64 and got.bytes > 0,
      got.to_record())
check("B5 license_cleared=True 时不强推 HITL", got.license_cleared is True and got.needs_hitl is False)
cand = got.to_candidate()
check("B6 转换为现有候选结构（render 直接可用）",
      {"path", "name", "ext", "size", "sha256", "license", "match_score", "matched_tokens"}
      <= set(cand) and cand["provider"] == "local_catalog" and cand["verified"] is True)
check("B7 capabilities 自述限制",
      got and set(p.capabilities()["limits"]) >= {"max_bytes", "timeout_s", "max_retries",
                                                  "max_concurrent_downloads", "max_cache_bytes"})

# ---------------- C1-C4. 传输层故障 ----------------
for label, code, entry in (
        ("C1 下载超时", "PROVIDER_TIMEOUT", {"simulate": "timeout"}),
        ("C2 HTTP 404", "PROVIDER_HTTP_404", {"simulate": "http_404"}),
        ("C3 HTTP 500", "PROVIDER_HTTP_5XX", {"simulate": "http_500"}),
        ("C4 空响应", "PROVIDER_EMPTY_RESPONSE", {"simulate": "empty"})):
    ctx = prep()
    p = provider_for([{"source_id": "f", "name": "皮肤界面截图_x.jpg", "file": str(REAL_JPG),
                       "license": "CC0", **entry}])
    got = p.fetch(p.search(query(), ctx), ctx)[0]
    check("{} → {} 且 REJECTED 且无 downloaded_path".format(label, code),
          got.status == "REJECTED" and got.error_code == code and not got.downloaded_path,
          "{} / {}".format(got.status, got.error_code))

# ---------------- C5. 文件损坏 ----------------
ctx = prep()
broken = WORK / "catalog" / "broken.jpg"
broken.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 400)          # JPEG 头 + 垃圾
p = provider_for([{"source_id": "b", "name": "皮肤界面截图_broken.jpg", "file": str(broken),
                   "license": "CC0"}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C5 文件损坏 → REJECTED + 截断/解码类错误码",
      got.status == "REJECTED" and (got.error_code or "").startswith(
          ("ASSET_TRUNCATED", "ASSET_DECODE_FAILED", "ASSET_PROBE_FAILED",
           "ASSET_FFMPEG_DECODE_FAILED")),
      got.error_code)

# ---------------- C6. 非媒体文件伪装 ----------------
ctx = prep()
fake = WORK / "catalog" / "fake.jpg"
fake.write_text("这不是图片，只是文本，伪装成 jpg。" * 20, encoding="utf-8")
p = provider_for([{"source_id": "n", "name": "皮肤界面截图_fake.jpg", "file": str(fake),
                   "license": "CC0"}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C6 非媒体伪装 → ASSET_TYPE_MISMATCH（不能只看扩展名）",
      got.status == "REJECTED" and got.error_code == "ASSET_TYPE_MISMATCH", got.error_code)

# ---------------- C7. 超过大小限制 ----------------
ctx = prep()
big = WORK / "catalog" / "big.jpg"
shutil.copy2(REAL_JPG, big)
p = provider_for([{"source_id": "big", "name": "皮肤界面截图_big.jpg", "file": str(big),
                   "license": "CC0"}], policy={"max_bytes": 1024})
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C7 超大小上限 → ASSET_OVERSIZE", got.status == "REJECTED"
      and got.error_code == "ASSET_OVERSIZE", got.error_code)

# ---------------- C8. 缺少许可证 ----------------
ctx = prep()
p = provider_for([{"source_id": "nol", "name": "皮肤界面截图_nol.jpg", "file": str(REAL_JPG)}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C8 缺许可证 → ASSET_LICENSE_MISSING + REJECTED + needs_hitl",
      got.status == "REJECTED" and got.error_code == "ASSET_LICENSE_MISSING"
      and got.needs_hitl is True and got.license_cleared is False,
      "{} / hitl={}".format(got.error_code, got.needs_hitl))
ctx = prep()
p = provider_for([{"source_id": "unk", "name": "皮肤界面截图_unk.jpg", "file": str(REAL_JPG),
                   "license": "unknown"}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C8b 许可证不明确（unknown）→ ASSET_LICENSE_UNCLEAR + needs_hitl",
      got.status == "REJECTED" and got.error_code == "ASSET_LICENSE_UNCLEAR"
      and got.needs_hitl is True, got.error_code)

# ---------------- C9. 路径穿越 / 危险文件名 ----------------
for name, why in (("../etc/passwd.jpg", "路径穿越"), ("a/b.jpg", "子路径"),
                  ("skin.jpg.exe", "可执行扩展名"), ("CON.jpg", "保留设备名"),
                  ("bad\x00.jpg", "控制字符"), ("x" * 200 + ".jpg", "超长")):
    ok, cleaned, err = safe_filename(name)
    check("C9 危险文件名被拒：{}（{}）".format(why, name[:24]),
          (not ok) and err == "ASSET_DANGEROUS_FILENAME", err)
ok, _, err = safe_filename("皮肤界面截图_01.jpg")
check("C9b 正常文件名通过", ok and err is None)
ctx = prep()
p = provider_for([{"source_id": "evil", "name": "../皮肤界面截图_evil.jpg", "file": str(REAL_JPG),
                   "license": "CC0"}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C9c provider 层拒绝危险文件名且未落盘",
      got.status == "REJECTED" and got.error_code == "ASSET_DANGEROUS_FILENAME"
      and not (WORK / "media" / "external" / "皮肤界面截图_evil.jpg").exists(), got.error_code)
check("C9c2 媒体目录未被写入任何外部文件（危险名未落盘）",
      not any((WORK / "media" / "external").glob("*")) if (WORK / "media" / "external").is_dir()
      else True)
ok, _, err = safe_filename("skin.exe")
check("C9d 可执行扩展名被拒", not ok and err == "ASSET_DANGEROUS_FILENAME")

# ---------------- C10. ffprobe / 解码失败 ----------------
ctx = prep()
trunc = WORK / "catalog" / "trunc.jpg"
trunc.write_bytes(REAL_JPG.read_bytes()[:2048])
p = provider_for([{"source_id": "t", "name": "皮肤界面截图_trunc.jpg", "file": str(trunc),
                   "license": "CC0"}])
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("C10 截断文件 → 被截断/探测/解码边界拦下（明确错误码）",
      got.status == "REJECTED" and (got.error_code or "").startswith(
          ("ASSET_TRUNCATED", "ASSET_DECODE_FAILED", "ASSET_PROBE_FAILED",
           "ASSET_FFMPEG_DECODE_FAILED")),
      got.error_code)
ok, err = sniff_media_type(trunc)
check("C10b magic bytes 判定与实际类型一致（不看扩展名）",
      (ok == "jpeg" and err is None) or err == "ASSET_TYPE_MISMATCH", (ok, err))

# ---------------- D. 安全与资源限制 ----------------
pol = {**DEFAULT_POLICY, "provider": "local_catalog"}
tr = FakeTransport({"https://x/a.jpg": ("bytes", REAL_JPG.read_bytes())})
ctx = prep()
p = provider_for([{"source_id": "u1", "name": "皮肤界面截图_u1.jpg", "url": "https://x/a.jpg",
                   "license": "CC0"}], transport=tr)
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("D1 HTTPS 下载后照常校验通过", got.status == "VERIFIED", got.error_code)
sha = got.sha256
cached = WORK / "media" / "external" / (sha + ".jpg")
check("D1b 落盘为内容寻址缓存（sha256 命名）", cached.is_file(), str(cached.name))
calls_before = len(tr.calls)
# 同一项目目录再跑一次：内容寻址缓存命中 → **不再触发传输层下载**
p2 = provider_for([{"source_id": "u1", "name": "皮肤界面截图_u1.jpg", "url": "https://x/a.jpg",
                    "license": "CC0"}], transport=tr)
got2 = p2.fetch(p2.search(query(), ctx), ctx)[0]
check("D2 同 sha256 不重复下载（缓存命中，传输层 0 次调用）",
      got2.status == "VERIFIED" and len(tr.calls) == calls_before, "calls={}".format(len(tr.calls)))
check("D2b 缓存命中计数", p2.stats["cache_hits"] >= 1, p2.stats)
ctx = prep()
pol_http = {**DEFAULT_POLICY, "require_https": True}
t = UrllibTransport(pol_http)
try:
    t.get("http://insecure/x.jpg", 1024, 1)
    check("D3 非 HTTPS 被拒", False, "未抛错")
except TransportError as exc:
    check("D3 非 HTTPS 被拒（require_https）", exc.code == "PROVIDER_HTTP_ERROR", exc.code)
ctx = prep()
p = provider_for([{"source_id": i, "name": "皮肤界面截图_{}.jpg".format(i), "file": str(REAL_JPG),
                   "license": "CC0"} for i in range(4)], transport=FakeTransport({}))
found = p.search(query(), ctx)
check("D4 search+fetch 多候选", len(found) >= 1, len(found))
got_all = fetch_many(p, found, ctx)
check("D4b 并发上限参数生效（并发=2）", p.policy["max_concurrent_downloads"] == 2
      and all(c.status == "VERIFIED" for c in got_all), [c.status for c in got_all])
ctx = prep()
cache_dir = WORK / "media" / "external"
cache_dir.mkdir(parents=True, exist_ok=True)
(cache_dir / "seed.bin").write_bytes(b"x" * 4096)          # 预置缓存已超限
p = provider_for([{"source_id": "c", "name": "皮肤界面截图_c.jpg", "file": str(REAL_JPG),
                   "license": "CC0"}], policy={"max_cache_bytes": 1})
got = p.fetch(p.search(query(), ctx), ctx)[0]
check("D5 缓存超限 → PROVIDER_CACHE_LIMIT（不做静默淘汰）",
      got.status == "REJECTED" and got.error_code == "PROVIDER_CACHE_LIMIT", got.error_code)
check("D5b 超限时不落盘新文件（仅预置文件）",
      sorted(f.name for f in cache_dir.glob("*")) == ["seed.bin"],
      sorted(f.name for f in cache_dir.glob("*")))
check("D6 下载内容从不执行（只读解析：无 exec/subprocess shell）",
      "shell=True" not in Path(ROOT / "src/video_studio/tools/material_provider.py").read_text(
          encoding="utf-8"))

# ---------------- E. 工厂与降级 ----------------
prov, err, pol = provider_from_config({"tools": {"image": {"provider": "none"}}})
check("E1 provider=none → 无 provider（现有行为不变）", prov is None and err is None)
prov, err, pol = provider_from_config({"tools": {"material": {"provider": "local_catalog",
                                                              "catalog": str(WORK / "catalog")}}})
check("E2 tools.material.provider 生效", prov is not None and prov.name == "local_catalog")
prov, err, pol = provider_from_config({"tools": {"image": {"provider": "unknown_thing"}}})
check("E3 未注册 provider → PROVIDER_UNKNOWN（不伪造候选）", prov is None
      and err == "PROVIDER_UNKNOWN")
prov, err, pol = provider_from_config({"tools": {"image": {"provider": "local_ingest"}}})
check("E4 既有 image.provider 开关可指向 local_ingest 兼容实现",
      prov is not None and prov.name == "local_ingest")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
