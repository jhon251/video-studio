# -*- coding: utf-8 -*-
"""P14-1：VLM 视觉相关性判定 provider（OpenAI 兼容，**默认关闭**，fail-closed）。

设计依据：PHASE14_REPORT.md §4（冻结设计）。要点逐条对应：
  · OpenAI 兼容 `chat/completions` + 图像输入（本地图 → **确定性降采样：最长边 ≤768px、
    JPEG q80**；参数入 `POLICY` 并注明依据 = 成本控制）；
  · `temperature=0`；JSON 输出 + Schema 校验；超时/重试预算；
  · `PROVIDER_*` fail-closed 错误码（沿用 `tools/material_provider.py` 分类学）；
  · **文件缓存**：键 = `prompt_version|model|image_sha256|need_text_sha256`（命中即 $0 复用）；
  · 输出 `{label: RELEVANT|PARTIAL|IRRELEVANT, reason, confidence}`；
  · **判定独立性**：单次只看一个 (需求, 候选图) 对（不含同景其它候选、不含任何他人结论）；
  · `resolve_config` 三级链（内存 `config.tools.vlm_judge` → `config/vlm_judge.json` → 默认
    `{"enabled": false}`）+ key **只从环境变量**读；
  · 未配置凭据 ⇒ `PROVIDER_NOT_CONFIGURED`（**零伪造**，绝不猜测判定）。

**本模块不接线到任何生产 agent**（P14-3 才做集成，且受 P14-2 硬门约束）。
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- 常量 / 策略
PROMPT_VERSION = "vlm-relevance-judge-v2"
SCHEMA = "vlm-relevance-judgment-v1"

LABELS = ("RELEVANT", "PARTIAL", "IRRELEVANT")
NA = "NOT_ASSESSABLE"

#: fail-closed 错误码（`PROVIDER_*` 分类学，与 material_provider 一致）
ERROR_CODES = (
    "PROVIDER_NOT_CONFIGURED",   # 未启用 / 无 key
    "PROVIDER_TIMEOUT",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_AUTH_FAILED",
    "PROVIDER_HTTP_ERROR",
    "PROVIDER_MALFORMED",        # 响应非 JSON / 结构不符
    "PROVIDER_EMPTY",            # 空响应
    "PROVIDER_OVERSIZE",         # 输入超限（图像/文本）
    "PROVIDER_IMAGE_UNREADABLE",
    "PROVIDER_BUDGET_EXHAUSTED",  # 触达成本/令牌预算
)

DEFAULT_CONFIG = {"enabled": False}

POLICY = {
    "max_image_edge_px": {
        "value": 768,
        "basis": "§4 冻结设计：确定性降采样最长边 ≤768px（成本控制；VLM 判相关性无需原分辨率）"},
    "jpeg_quality": {
        "value": 80,
        "basis": "§4 冻结设计：JPEG q80（成本/保真折中，确定性编码）"},
    "temperature": {
        "value": 0,
        "basis": "§4 冻结设计：temperature=0（同输入同判定，配合缓存可复现）"},
    "max_tokens": {
        "value": 256,
        "basis": "§4 冻结设计：JSON 输出仅需 label/reason/confidence；256 足以避免截断"},
    "timeout_s": {
        "value": 90,
        "basis": "视觉请求含图像上行；90s 覆盖慢链路且不至于无限挂起"},
    "max_retries": {
        "value": 2,
        "basis": "§4 冻结设计：超时/重试预算（总尝试次数=2）"},
    "backoff_base_s": {
        "value": 2.0,
        "basis": "指数退避基数（与 config.retry.backoff_base_s 同量级）"},
    "reason_max_chars": {
        "value": 160,
        "basis": "理由仅供人工速览；截断长度固定以保证缓存键与产物稳定"},
    "requirement_text_max_chars": {
        "value": 1200,
        "basis": "需求文本上限（防超长输入推高成本）；超出即截断并在产物标注"},
}

#: 单价表（USD / 1M tokens）。**必须按供应商实际账单核对**；本表用于逐调用记账，
#: 不参与任何门禁判定。`verified=False` 表示未经真实账单核对（如实登记）。
PRICING = {
    "qwen3-vl-plus": {
        "input_text": 0.60, "input_image": 0.60, "output": 1.80, "verified": False,
        "basis": "阿里云百炼 qwen3-vl-plus 公开档位占位值；**以实际账单为准**"},
}
DEFAULT_PRICING = {"input_text": 1.00, "input_image": 1.00, "output": 3.00,
                   "verified": False, "basis": "未知模型的保守占位单价（记账用，非判定用）"}

CACHE_DIR_REL = pathlib.Path("output") / "vlm_judge_cache"

SYSTEM_PROMPT = (
    "你是视频素材与画面需求的**视觉相关性**判定模块。你会收到一个镜头需求（该镜头要用画面表达什么）"
    "和一张候选图片。你只判断：**这张图的画面内容是否满足该需求**。\n\n"
    "判定三类（严格遵守）：\n"
    "1. RELEVANT：画面内容直接、具体地满足需求的核心视觉诉求"
    "（主体/场景/物件/图表与需求一致，可作为该镜头的画面）。\n"
    "2. PARTIAL：画面与需求主题相关，但只满足一部分诉求，或过于泛化/抽象，"
    "需要人工判断是否可用（例如需求要具体界面图，而图只是抽象几何结构）。\n"
    "3. IRRELEVANT：画面与需求主题无关，或属于同形异义/不同对象"
    "（例如需求讲 VR 头显佩戴，图却是鲨鱼照片）。\n\n"
    "硬性规则：\n"
    "- 只依据**画面实际内容**判断，不依据文件名、不依据需求里的关键词字面重叠。\n"
    "- 需求会同时给出「画面目标」（该镜理想画面）与「本镜旁白」（该镜在讲什么）。"
    "判定「是否满足需求」时，**两者都要看**：画面只需成为该镜可用、切题的视觉锚点即可，"
    "**不要求逐字复现「画面目标」里的每个元素**（例如目标是「三千页证明堆叠」，"
    "而画面是一张切题的数学图，仍在讲同一件事，应判 RELEVANT 或 PARTIAL，不应判 IRRELEVANT）。\n"
    "- 只有画面与「旁白主题 + 画面目标」**都**无关（讲 VR 头显却给鲨鱼照片这类）才判 IRRELEVANT。\n"
    "- 素材池**只有 8 张**图，无法逐镜定制；因此「不够完美但切题」应判 PARTIAL 或 RELEVANT，"
    "不要把「不如理想画面精确」当成无关。\n"
    "- 不要因为图片「好看/专业」就判 RELEVANT；也不要因为风格朴素就判 IRRELEVANT。\n"
    "- 不要输出任何解释性段落，只输出 JSON。\n\n"
    "只输出 JSON，格式："
    "{\"label\": \"RELEVANT|PARTIAL|IRRELEVANT\", \"reason\": \"一句中文理由(≤60字)\", "
    "\"confidence\": 0.0-1.0 的数字}"
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(LABELS)},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["label", "reason", "confidence"],
}

#: **P18-3 专用**：视觉**存在性**核验（"帧里在不在"），与 #73 的语义相关性判定**无关**。
#: 任务边界：只判「帧中是否出现该素材的任何部分（允许裁切/缩放/局部）」，
#: **不判**「配不配/合不合适」。
PROMPT_VERSION_PRESENCE = "vlm-presence-verify-v1"
SYSTEM_PROMPT_PRESENCE = (
    "你是视频帧的**视觉存在性**核验模块。你会收到（1）一帧成片画面，（2）一张素材原图。"
    "你只回答一个问题：**这帧画面里是否出现了这张素材的任何部分？**\n\n"
    "允许的情形（都应判 present）：素材被裁切、被缩放、只露出一部分、被放大到只看得到局部、"
    "经过调色或叠加字幕、画面里的素材与其它画面元素拼接。\n"
    "**不要**判断素材与镜头内容是否相关、是否合适、是否好看——**只看在不在**。\n\n"
    "三类输出：\n"
    "1. present：帧中确实能辨认出该素材的某个部分（哪怕只是局部/被缩放）。\n"
    "2. absent：帧中找不到该素材的任何部分（是别的画面）。\n"
    "3. uncertain：画面过于局部/模糊/被遮挡，无法确定。\n\n"
    "判定要点：关注素材的**结构特征**（线条走向、图形布局、文字块位置、显著色块/形状），"
    "而不是像素级完全一致；缩放/裁切会改变像素但不改变结构。\n"
    "拿不准时输出 uncertain，**不要猜**。\n\n"
    "只输出 JSON：{\"presence\": \"present|absent|uncertain\", \"reason\": \"一句中文理由(≤60字)\"}"
)

OUTPUT_SCHEMA_PRESENCE = {
    "type": "object",
    "properties": {
        "presence": {"type": "string", "enum": ["present", "absent", "uncertain"]},
        "reason": {"type": "string"},
    },
    "required": ["presence", "reason"],
}

PRESENCE_LABELS = ("present", "absent", "uncertain")

#: **诊断专用**提示词变体（默认**不启用**）：把判定口径从「逐元素复现画面目标」
#: 改为「是否可作该镜切题的视觉锚点」。仅用于 P14-2 失配根因诊断，**不参与门禁判定**。
PROMPT_VERSION_DIAG = "vlm-relevance-judge-diag-anchor-v1"
SYSTEM_PROMPT_DIAG = (
    "你是视频镜头素材的**可用性**判定模块。你会收到一个镜头的旁白与画面目标，以及一张候选图片。"
    "请回答一个问题：**这张图能否作为该镜头切题的视觉锚点**（观众看到它，不会觉得与这段旁白无关）？\n\n"
    "判定三类：\n"
    "1. RELEVANT：画面主题与旁白所讲的事**属于同一话题**，作为该镜画面合理。\n"
    "2. PARTIAL：画面与旁白话题部分相关、或明显更泛化，需要人工定夺。\n"
    "3. IRRELEVANT：画面与旁白话题**属于不同领域/不同事物**（讲 VR 头显却给鲨鱼照片）。\n\n"
    "重要口径：\n"
    "- 素材池有限，**不要求**画面复现「画面目标」里的每个细节元素；细节不符不构成无关。\n"
    "- 判定依据是**话题是否同一**，不是「元素是否逐一命中」。\n"
    "- 不要因为缺少某个具体年份/人名/术语的视觉呈现就判 IRRELEVANT。\n"
    "- 只输出 JSON：{\"label\": \"RELEVANT|PARTIAL|IRRELEVANT\", \"reason\": \"一句中文理由(≤60字)\", "
    "\"confidence\": 0-1 数字}"
)


# ---------------------------------------------------------------- 配置解析
def _load_external(root: pathlib.Path) -> tuple[dict, str]:
    p = pathlib.Path(root) / "config" / "vlm_judge.json"
    if not p.is_file():
        return {}, "default(no-file)"
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                                       # noqa: BLE001
        return {}, "default(unreadable)"
    if not isinstance(j, dict):
        return {}, "default(non-object)"
    return j, str(p)


def resolve_config(config: dict | None = None, root: str | pathlib.Path | None = None
                   ) -> tuple[dict, str]:
    """三级链：内存 `config.tools.vlm_judge` → `config/vlm_judge.json` → 默认关闭。

    返回 `(resolved, source)`。**只做加法**：不改 `config.json`、不改任何既有键语义。
    """
    r = pathlib.Path(root) if root else pathlib.Path(
        os.environ.get("VIDEO_STUDIO_ROOT", ".")).resolve()
    merged = dict(DEFAULT_CONFIG)
    source = "default"
    ext, ext_src = _load_external(r)
    if ext:
        merged.update({k: v for k, v in ext.items()})
        source = ext_src
    mem = ((config or {}).get("tools") or {}).get("vlm_judge")
    if isinstance(mem, dict) and mem:
        merged.update(mem)
        source = "config.tools.vlm_judge"
    out = {
        "enabled": bool(merged.get("enabled", False)),
        "base_url": str(merged.get("base_url") or "").rstrip("/"),
        "model": str(merged.get("model") or ""),
        "api_key_env": str(merged.get("api_key_env") or "VLM_API_KEY"),
        "_source": source,
    }
    return out, source


def api_key(cfg: dict) -> str | None:
    """key **只从环境变量**读（禁止硬编码/禁止写入产物）。"""
    v = os.environ.get(cfg.get("api_key_env") or "VLM_API_KEY")
    return v.strip() if isinstance(v, str) and v.strip() else None


def available(cfg: dict) -> tuple[bool, str]:
    """是否可真实调用。不可用 ⇒ (False, PROVIDER_* 原因)。"""
    if not cfg.get("enabled"):
        return False, "PROVIDER_NOT_CONFIGURED"
    if not cfg.get("base_url"):
        return False, "PROVIDER_NOT_CONFIGURED"
    if not cfg.get("model"):
        return False, "PROVIDER_NOT_CONFIGURED"
    if api_key(cfg) is None:
        return False, "PROVIDER_NOT_CONFIGURED"
    return True, ""


# ---------------------------------------------------------------- 输入构造
def requirement_text(requirement: dict, max_chars: int | None = None) -> str:
    """把 VisualRequirement 渲染为**人可读的视觉诉求**文本（不含 asset 侧信息）。"""
    lim = int(max_chars if max_chars is not None
              else POLICY["requirement_text_max_chars"]["value"])
    r = requirement or {}
    parts = []
    vg = str(r.get("visual_goal") or "").strip()
    if vg:
        parts.append("视觉目标：" + vg)
    for key, label in (("subject", "主体"), ("action", "动作"), ("object", "对象"),
                       ("environment", "环境"), ("concept", "概念")):
        v = str(r.get(key) or "").strip()
        if v:
            parts.append("{}：{}".format(label, v))
    cp = [str(x).strip() for x in (r.get("concepts_pos") or []) if str(x).strip()]
    if cp:
        parts.append("正向概念：" + "、".join(cp))
    cn = [str(x).strip() for x in (r.get("concepts_neg") or []) if str(x).strip()]
    if cn:
        parts.append("**不得出现**：" + "、".join(cn))
    av = [str(x).strip() for x in (r.get("avoid_list") or []) if str(x).strip()]
    if av:
        parts.append("**避免**：" + "、".join(av))
    ek = str(r.get("expected_kind") or "").strip()
    if ek:
        parts.append("期望素材类型：" + ek)
    nar = str(r.get("narration") or "").strip()
    if nar:
        parts.append("本镜旁白：" + nar)
    txt = "\n".join(parts).strip() or "（该需求未提供可用视觉字段）"
    if len(txt) > lim:
        txt = txt[:lim] + "…（已截断）"
    return txt


def need_text_sha256(requirement: dict) -> str:
    return hashlib.sha256(requirement_text(requirement).encode("utf-8")).hexdigest()


def build_prompt(requirement: dict, image_sha256: str) -> tuple[str, str]:
    """返回 (system, user)。**单次只看一个 (需求, 候选图) 对** —— 判定独立性纪律。

    刻意**不**传入：同景其它候选、词面匹配分数、任何既有机器/人工结论。
    """
    user = (
        "请判定下面这张候选图片是否满足该镜头的视觉需求。\n\n"
        "# 镜头视觉需求\n" + requirement_text(requirement) + "\n\n"
        "# 候选图片\n"
        "（见本条消息附带的图片；图片指纹 sha256:{}…）\n\n"
        "只输出 JSON：{{\"label\": \"RELEVANT|PARTIAL|IRRELEVANT\", "
        "\"reason\": \"一句中文理由(≤60字)\", \"confidence\": 0-1 数字}}"
    ).format(image_sha256[:16])
    return SYSTEM_PROMPT, user


def prepare_image_data_uri(image_path: str | pathlib.Path, *,
                           max_edge: int | None = None, quality: int | None = None
                           ) -> tuple[str, dict]:
    """本地图 → **确定性**降采样 JPEG data URI。返回 (data_uri, info)。

    确定性：固定 `LANCZOS` 重采样、固定 JPEG 质量、去掉 EXIF（`Image.info` 不写入）、
    无时间戳。同输入 ⇒ 同字节 ⇒ 可用 image_sha256 作缓存键。
    """
    from PIL import Image
    me = int(max_edge if max_edge is not None else POLICY["max_image_edge_px"]["value"])
    q = int(quality if quality is not None else POLICY["jpeg_quality"]["value"])
    p = pathlib.Path(image_path)
    if not p.is_file():
        raise ValueError("PROVIDER_IMAGE_UNREADABLE")
    with Image.open(p) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, float(me) / float(max(w, h))) if max(w, h) > 0 else 1.0
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        if (nw, nh) != (w, h):
            im = im.resize((nw, nh), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=q, optimize=False)
        raw = buf.getvalue()
    uri = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    info = {"src_width": w, "src_height": h, "out_width": nw, "out_height": nh,
            "jpeg_quality": q, "max_edge_px": me, "jpeg_bytes": len(raw),
            "jpeg_sha256": hashlib.sha256(raw).hexdigest(),
            "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return uri, info


# ---------------------------------------------------------------- 缓存（文件）
def active_prompt(variant: str = "main") -> tuple[str, str]:
    """返回 (system_prompt, prompt_version)。`variant="diag_anchor"` 为**诊断专用**变体。"""
    if variant == "diag_anchor":
        return SYSTEM_PROMPT_DIAG, PROMPT_VERSION_DIAG
    return SYSTEM_PROMPT, PROMPT_VERSION


def cache_key(model: str, image_sha256: str, requirement: dict,
              prompt_version: str | None = None) -> str:
    pv = prompt_version or PROMPT_VERSION
    raw = "\x00".join([pv, model, image_sha256, need_text_sha256(requirement)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _cache_path(root: pathlib.Path, key: str) -> pathlib.Path:
    d = pathlib.Path(root) / CACHE_DIR_REL
    return d / "{}.json".format(key)


def cache_get(root: pathlib.Path, key: str) -> dict | None:
    p = _cache_path(root, key)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                                       # noqa: BLE001
        return None


def cache_put(root: pathlib.Path, key: str, row: dict) -> None:
    p = _cache_path(root, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(row, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")


# ---------------------------------------------------------------- 计价 / 解析
def price_of(model: str) -> dict:
    return PRICING.get(model) or DEFAULT_PRICING


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int,
                      image_tokens: int = 0) -> float:
    pr = price_of(model)
    text_in = max(int(tokens_in) - int(image_tokens), 0)
    usd = (text_in * float(pr["input_text"])
           + int(image_tokens) * float(pr["input_image"])
           + int(tokens_out) * float(pr["output"])) / 1_000_000.0
    return round(usd, 8)


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        t = t[a:b + 1]
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("顶层应为对象")
    return data


def validate_output(data: dict) -> list[str]:
    errs = []
    lab = data.get("label")
    if lab not in LABELS:
        errs.append("label 不在枚举内: {!r}".format(lab))
    if not isinstance(data.get("reason"), str) or not str(data.get("reason")).strip():
        errs.append("reason 缺失或非字符串")
    try:
        c = float(data.get("confidence"))
        if not (0.0 <= c <= 1.0):
            errs.append("confidence 越界: {}".format(c))
    except (TypeError, ValueError):
        errs.append("confidence 非数值")
    return errs


# ---------------------------------------------------------------- 调用
def _post_json(url: str, payload: dict, key: str, timeout_s: float) -> tuple[dict, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer {}".format(key)})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8", "replace")), ""


def _classify_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:                                                   # noqa: BLE001
            pass
        if code in (401, 403):
            return "PROVIDER_AUTH_FAILED", "HTTP {}: {}".format(code, detail)
        if code == 429:
            return "PROVIDER_RATE_LIMITED", "HTTP 429: {}".format(detail)
        if code == 408 or code >= 500:
            return "PROVIDER_TIMEOUT", "HTTP {}: {}".format(code, detail)
        return "PROVIDER_HTTP_ERROR", "HTTP {}: {}".format(code, detail)
    if isinstance(exc, urllib.error.URLError):
        return "PROVIDER_TIMEOUT", "URLError: {}".format(str(getattr(exc, "reason", exc))[:200])
    if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
        return "PROVIDER_TIMEOUT", type(exc).__name__
    return "PROVIDER_HTTP_ERROR", "{}: {}".format(type(exc).__name__, str(exc)[:200])


def judge_pair(*, requirement: dict, image_path: str | pathlib.Path, cfg: dict,
               root: str | pathlib.Path, budget_usd: float | None = None,
               spent_usd: float = 0.0, prompt_variant: str = "main") -> dict:
    """判定单对 (需求, 候选图)。**任何失败都不抛异常**，返回 `error_code` 且 label=NA。

    返回字段：label / reason / confidence / error_code / error_detail / model /
    prompt_version / cache_key / cache_hit / tokens_in / tokens_out / image_tokens /
    cost_usd / latency_ms / image / requirement_text_sha256。
    """
    r = pathlib.Path(root)
    model = cfg.get("model") or ""
    system_prompt, pver = active_prompt(prompt_variant)
    base = {
        "schema": SCHEMA,
        "prompt_version": pver,
        "label": NA,
        "reason": "",
        "confidence": None,
        "error_code": "",
        "error_detail": "",
        "model": model,
        "cache_key": "",
        "cache_hit": False,
        "tokens_in": 0,
        "tokens_out": 0,
        "image_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0,
        "image": {},
        "requirement_text_sha256": need_text_sha256(requirement),
    }

    ok, why = available(cfg)
    if not ok:
        base["error_code"] = why
        base["error_detail"] = "未启用或缺凭据（enabled/model/base_url/环境变量 key）"
        return base

    if budget_usd is not None and spent_usd >= float(budget_usd):
        base["error_code"] = "PROVIDER_BUDGET_EXHAUSTED"
        base["error_detail"] = "已达成本上限 ${:.4f}".format(float(budget_usd))
        return base

    try:
        data_uri, info = prepare_image_data_uri(image_path)
    except ValueError as exc:
        base["error_code"] = str(exc) or "PROVIDER_IMAGE_UNREADABLE"
        base["error_detail"] = "图像不可读: {}".format(image_path)
        return base
    except Exception as exc:                                                # noqa: BLE001
        base["error_code"] = "PROVIDER_IMAGE_UNREADABLE"
        base["error_detail"] = "{}: {}".format(type(exc).__name__, str(exc)[:160])
        return base
    base["image"] = info

    key = cache_key(model, info["source_sha256"], requirement, pver)
    base["cache_key"] = key
    hit = cache_get(r, key)
    if hit and hit.get("label") in LABELS:
        out = {**base,
               "label": hit["label"], "reason": hit.get("reason") or "",
               "confidence": hit.get("confidence"),
               "cache_hit": True, "cost_usd": 0.0, "latency_ms": 0}
        return out

    system, user = system_prompt, build_prompt(requirement, info["source_sha256"])[1]
    payload = {
        "model": model,
        "temperature": POLICY["temperature"]["value"],
        "max_tokens": POLICY["max_tokens"]["value"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ],
    }
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    keytxt = api_key(cfg)
    last = ("PROVIDER_HTTP_ERROR", "")
    attempts = int(POLICY["max_retries"]["value"])
    for attempt in range(1, attempts + 1):
        t0 = time.perf_counter()
        try:
            resp, _ = _post_json(url, payload, keytxt,
                                 float(POLICY["timeout_s"]["value"]))
            latency = int((time.perf_counter() - t0) * 1000)
            choices = resp.get("choices") or []
            if not choices:
                last = ("PROVIDER_EMPTY", "响应无 choices")
                continue
            content = ((choices[0].get("message") or {}).get("content")
                       if isinstance(choices[0], dict) else None)
            if isinstance(content, list):        # 部分实现返回分段内容
                content = "".join(str(seg.get("text") or "") if isinstance(seg, dict)
                                  else str(seg) for seg in content)
            if not content or not str(content).strip():
                last = ("PROVIDER_EMPTY", "content 为空")
                continue
            try:
                parsed = _extract_json(str(content))
            except Exception as exc:                                        # noqa: BLE001
                last = ("PROVIDER_MALFORMED", "JSON 解析失败: {}: {}".format(
                    type(exc).__name__, str(exc)[:120]))
                continue
            errs = validate_output(parsed)
            if errs:
                last = ("PROVIDER_MALFORMED", "；".join(errs)[:200])
                continue
            usage = resp.get("usage") or {}
            tin = int(usage.get("prompt_tokens") or 0)
            tout = int(usage.get("completion_tokens") or 0)
            itok = int(((usage.get("prompt_tokens_details") or {})
                        .get("image_tokens")) or 0)
            cost = estimate_cost_usd(model, tin, tout, itok)
            out = {**base,
                   "label": parsed["label"],
                   "reason": str(parsed.get("reason") or "")[
                       :int(POLICY["reason_max_chars"]["value"])],
                   "confidence": float(parsed.get("confidence")),
                   "tokens_in": tin, "tokens_out": tout, "image_tokens": itok,
                   "cost_usd": cost, "latency_ms": latency}
            cache_put(r, key, {"label": out["label"], "reason": out["reason"],
                               "confidence": out["confidence"], "model": model,
                               "prompt_version": pver,
                               "cache_key": key,
                               "image_sha256": info["source_sha256"],
                               "requirement_text_sha256": base["requirement_text_sha256"],
                               "tokens_in": tin, "tokens_out": tout,
                               "image_tokens": itok, "cost_usd": cost})
            return out
        except Exception as exc:                                            # noqa: BLE001
            last = _classify_error(exc)
            if attempt < attempts and last[0] in ("PROVIDER_TIMEOUT",
                                                  "PROVIDER_RATE_LIMITED",
                                                  "PROVIDER_HTTP_ERROR"):
                time.sleep(float(POLICY["backoff_base_s"]["value"]) * attempt)
                continue
            break
    base["error_code"], base["error_detail"] = last
    return base


def judge_presence(*, frame_path, asset_path, cfg: dict, root: str | pathlib.Path,
                   budget_usd: float | None = None, spent_usd: float = 0.0) -> dict:
    """**P18-3**：视觉存在性核验（帧里在不在该素材）。

    与 `judge_pair`（语义相关性）**无关**：这里只判"在不在"，不判"配不配"。
    返回 {presence, reason, error_code, ...}；**任何失败都不抛异常**，presence 置 `uncertain`
    （fail-closed：由调用方按"不在屏"处理）。
    """
    r = pathlib.Path(root)
    model = cfg.get("model") or ""
    base = {
        "schema": "vlm-presence-verification-v1",
        "prompt_version": PROMPT_VERSION_PRESENCE,
        "presence": "uncertain", "reason": "", "error_code": "", "error_detail": "",
        "model": model, "cache_key": "", "cache_hit": False,
        "tokens_in": 0, "tokens_out": 0, "image_tokens": 0, "cost_usd": 0.0,
        "latency_ms": 0, "frame_image": {}, "asset_image": {},
    }
    ok, why = available(cfg)
    if not ok:
        base["error_code"] = why
        base["error_detail"] = "未启用或缺凭据"
        return base
    if budget_usd is not None and spent_usd >= float(budget_usd):
        base["error_code"] = "PROVIDER_BUDGET_EXHAUSTED"
        base["error_detail"] = "已达成本上限 ${:.4f}".format(float(budget_usd))
        return base
    try:
        f_uri, f_info = prepare_image_data_uri(frame_path)
        a_uri, a_info = prepare_image_data_uri(asset_path)
    except Exception as exc:                                                # noqa: BLE001
        base["error_code"] = "PROVIDER_IMAGE_UNREADABLE"
        base["error_detail"] = "{}: {}".format(type(exc).__name__, str(exc)[:160])
        return base
    base["frame_image"] = f_info
    base["asset_image"] = a_info

    raw = "\x00".join([PROMPT_VERSION_PRESENCE, model, f_info["source_sha256"],
                       a_info["source_sha256"]])
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    base["cache_key"] = key
    hit = cache_get(r, key)
    if hit and hit.get("presence") in PRESENCE_LABELS:
        return {**base, "presence": hit["presence"], "reason": hit.get("reason") or "",
                "cache_hit": True}
    user = ("请判断：**下面第一张是成片帧，第二张是素材原图**。"
            "该帧中是否出现了这张素材的任何部分（允许裁切/缩放/只露局部）？\n\n"
            "只输出 JSON：{{\"presence\": \"present|absent|uncertain\", "
            "\"reason\": \"一句中文理由(≤60字)\"}}")
    payload = {
        "model": model,
        "temperature": POLICY["temperature"]["value"],
        "max_tokens": POLICY["max_tokens"]["value"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_PRESENCE},
            {"role": "user", "content": [
                {"type": "text", "text": "成片帧："},
                {"type": "image_url", "image_url": {"url": f_uri}},
                {"type": "text", "text": "素材原图："},
                {"type": "image_url", "image_url": {"url": a_uri}},
                {"type": "text", "text": user},
            ]},
        ],
    }
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    keytxt = api_key(cfg)
    last = ("PROVIDER_HTTP_ERROR", "")
    attempts = int(POLICY["max_retries"]["value"])
    for attempt in range(1, attempts + 1):
        t0 = time.perf_counter()
        try:
            resp, _ = _post_json(url, payload, keytxt, float(POLICY["timeout_s"]["value"]))
            latency = int((time.perf_counter() - t0) * 1000)
            choices = resp.get("choices") or []
            if not choices:
                last = ("PROVIDER_EMPTY", "响应无 choices")
                continue
            content = ((choices[0].get("message") or {}).get("content")
                       if isinstance(choices[0], dict) else None)
            if isinstance(content, list):
                content = "".join(str(seg.get("text") or "") if isinstance(seg, dict)
                                  else str(seg) for seg in content)
            if not content or not str(content).strip():
                last = ("PROVIDER_EMPTY", "content 为空")
                continue
            try:
                parsed = _extract_json(str(content))
            except Exception as exc:                                        # noqa: BLE001
                last = ("PROVIDER_MALFORMED", "JSON 解析失败: {}".format(type(exc).__name__))
                continue
            pres = str(parsed.get("presence") or "").strip().lower()
            if pres not in PRESENCE_LABELS:
                last = ("PROVIDER_MALFORMED", "presence 不在枚举内: {!r}".format(pres))
                continue
            usage = resp.get("usage") or {}
            tin = int(usage.get("prompt_tokens") or 0)
            tout = int(usage.get("completion_tokens") or 0)
            itok = int(((usage.get("prompt_tokens_details") or {}).get("image_tokens")) or 0)
            cost = estimate_cost_usd(model, tin, tout, itok)
            out = {**base, "presence": pres,
                   "reason": str(parsed.get("reason") or "")[
                       :int(POLICY["reason_max_chars"]["value"])],
                   "tokens_in": tin, "tokens_out": tout, "image_tokens": itok,
                   "cost_usd": cost, "latency_ms": latency}
            cache_put(r, key, {"presence": pres, "reason": out["reason"], "model": model,
                               "prompt_version": PROMPT_VERSION_PRESENCE,
                               "cache_key": key,
                               "frame_sha256": f_info["source_sha256"],
                               "asset_sha256": a_info["source_sha256"],
                               "tokens_in": tin, "tokens_out": tout,
                               "image_tokens": itok, "cost_usd": cost})
            return out
        except Exception as exc:                                            # noqa: BLE001
            last = _classify_error(exc)
            if attempt < attempts and last[0] in ("PROVIDER_TIMEOUT",
                                                  "PROVIDER_RATE_LIMITED",
                                                  "PROVIDER_HTTP_ERROR"):
                time.sleep(float(POLICY["backoff_base_s"]["value"]) * attempt)
                continue
            break
    base["error_code"], base["error_detail"] = last
    return base


def pixel_cost_note() -> dict:
    """单价表出处与核对状态（供报告如实登记）。"""
    return {"pricing": PRICING, "default": DEFAULT_PRICING,
            "note": ("逐调用记账用单价；`verified=False` ⇒ **未按真实账单核对**，"
                     "成本数字为估算，实测后应回填账单值。不参与任何门禁判定。")}
