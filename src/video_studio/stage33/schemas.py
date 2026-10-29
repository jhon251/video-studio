"""Stage 3.3 v3-mvp 常量/枚举/契约。

核心原则：Visual Statement 的字段枚举里**没有模板名**——模板/实现原语只存在于
realizer 内部（LLM 不可见）。反模板黑名单用于 Validator 拦截"高级模板系统"回归。
"""
STAGE33_VERSION = "3.3-v3-mvp"
STAGE33_STATUS = "DEV"

# Visual Statement 字段枚举（LLM 可见）
RELATION_TYPES = ["continuation", "contrast", "escalation", "release", "handoff", "none"]
LAYER_ROLES = ["background", "midground", "foreground"]
STAGE_NAMES = ["enter", "hold", "reveal", "exit"]
MOTION_INTENTS = ["attention_shift", "process_expression", "revelation", "none"]

# 反模板黑名单：statement 任何文本字段出现以下词 → REJECT
TEMPLATE_NAMES_BLACKLIST = [
    "DATA_GRAPHIC", "SAFE_IMAGE", "SAFE_VIDEO", "SAFE_COMPOSITE", "SELF_CREATED_GRAPHIC",
    "TEXT_CARD", "FULL_BLEED", "CENTER_CROP", "THIRDS_LEFT", "THIRDS_RIGHT", "INSET_FRAME",
    "SPLIT_H", "SPLIT_V", "UPPER_TITLE", "SLOW_PUSH_IN", "SLOW_PULL_OUT", "PAN_H", "PAN_V",
    "DIAGONAL_DRIFT", "FOCAL_ZOOM", "HOLD_MICRO", "SOURCE_NATIVE", "NUMBER_EMPHASIS",
    "COMPARISON", "TYPO_COMPOSITION", "CONTRAST_SPLIT", "STATEMENT", "QUESTION",
]
# 模板式决策句式（"因为这是数据句，所以用某模板"）→ REJECT
TEMPLATE_REASON_PATTERN = (
    r"(因为|所以|由于).{0,8}(数据|人物|因果|情绪|对比|时间|抽象|结论)(句|镜|段)"
    r".{0,12}(使用|用|选择|套用|模板)")

# Executor 能力清单（LLM 只能要求这些行为）
CAPABILITIES = [
    "static_composition（静止构图）",
    "integer_pan（整数帧平移，速度≥1px/帧，恒定步长）",
    "integer_zoom_in/out（整数帧缩放，偶数步长 2px/帧）",
    "layered_composition（≤3 层：素材/色块/锚点词，每层一个职责）",
    "geometric_mask（矩形/圆角/圆形遮罩）",
    "temporal_reveal（进入/停留/揭示/退出，帧级整数透明度）",
    "emphasis（字号/颜色/描边/明度对比）",
    "contrast_juxtaposition（左右/大小并置）",
    "keyword_dynamics（进入/点亮/淡出各一次）",
]

CAPS = {
    "GRAPHIC_TEXT_MAX": 12,          # 图形层最大字数
    "ANCHOR_TEXT_MAX": 12,
    "LAYERS_MAX": 3,
    "BEAT_MIN_DUR": 1.2,
    "REPAIR_RATE_MAX": 0.05,
    "SEM_MIN": 50.0,                 # 3.2b P0-4 裁决线（不降低）
    "MOTION_STATIC_HEAD_TAIL": 0.3,  # 运动前后静止时长(s)
    "MOTION_MIN_PAN_RATIO": 0.02,    # 平移最小幅度（源宽比）
    "MOTION_MIN_ZOOM_RATIO": 0.04,   # 缩放最小幅度
    "MOTION_MIN_SPEED": 1.0,         # 平移最小速度 px/帧（低于→HOLD）
    "MOTION_ZOOM_STEP": 2,           # 缩放偶数步长 px/帧
    "DIRECTOR_NOTE_MAX": 80,
    "MOTION_NECESSITY_MIN": 8,
}

STYLE_CONTRACT = {
    "family": "SCIENTIFIC",
    "palette": {"bg": "#0E2A33", "surface": "#16404F", "accent": "#4FC3F7",
                "text": "#F4F8F9", "highlight": "#FFB74D", "dim": "#1E4A59"},
    "typography": {"anchor": 128, "small_anchor": 84, "tag": 30},
    "motion_band": "LOW",  # 全片克制；静止是默认
}

# 语义方向词典（供 realizer 判断 attention_shift 方向；主题无关）
DIRECTION_LEXICON = {
    "UP": ["升", "高", "涨", "增", "上", "浮", "起", "热", "多", "长", "挺"],
    "DOWN": ["降", "低", "落", "褪", "下", "沉", "减", "少", "冷", "衰", "消失", "安静"],
    "LEFT": ["过去", "从前", "回"],
    "RIGHT": ["接下来", "未来", "向前", "推进"],
}

# 数字词（v2 修复版：单字量词不算数字）
NUM_RE_SRC = (
    r"[0-9]+(?:\.\d+)?(?:度|米|倍|年|%|℃|°C|分之一)?"
    r"|[一二两三四五六七八九十百千万亿]{2,}(?:度|米|倍|年|分之一|°C|℃)?"
    r"|[一二两三四五六七八九十百千万亿]+(?:度|米|倍|年|分之一|°C|℃)")

TIME_CUES = ["过去", "现在", "正在", "接下来", "几十年", "十年", "每天", "慢慢", "第一次",
             "已经", "将来", "最后"]
CAUSE_CUES = ["因为", "所以", "导致", "使", "只要", "吸收了", "取决于", "如果"]
CONTRAST_CUES = ["不是", "而是", "但", "却", "反而", "一半", "越来越", "挺过"]
ACTION_CUES = ["游过", "下到", "绑在", "掠过", "戴上", "穿过", "挺过", "改变", "等待",
               "褪色", "消失", "带来", "跑"]
SPACE_CUES = ["海面之下", "水下", "下到", "穿过", "缝隙", "海里", "海底", "海边", "站台"]
EMOTION_CUES = ["慢慢", "褪色", "消失", "失去", "等待", "选择", "安静", "温暖", "呼吸"]
CONCLUSION_CUES = ["取决于", "才是", "而它正在", "生死", "最终"]
