"""Curated, versioned Pinyin foundation catalog and course import."""

import math
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    ActivityType,
    Course,
    CourseSourceType,
    CourseStatus,
    CourseSubject,
    CourseUnit,
    KnowledgePoint,
    KnowledgePointRole,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    LearningActivity,
    PinyinCatalogRelease,
    PinyinItem,
    PinyinKind,
    PinyinPracticeItem,
    RelationType,
)

PINYIN_CATALOG_VERSION = "pinyin-foundation-v1"
PINYIN_COURSE_KEY = "system-pinyin-foundation-v1"


@dataclass(frozen=True)
class PinyinSeed:
    symbol: str
    kind: str
    subcategory: str
    display_text: str
    pronunciation_cue: str
    example_text: str
    example_pinyin: str
    description: str
    parent_tip: str
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def canonical_key(self) -> str:
        key_kind = "whole" if self.kind == PinyinKind.WHOLE else self.kind
        symbol = self.symbol if self.kind != PinyinKind.TONE else str(self.metadata["tone"])
        return f"chinese:pinyin:{key_kind}:{symbol}"

    @property
    def knowledge_type(self) -> str:
        return {
            PinyinKind.INITIAL: KnowledgeType.PINYIN_INITIAL,
            PinyinKind.FINAL: KnowledgeType.PINYIN_FINAL,
            PinyinKind.TONE: KnowledgeType.PINYIN_TONE,
            PinyinKind.WHOLE: KnowledgeType.PINYIN_SYLLABLE,
        }[self.kind]


def _initial(
    symbol: str,
    cue: str,
    example: str,
    example_pinyin: str,
    tip: str,
    *,
    subcategory: str = "basic_initial",
) -> PinyinSeed:
    return PinyinSeed(
        symbol=symbol,
        kind=PinyinKind.INITIAL,
        subcategory=subcategory,
        display_text=symbol,
        pronunciation_cue=f"{cue}，{example}的{cue}。",
        example_text=example,
        example_pinyin=example_pinyin,
        description="先听中文示范音，再看符号并跟读。",
        parent_tip=tip,
    )


def _final(
    symbol: str,
    cue: str,
    example: str,
    example_pinyin: str,
    subcategory: str,
    tip: str | None = None,
) -> PinyinSeed:
    if tip is None:
        tip = subcategory
        if symbol in {"a", "o", "e", "i", "u", "ü"}:
            subcategory = "single_final"
        elif symbol in {"an", "en", "in", "un", "ün"}:
            subcategory = "front_nasal_final"
        elif symbol in {"ang", "eng", "ing", "ong"}:
            subcategory = "back_nasal_final"
        else:
            subcategory = "compound_final"
    return PinyinSeed(
        symbol=symbol,
        kind=PinyinKind.FINAL,
        subcategory=subcategory,
        display_text=symbol,
        pronunciation_cue=f"{cue}，{example}的{cue}。",
        example_text=example,
        example_pinyin=example_pinyin,
        description="把声音拉长一点听清楚，再看嘴形跟读。",
        parent_tip=tip,
    )


INITIALS = {
    item.symbol: item
    for item in (
        _initial("b", "玻", "玻璃", "bō li", "嘴唇先闭起来，再轻轻放开；可和 p 对比送气。"),
        _initial("p", "坡", "山坡", "shān pō", "让孩子把手放在嘴前，感受比 b 更明显的气流。"),
        _initial("m", "摸", "摸一摸", "mō yi mō", "双唇闭合，声音从鼻腔出来，不必强调术语。"),
        _initial("f", "佛", "佛像", "fó xiàng", "上牙轻碰下唇，让气流慢慢出来。"),
        _initial("d", "得", "得到", "dé dào", "舌尖轻碰上齿龈，听完示范再短短地读。"),
        _initial("t", "特", "特别", "tè bié", "和 d 对比，让孩子感受 t 的气流更明显。"),
        _initial("n", "呢", "你呢", "nǐ ne", "舌尖轻碰上方，声音从鼻腔出来。"),
        _initial("l", "乐", "快乐", "kuài lè", "舌尖轻碰上方，声音从舌头两边出来。"),
        _initial("g", "哥", "哥哥", "gē ge", "声音短而轻，不要读成英文单词。"),
        _initial("k", "科", "科学", "kē xué", "和 g 对比，用手感受 k 更明显的气流。"),
        _initial("h", "喝", "喝水", "hē shuǐ", "像轻轻哈气一样，保持声音短而清楚。"),
        _initial("j", "鸡", "小鸡", "xiǎo jī", "嘴角微微展开；和 q、x 放在一起听辨。"),
        _initial("q", "七", "七个", "qī ge", "比 j 多一点气流，可把手放在嘴前感受。"),
        _initial("x", "西", "西瓜", "xī guā", "让气流轻轻通过，不要把声音拖成英文读法。"),
        _initial(
            "zh",
            "知",
            "知道",
            "zhī dào",
            "这是翘舌音，先听清楚，再让舌尖轻轻翘起。",
            subcategory="retroflex_initial",
        ),
        _initial(
            "ch",
            "吃",
            "吃饭",
            "chī fàn",
            "和 zh 对比，ch 的气流更明显。",
            subcategory="retroflex_initial",
        ),
        _initial(
            "sh",
            "师",
            "老师",
            "lǎo shī",
            "舌尖轻轻翘起，让气流慢慢通过。",
            subcategory="retroflex_initial",
        ),
        _initial(
            "r",
            "日",
            "日光",
            "rì guāng",
            "先听“日”的声音，不要求孩子解释发音部位。",
            subcategory="retroflex_initial",
        ),
        _initial(
            "z",
            "资",
            "资料",
            "zī liào",
            "这是平舌音，可和 zh 分组听辨。",
            subcategory="flat_tongue_initial",
        ),
        _initial(
            "c",
            "刺",
            "小刺",
            "xiǎo cì",
            "和 z 对比，c 的气流更明显。",
            subcategory="flat_tongue_initial",
        ),
        _initial(
            "s",
            "丝",
            "丝巾",
            "sī jīn",
            "像轻轻发出丝丝声，注意不要读成英文 s。",
            subcategory="flat_tongue_initial",
        ),
        _initial(
            "y",
            "衣",
            "衣服",
            "yī fu",
            "把它作为音节开头来听，不用讲复杂规则。",
            subcategory="special_initial",
        ),
        _initial(
            "w",
            "屋",
            "屋子",
            "wū zi",
            "先听“屋”的开头声音，再看 w。",
            subcategory="special_initial",
        ),
    )
}

FINALS = {
    item.symbol: item
    for item in (
        _final("a", "啊", "阿姨", "ā yí", "single_final", "嘴巴自然张大，声音响亮而放松。"),
        _final("o", "喔", "喔喔叫", "ō ō jiào", "嘴唇拢圆，听清中文示范音。"),
        _final("e", "鹅", "白鹅", "bái é", "嘴角自然展开，听“鹅”的声音。"),
        _final("i", "衣", "衣服", "yī fu", "嘴角向两边展开，声音可以稍微拉长。"),
        _final("u", "乌", "乌云", "wū yún", "嘴唇拢成小圆形，听“乌”的声音。"),
        _final("ü", "鱼", "小鱼", "xiǎo yú", "先做 i 的嘴形，再把嘴唇拢圆；页面永远显示 ü。"),
        _final("ai", "哎", "哎呀", "āi yā", "声音从 a 滑向 i，先听整体变化。"),
        _final("ei", "诶", "诶一声", "ēi yì shēng", "声音从 e 滑向 i，不拆成两个字母名。"),
        _final("ui", "威", "威风", "wēi fēng", "听“威”的韵母，声音滑动要连贯。"),
        _final("ao", "奥", "奥秘", "ào mì", "声音从 a 滑向 o，嘴形逐渐变圆。"),
        _final("ou", "欧", "欧洲", "ōu zhōu", "先听“欧”，再模仿声音的滑动。"),
        _final("iu", "优", "优秀", "yōu xiù", "听“优”的韵母，连起来读，不逐个念字母。"),
        _final("ie", "耶", "椰子", "yē zi", "听“椰”的韵母，嘴形由窄到稍开。"),
        _final(
            "üe", "约", "月亮", "yuè liang", "保留 underlying ü；和 j、q、x 相拼时显示会省略两点。"
        ),
        _final("er", "儿", "儿童", "ér tóng", "这是一个特别的韵母，直接听“儿”的声音。"),
        _final("an", "安", "安全", "ān quán", "先听末尾轻轻收住的 n。"),
        _final("en", "恩", "恩情", "ēn qíng", "和 eng 对比，末尾不要拖得太长。"),
        _final("in", "音", "音乐", "yīn yuè", "听“音”的韵母，和 ing 做对比。"),
        _final("un", "温", "温暖", "wēn nuǎn", "听“温”的韵母，连贯地读。"),
        _final("ün", "云", "白云", "bái yún", "保留 ü 的嘴形，页面不使用 v。"),
        _final("ang", "昂", "昂头", "áng tóu", "声音在口腔后部收住，可和 an 对比。"),
        _final("eng", "鞥", "风声", "fēng shēng", "重点听后鼻音，和 en 分组辨听。"),
        _final("ing", "英", "英雄", "yīng xióng", "听“英”的韵母，和 in 分组辨听。"),
        _final("ong", "翁", "老翁", "lǎo wēng", "嘴唇拢圆，声音在后部收住。"),
    )
}

TONES = {
    "tone:1": PinyinSeed(
        "tone:1",
        PinyinKind.TONE,
        "tone",
        "ā",
        "第一声，阿姨的阿，声音平平的。",
        "阿姨",
        "ā yí",
        "第一声像一条平平的路。",
        "用手平平地划过去，动作只是辅助，仍要多听。",
        {"tone": 1, "label": "第一声", "gesture": "→", "shape": "平"},
    ),
    "tone:2": PinyinSeed(
        "tone:2",
        PinyinKind.TONE,
        "tone",
        "á",
        "第二声，回答的答，声音向上扬。",
        "回答",
        "huí dá",
        "第二声像声音沿着小坡向上走。",
        "手势可以向右上方划，听音比背口诀更重要。",
        {"tone": 2, "label": "第二声", "gesture": "↗", "shape": "上扬"},
    ),
    "tone:3": PinyinSeed(
        "tone:3",
        PinyinKind.TONE,
        "tone",
        "ǎ",
        "第三声，小马的马，声音先下再上。",
        "小马",
        "xiǎo mǎ",
        "第三声先往下，再轻轻转上来。",
        "慢一点示范，不要求孩子夸张地压低声音。",
        {"tone": 3, "label": "第三声", "gesture": "↘↗", "shape": "先下再上"},
    ),
    "tone:4": PinyinSeed(
        "tone:4",
        PinyinKind.TONE,
        "tone",
        "à",
        "第四声，大树的大，声音干脆下降。",
        "大树",
        "dà shù",
        "第四声像从高处快速滑下来。",
        "手势向右下方划，保持自然，不需要大声喊。",
        {"tone": 4, "label": "第四声", "gesture": "↘", "shape": "下降"},
    ),
    "tone:neutral": PinyinSeed(
        "tone:neutral",
        PinyinKind.TONE,
        "tone",
        "a",
        "轻声，妈妈第二个妈，读得轻轻短短。",
        "妈妈",
        "mā ma",
        "轻声没有调号，声音轻而短。",
        "用熟悉词语对比即可，不必给低龄孩子讲复杂变调。",
        {"tone": "neutral", "label": "轻声", "gesture": "·", "shape": "轻短"},
    ),
}


def _whole(symbol: str, cue: str, example: str, example_pinyin: str) -> PinyinSeed:
    return PinyinSeed(
        symbol=symbol,
        kind=PinyinKind.WHOLE,
        subcategory="whole_recognition",
        display_text=symbol,
        pronunciation_cue=f"{cue}，{example}。",
        example_text=example,
        example_pinyin=example_pinyin,
        description="这是整体认读音节，看到后直接读出来，不拆成普通拼读。",
        parent_tip="把它当作一个完整声音来听和记，不要强行拆分声母、韵母。",
        metadata={"whole_recognition": True},
    )


WHOLE_SYLLABLES = {
    item.symbol: item
    for item in (
        _whole("zhi", "知道的知", "知道", "zhī dào"),
        _whole("chi", "吃饭的吃", "吃饭", "chī fàn"),
        _whole("shi", "老师的师", "老师", "lǎo shī"),
        _whole("ri", "日光的日", "日光", "rì guāng"),
        _whole("zi", "写字的字", "写字", "xiě zì"),
        _whole("ci", "一次的次", "一次", "yí cì"),
        _whole("si", "丝巾的丝", "丝巾", "sī jīn"),
        _whole("yi", "衣服的衣", "衣服", "yī fu"),
        _whole("wu", "乌云的乌", "乌云", "wū yún"),
        _whole("yu", "小鱼的鱼", "小鱼", "xiǎo yú"),
        _whole("ye", "椰子的椰", "椰子", "yē zi"),
        _whole("yue", "月亮的月", "月亮", "yuè liang"),
        _whole("yuan", "圆圈的圆", "圆圈", "yuán quān"),
        _whole("yin", "音乐的音", "音乐", "yīn yuè"),
        _whole("yun", "白云的云", "白云", "bái yún"),
        _whole("ying", "英雄的英", "英雄", "yīng xióng"),
    )
}

PINYIN_SEEDS = tuple(
    [FINALS[key] for key in ("a", "o", "e")]
    + [TONES[key] for key in ("tone:1", "tone:2", "tone:3", "tone:4")]
    + [FINALS[key] for key in ("i", "u", "ü")]
    + [TONES["tone:neutral"]]
    + [
        INITIALS[key]
        for key in (
            "b",
            "p",
            "m",
            "f",
            "d",
            "t",
            "n",
            "l",
            "g",
            "k",
            "h",
            "j",
            "q",
            "x",
            "z",
            "c",
            "s",
            "zh",
            "ch",
            "sh",
            "r",
            "y",
            "w",
        )
    ]
    + [
        FINALS[key]
        for key in (
            "ai",
            "ei",
            "ui",
            "ao",
            "ou",
            "iu",
            "ie",
            "üe",
            "er",
            "an",
            "en",
            "in",
            "un",
            "ün",
            "ang",
            "eng",
            "ing",
            "ong",
        )
    ]
    + [
        WHOLE_SYLLABLES[key]
        for key in (
            "zhi",
            "chi",
            "shi",
            "ri",
            "zi",
            "ci",
            "si",
            "yi",
            "wu",
            "yu",
            "ye",
            "yue",
            "yuan",
            "yin",
            "yun",
            "ying",
        )
    ]
)

CONFUSING_PAIRS = (
    ("chinese:pinyin:initial:b", "chinese:pinyin:initial:p"),
    ("chinese:pinyin:initial:d", "chinese:pinyin:initial:t"),
    ("chinese:pinyin:initial:g", "chinese:pinyin:initial:k"),
    ("chinese:pinyin:initial:z", "chinese:pinyin:initial:c"),
    ("chinese:pinyin:initial:zh", "chinese:pinyin:initial:ch"),
    ("chinese:pinyin:final:an", "chinese:pinyin:final:ang"),
    ("chinese:pinyin:final:en", "chinese:pinyin:final:eng"),
    ("chinese:pinyin:final:in", "chinese:pinyin:final:ing"),
)

PRACTICE_SEEDS = (
    ("b", "a", "ba", "八，数字八。"),
    ("m", "a", "ma", "妈，妈妈的妈。"),
    ("d", "a", "da", "大，大小的大。"),
    ("l", "i", "li", "梨，鸭梨的梨。"),
    ("g", "e", "ge", "哥，哥哥的哥。"),
    ("h", "u", "hu", "湖，湖水的湖。"),
    ("p", "o", "po", "坡，山坡的坡。"),
    ("t", "u", "tu", "兔，小兔的兔。"),
    ("n", "i", "ni", "你，你好的你。"),
    ("k", "e", "ke", "科，科学的科。"),
    ("j", "ü", "ju", "居，居住的居。"),
    ("q", "ü", "qu", "区，小区的区。"),
    ("x", "ü", "xu", "需，需要的需。"),
    ("zh", "u", "zhu", "猪，小猪的猪。"),
    ("ch", "a", "cha", "茶，喝茶的茶。"),
    ("sh", "u", "shu", "书，看书的书。"),
    ("z", "u", "zu", "租，租借的租。"),
    ("c", "ao", "cao", "草，小草的草。"),
)

COURSE_UNITS = (
    (
        "a o e · 四声初体验",
        ("final:a", "final:o", "final:e", "tone:1", "tone:2", "tone:3", "tone:4"),
    ),
    ("i u ü", ("final:i", "final:u", "final:ü", "tone:neutral")),
    ("b p m f", tuple(f"initial:{item}" for item in ("b", "p", "m", "f"))),
    ("d t n l", tuple(f"initial:{item}" for item in ("d", "t", "n", "l"))),
    ("g k h", tuple(f"initial:{item}" for item in ("g", "k", "h"))),
    ("j q x", tuple(f"initial:{item}" for item in ("j", "q", "x"))),
    ("z c s", tuple(f"initial:{item}" for item in ("z", "c", "s"))),
    ("zh ch sh r", tuple(f"initial:{item}" for item in ("zh", "ch", "sh", "r"))),
    ("y w", ("initial:y", "initial:w")),
    ("ai ei ui", tuple(f"final:{item}" for item in ("ai", "ei", "ui"))),
    ("ao ou iu", tuple(f"final:{item}" for item in ("ao", "ou", "iu"))),
    ("ie üe er", tuple(f"final:{item}" for item in ("ie", "üe", "er"))),
    ("an en in un ün", tuple(f"final:{item}" for item in ("an", "en", "in", "un", "ün"))),
    ("ang eng ing ong", tuple(f"final:{item}" for item in ("ang", "eng", "ing", "ong"))),
    ("整体认读音节", tuple(f"whole:{item}" for item in WHOLE_SYLLABLES)),
    (
        "综合拼读",
        (
            "initial:b",
            "final:a",
            "initial:m",
            "initial:d",
            "initial:l",
            "final:i",
            "initial:j",
            "final:ü",
        ),
    ),
)


@dataclass
class PinyinImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    relations_created: int = 0
    practices_created: int = 0
    catalog_version: str = PINYIN_CATALOG_VERSION
    catalog_size: int = 0
    course_created: bool = False
    errors: list[str] = field(default_factory=list)


def normalize_pinyin(value: str) -> str:
    """Normalize user/admin input while keeping canonical ü visible."""

    normalized = unicodedata.normalize("NFC", value.strip().lower())
    return normalized.replace("u:", "ü").replace("v", "ü")


_TONE_MARKS = {
    "a": "āáǎà",
    "o": "ōóǒò",
    "e": "ēéěè",
    "i": "īíǐì",
    "u": "ūúǔù",
    "ü": "ǖǘǚǜ",
}
_MARK_TO_BASE = {mark: base for base, marks in _TONE_MARKS.items() for mark in marks}


def strip_tone_marks(value: str) -> str:
    return "".join(_MARK_TO_BASE.get(character, character) for character in normalize_pinyin(value))


def apply_tone_mark(value: str, tone: int | str) -> str:
    """Apply the standard a/e/ou/last-vowel Pinyin tone-mark rule."""

    base = strip_tone_marks(value)
    if tone in (0, 5, "neutral"):
        return base
    tone_number = int(tone)
    if tone_number not in (1, 2, 3, 4):
        raise ValueError("Tone must be 1, 2, 3, 4, or neutral")
    if "a" in base:
        index = base.index("a")
    elif "e" in base:
        index = base.index("e")
    elif "ou" in base:
        index = base.index("o")
    else:
        candidates = [index for index, character in enumerate(base) if character in _TONE_MARKS]
        if not candidates:
            raise ValueError("Syllable does not contain a tone-bearing vowel")
        index = candidates[-1]
    vowel = base[index]
    return f"{base[:index]}{_TONE_MARKS[vowel][tone_number - 1]}{base[index + 1 :]}"


def spell_blend(initial: str, final: str) -> tuple[str, str, str]:
    """Return normalized underlying final, displayed final, and displayed syllable."""

    normalized_initial = normalize_pinyin(initial)
    underlying_final = normalize_pinyin(final)
    display_final = underlying_final
    if normalized_initial in {"j", "q", "x"} and underlying_final.startswith("ü"):
        display_final = f"u{underlying_final[1:]}"
    return underlying_final, display_final, f"{normalized_initial}{display_final}"


def _seed_lookup_key(seed: PinyinSeed) -> str:
    if seed.kind == PinyinKind.TONE:
        tone = seed.metadata["tone"]
        return f"tone:{tone}"
    return f"{seed.kind}:{seed.symbol}"


async def _seed_course(session: AsyncSession, point_ids: dict[str, uuid.UUID]) -> bool:
    course = await session.scalar(select(Course).where(Course.system_key == PINYIN_COURSE_KEY))
    if course is not None:
        return False
    course = Course(
        subject=CourseSubject.CHINESE,
        title="拼音启蒙",
        description="语音优先、一次一个，循序学习声母、韵母、声调、整体认读和基础拼读。",
        source_type=CourseSourceType.SYSTEM,
        status=CourseStatus.ENABLED,
        version=1,
        system_key=PINYIN_COURSE_KEY,
        recommended_age_min=4,
        recommended_age_max=8,
        reference_metadata={
            "catalog_version": PINYIN_CATALOG_VERSION,
            "audio_strategy": "curated-or-safe-zh-cn-cue",
        },
    )
    session.add(course)
    await session.flush()
    for unit_order, (title, keys) in enumerate(COURSE_UNITS):
        unit = CourseUnit(
            course_id=course.id,
            title=title,
            description="先听，再看，再跟读；每次只学习少量内容。",
            order_index=unit_order,
            status=CourseStatus.ENABLED,
        )
        session.add(unit)
        await session.flush()
        activity = LearningActivity(
            course_unit_id=unit.id,
            activity_type=(
                ActivityType.GUIDED_PRACTICE
                if unit_order == len(COURSE_UNITS) - 1
                else ActivityType.KNOWLEDGE_LEARNING
            ),
            title="拼一拼" if unit_order == len(COURSE_UNITS) - 1 else f"听一听 · {title}",
            instructions="听声音、看大符号、跟读；播放本身不会被当作答对证据。",
            order_index=0,
            status=CourseStatus.ENABLED,
            content_metadata={"catalog_version": PINYIN_CATALOG_VERSION, "audio_first": True},
        )
        session.add(activity)
        await session.flush()
        for position, key in enumerate(keys):
            session.add(
                ActivityKnowledgePoint(
                    activity_id=activity.id,
                    knowledge_point_id=point_ids[key],
                    role=KnowledgePointRole.PRIMARY,
                    order_index=position,
                )
            )
    return True


async def import_pinyin_foundation(session: AsyncSession) -> PinyinImportResult:
    """Idempotently upsert curated Pinyin content without replacing canonical IDs."""

    result = PinyinImportResult(catalog_size=len(PINYIN_SEEDS))
    point_ids: dict[str, uuid.UUID] = {}
    for order_index, seed in enumerate(PINYIN_SEEDS):
        try:
            point = await session.scalar(
                select(KnowledgePoint).where(KnowledgePoint.canonical_key == seed.canonical_key)
            )
            created = point is None
            if point is None:
                point = KnowledgePoint(
                    subject=CourseSubject.CHINESE,
                    type=seed.knowledge_type,
                    status=KnowledgeStatus.ACTIVE,
                    title=seed.display_text,
                    canonical_key=seed.canonical_key,
                    source_type="curated_catalog",
                    source_reference=PINYIN_CATALOG_VERSION,
                )
                session.add(point)
                await session.flush()
            item = await session.get(PinyinItem, point.id)
            if item is None:
                item = PinyinItem(knowledge_point_id=point.id)
                session.add(item)
                created = True
            desired = {
                "symbol": seed.symbol,
                "kind": seed.kind,
                "subcategory": seed.subcategory,
                "display_text": seed.display_text,
                "pronunciation_cue": seed.pronunciation_cue,
                "example_text": seed.example_text,
                "example_pinyin": seed.example_pinyin,
                "description": seed.description,
                "parent_tip": seed.parent_tip,
                "order_index": order_index,
                "catalog_version": PINYIN_CATALOG_VERSION,
                "metadata_json": seed.metadata,
            }
            changed = created
            point_values = {
                "subject": CourseSubject.CHINESE,
                "type": seed.knowledge_type,
                "status": KnowledgeStatus.ACTIVE,
                "title": seed.display_text,
                "source_type": "curated_catalog",
                "source_reference": PINYIN_CATALOG_VERSION,
            }
            for field_name, value in point_values.items():
                if getattr(point, field_name) != value:
                    setattr(point, field_name, value)
                    changed = True
            for field_name, value in desired.items():
                if getattr(item, field_name, None) != value:
                    setattr(item, field_name, value)
                    changed = True
            result.created += int(created)
            if not created:
                result.updated += int(changed)
                result.skipped += int(not changed)
            point_ids[_seed_lookup_key(seed)] = point.id
        except Exception as error:
            result.errors.append(f"{seed.canonical_key}: {type(error).__name__}")
    if result.errors:
        await session.rollback()
        return result

    for left_key, right_key in CONFUSING_PAIRS:
        for source_key, target_key in ((left_key, right_key), (right_key, left_key)):
            source = await session.scalar(
                select(KnowledgePoint.id).where(KnowledgePoint.canonical_key == source_key)
            )
            target = await session.scalar(
                select(KnowledgePoint.id).where(KnowledgePoint.canonical_key == target_key)
            )
            assert source is not None and target is not None
            exists = await session.scalar(
                select(KnowledgeRelation.id).where(
                    KnowledgeRelation.source_id == source,
                    KnowledgeRelation.target_id == target,
                    KnowledgeRelation.relation_type == RelationType.CONFUSING,
                )
            )
            if exists is None:
                session.add(
                    KnowledgeRelation(
                        source_id=source,
                        target_id=target,
                        relation_type=RelationType.CONFUSING,
                    )
                )
                result.relations_created += 1

    for order_index, (initial, final, expected_syllable, cue) in enumerate(PRACTICE_SEEDS):
        underlying_final, display_final, syllable = spell_blend(initial, final)
        if syllable != expected_syllable:
            result.errors.append(f"Invalid practice spelling: {initial}+{final}")
            continue
        practice_key = f"chinese:pinyin:practice:{initial}-{underlying_final}"
        practice = await session.scalar(
            select(PinyinPracticeItem).where(PinyinPracticeItem.practice_key == practice_key)
        )
        if practice is None:
            practice = PinyinPracticeItem(id=uuid.uuid4(), practice_key=practice_key)
            session.add(practice)
            result.practices_created += 1
        practice.initial_knowledge_point_id = point_ids[f"initial:{initial}"]
        practice.final_knowledge_point_id = point_ids[f"final:{final}"]
        practice.display_syllable = syllable
        practice.underlying_final = underlying_final
        practice.display_final = display_final
        practice.pronunciation_cue = cue
        practice.order_index = order_index
        practice.catalog_version = PINYIN_CATALOG_VERSION
        practice.metadata_json = {
            "underlying_final": underlying_final,
            "display_final": display_final,
            "umlaut_omitted": underlying_final != display_final,
        }

    release = await session.scalar(
        select(PinyinCatalogRelease).where(
            PinyinCatalogRelease.catalog_version == PINYIN_CATALOG_VERSION
        )
    )
    if release is None:
        release = PinyinCatalogRelease(
            catalog_version=PINYIN_CATALOG_VERSION,
            source_name="Growth Learning curated child Pinyin foundation",
            source_reference="docs/PINYIN_CANONICAL_CATALOG.md",
            imported_at=datetime.now(UTC),
            item_count=len(PINYIN_SEEDS),
            practice_item_count=len(PRACTICE_SEEDS),
            is_current=True,
            metadata_json={
                "subject": "chinese",
                "audio_policy": "curated audio, then safe Chinese pronunciation cue",
            },
        )
        session.add(release)
    else:
        release.item_count = len(PINYIN_SEEDS)
        release.practice_item_count = len(PRACTICE_SEEDS)
        release.is_current = True
    result.course_created = await _seed_course(session, point_ids)
    if result.errors:
        await session.rollback()
        return result
    await session.commit()
    return result


async def pinyin_catalog_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(select(PinyinItem.kind, func.count()).group_by(PinyinItem.kind))
    ).all()
    return {kind: int(count) for kind, count in rows}


async def list_pinyin_items(
    session: AsyncSession,
    *,
    kind: str | None = None,
    subcategory: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 100,
    public_only: bool = False,
) -> tuple[list[tuple[KnowledgePoint, PinyinItem]], int, int]:
    filters = []
    if kind:
        filters.append(PinyinItem.kind == kind)
    if subcategory:
        filters.append(PinyinItem.subcategory == subcategory)
    if status:
        filters.append(KnowledgePoint.status == status)
    if public_only:
        filters.append(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            PinyinItem.symbol.ilike(term)
            | PinyinItem.example_text.ilike(term)
            | KnowledgePoint.canonical_key.ilike(term)
        )
    total = int(
        await session.scalar(
            select(func.count()).select_from(PinyinItem).join(KnowledgePoint).where(*filters)
        )
        or 0
    )
    rows = list(
        (
            await session.execute(
                select(KnowledgePoint, PinyinItem)
                .join(PinyinItem)
                .where(*filters)
                .order_by(PinyinItem.order_index)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return rows, total, max(1, math.ceil(total / page_size))
