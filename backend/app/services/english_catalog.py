"""Project-curated, idempotent English Foundation V1 catalog."""

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    ActivityType,
    Course,
    CourseSourceType,
    CourseStatus,
    CourseSubject,
    CourseUnit,
    EnglishCatalogRelease,
    EnglishItem,
    EnglishPracticeItem,
    KnowledgePoint,
    KnowledgePointRole,
    KnowledgeStatus,
    KnowledgeType,
    LearningActivity,
    Subject,
)

ENGLISH_CATALOG_VERSION = "english-foundation-v1"
ENGLISH_GENERATOR_VERSION = "english-generator-v1"
ENGLISH_COURSE_KEY = "system-english-foundation-v1"
ENGLISH_NAMESPACE = uuid.UUID("84cf0539-fad2-59f0-865d-629261e61c91")
ENGLISH_TEMPLATE_NAMESPACE = uuid.UUID("f8faee52-22fb-58ac-bcfb-e9e727f39797")
DEFAULT_ENGLISH_ACCENT = "en-US"


@dataclass(frozen=True)
class EnglishSeed:
    kind: str
    text: str
    normalized_text: str
    meaning_zh: str
    category: str
    child_hint_zh: str
    parent_tip: str
    example_text: str | None = None
    example_meaning_zh: str | None = None
    image_key: str | None = None
    visual_key: str | None = None
    visual_type: str = "emoji_fallback"
    audio_key: str | None = None
    audio_accent: str = DEFAULT_ENGLISH_ACCENT
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def canonical_key(self) -> str:
        return f"english:{self.kind}:{self.normalized_text}"

    @property
    def title(self) -> str:
        return self.text

    @property
    def knowledge_type(self) -> str:
        return {
            "letter": KnowledgeType.ENGLISH_LETTER,
            "word": KnowledgeType.ENGLISH_WORD,
            "phonics": KnowledgeType.ENGLISH_PHONICS,
            "phrase": KnowledgeType.ENGLISH_PHRASE,
        }[self.kind]


CATEGORY_LABELS = {
    "greetings": "Hello! 基本问候",
    "animals": "Animals 动物",
    "body": "My Body 身体",
    "colors": "Colors 颜色",
    "family": "My Family 家庭",
    "toys": "Toys 玩具",
    "home": "Home 家中物品",
    "food": "Food & Drink 食物饮料",
    "actions": "Actions 动作",
    "numbers": "Numbers 数字表达",
    "shapes": "Shapes 图形",
    "nature": "Nature 自然",
    "feelings": "Feelings 感受",
    "daily-life": "Daily Life 日常表达",
    "letters": "Letters 字母",
    "short-vowel": "Short Vowels 短元音",
    "consonant-sound": "Consonant Sounds 辅音开头音",
    "cvc": "CVC Blending 基础拼读",
    "functional-phrase": "Simple Phrases 简单表达",
    "short-reading": "Very Short Reading 简短阅读",
}


WORD_GROUPS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "animals": (
        ("cat", "猫", "🐱"),
        ("dog", "狗", "🐶"),
        ("bird", "鸟", "🐦"),
        ("fish", "鱼", "🐟"),
        ("duck", "鸭子", "🦆"),
        ("rabbit", "兔子", "🐰"),
        ("cow", "奶牛", "🐄"),
        ("pig", "猪", "🐷"),
        ("horse", "马", "🐴"),
        ("sheep", "绵羊", "🐑"),
        ("frog", "青蛙", "🐸"),
        ("bear", "熊", "🐻"),
    ),
    "body": (
        ("head", "头", "🙂"),
        ("eye", "眼睛", "👁️"),
        ("ear", "耳朵", "👂"),
        ("nose", "鼻子", "👃"),
        ("mouth", "嘴巴", "👄"),
        ("hand", "手", "✋"),
        ("foot", "脚", "🦶"),
        ("arm", "手臂", "💪"),
        ("leg", "腿", "🦵"),
        ("hair", "头发", "🧒"),
    ),
    "family": (
        ("mom", "妈妈", "👩"),
        ("dad", "爸爸", "👨"),
        ("baby", "宝宝", "👶"),
        ("brother", "兄弟", "👦"),
        ("sister", "姐妹", "👧"),
        ("grandma", "奶奶或外婆", "👵"),
        ("grandpa", "爷爷或外公", "👴"),
        ("family", "家人", "👪"),
    ),
    "colors": (
        ("red", "红色", "#ef4444"),
        ("blue", "蓝色", "#3b82f6"),
        ("yellow", "黄色", "#facc15"),
        ("green", "绿色", "#22c55e"),
        ("black", "黑色", "#111827"),
        ("white", "白色", "#ffffff"),
        ("orange", "橙色", "#f97316"),
        ("purple", "紫色", "#a855f7"),
        ("pink", "粉色", "#ec4899"),
        ("brown", "棕色", "#92400e"),
    ),
    "food": (
        ("apple", "苹果", "🍎"),
        ("banana", "香蕉", "🍌"),
        ("egg", "鸡蛋", "🥚"),
        ("milk", "牛奶", "🥛"),
        ("water", "水", "💧"),
        ("bread", "面包", "🍞"),
        ("rice", "米饭", "🍚"),
        ("cake", "蛋糕", "🍰"),
        ("cookie", "饼干", "🍪"),
        ("juice", "果汁", "🧃"),
        ("grape", "葡萄", "🍇"),
        ("pear", "梨", "🍐"),
        ("carrot", "胡萝卜", "🥕"),
        ("strawberry", "草莓", "🍓"),
    ),
    "toys": (
        ("ball", "球", "⚽"),
        ("doll", "玩偶", "🪆"),
        ("car", "小汽车", "🚗"),
        ("kite", "风筝", "🪁"),
        ("block", "积木", "🧱"),
        ("book", "书", "📘"),
        ("bike", "自行车", "🚲"),
        ("train", "火车", "🚆"),
    ),
    "home": (
        ("bed", "床", "🛏️"),
        ("chair", "椅子", "🪑"),
        ("table", "桌子", "🟫"),
        ("door", "门", "🚪"),
        ("window", "窗户", "🪟"),
        ("cup", "杯子", "🥤"),
        ("spoon", "勺子", "🥄"),
        ("plate", "盘子", "🍽️"),
        ("box", "盒子", "📦"),
        ("lamp", "灯", "💡"),
    ),
    "actions": (
        ("run", "跑", "🏃"),
        ("jump", "跳", "🤸"),
        ("sit", "坐下", "🪑"),
        ("stand", "站立", "🧍"),
        ("eat", "吃", "🍽️"),
        ("drink", "喝", "🥤"),
        ("look", "看", "👀"),
        ("listen", "听", "👂"),
        ("walk", "走", "🚶"),
        ("clap", "拍手", "👏"),
        ("open", "打开", "📖"),
        ("close", "关上", "📕"),
        ("wash", "清洗", "🧼"),
        ("sleep", "睡觉", "😴"),
    ),
    "numbers": (
        ("one", "一", "1"),
        ("two", "二", "2"),
        ("three", "三", "3"),
        ("four", "四", "4"),
        ("five", "五", "5"),
        ("six", "六", "6"),
        ("seven", "七", "7"),
        ("eight", "八", "8"),
        ("nine", "九", "9"),
        ("ten", "十", "10"),
    ),
    "shapes": (
        ("circle", "圆形", "circle"),
        ("square", "正方形", "square"),
        ("triangle", "三角形", "triangle"),
        ("rectangle", "长方形", "rectangle"),
        ("star", "星形", "star"),
        ("heart", "心形", "heart"),
    ),
    "nature": (
        ("sun", "太阳", "☀️"),
        ("moon", "月亮", "🌙"),
        ("sky", "天空", "🌤️"),
        ("rain", "雨", "🌧️"),
        ("cloud", "云", "☁️"),
        ("tree", "树", "🌳"),
        ("flower", "花", "🌼"),
        ("grass", "草", "🌱"),
        ("river", "河流", "🌊"),
        ("leaf", "叶子", "🍃"),
    ),
    "feelings": (
        ("happy", "开心", "😊"),
        ("sad", "难过", "😢"),
        ("angry", "生气", "😠"),
        ("tired", "累", "🥱"),
        ("scared", "害怕", "😨"),
        ("good", "很好", "👍"),
        ("cold", "冷", "🥶"),
        ("hot", "热", "🥵"),
    ),
    "daily-life": (
        ("hello", "你好", "👋"),
        ("goodbye", "再见", "👋"),
        ("please", "请", "🙏"),
        ("thanks", "谢谢", "💛"),
        ("yes", "是", "✅"),
        ("no", "不是", "⭕"),
        ("morning", "早晨", "🌅"),
        ("night", "夜晚", "🌙"),
        ("school", "学校", "🏫"),
        ("day", "一天", "🌞"),
        ("friend", "朋友", "🧑‍🤝‍🧑"),
        ("play", "玩", "🛝"),
    ),
}

STATIC_VISUAL_WORDS = frozenset({"cat", "dog", "apple", "ball", "sun", "moon"})


def _word_seeds() -> tuple[EnglishSeed, ...]:
    seeds: list[EnglishSeed] = []
    for category, rows in WORD_GROUPS.items():
        for text, meaning, visual in rows:
            visual_type = "emoji_fallback"
            image_key = None
            if text in STATIC_VISUAL_WORDS:
                visual_type = "static_image"
                image_key = f"/english/visuals/{text}.svg"
            elif category == "colors":
                visual_type = "color_swatch"
            elif category == "shapes":
                visual_type = "shape"
            elif category == "numbers":
                visual_type = "icon"
            seeds.append(
                EnglishSeed(
                    kind="word",
                    text=text,
                    normalized_text=text.lower(),
                    meaning_zh=meaning,
                    category=category,
                    child_hint_zh="先听声音，再看看它表示的物体、动作或意思。",
                    parent_tip=f"先让孩子听 {text}，再指向真实物品或动作，不必先背中文翻译。",
                    example_text=f"I see {text}."
                    if category not in {"actions", "colors"}
                    else text,
                    example_meaning_zh=f"我看见{meaning}。"
                    if category not in {"actions", "colors"}
                    else meaning,
                    image_key=image_key,
                    visual_key=visual,
                    visual_type=visual_type,
                    metadata={
                        "source": "Growth Learning project-curated",
                        "license": "project-owned",
                        "attribution": None,
                    },
                )
            )
    return tuple(seeds)


LETTER_SEEDS = tuple(
    EnglishSeed(
        kind="letter",
        text=letter,
        normalized_text=letter.lower(),
        meaning_zh=f"英文字母 {letter}",
        category="letters",
        child_hint_zh=f"看看大写 {letter} 和小写 {letter.lower()}，再听字母名称。",
        parent_tip="字母名称和字母在单词中的声音是两个知识点，请不要混在一起。",
        visual_key=f"letter:{letter}",
        visual_type="icon",
        example_text=f"{letter}  {letter.lower()}",
        example_meaning_zh="大写和小写是一对。",
        metadata={"uppercase": letter, "lowercase": letter.lower(), "audio_role": "letter_name"},
    )
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


SHORT_VOWELS = (
    ("a", "apple", "苹果"),
    ("e", "egg", "鸡蛋"),
    ("i", "igloo", "冰屋"),
    ("o", "octopus", "章鱼"),
    ("u", "umbrella", "雨伞"),
)
CONSONANT_SOUNDS = (
    ("b", "ball", "球"),
    ("c", "cat", "猫"),
    ("d", "dog", "狗"),
    ("f", "fish", "鱼"),
    ("g", "goat", "山羊"),
    ("h", "hat", "帽子"),
    ("j", "jam", "果酱"),
    ("k", "kite", "风筝"),
    ("l", "leaf", "叶子"),
    ("m", "moon", "月亮"),
    ("n", "nose", "鼻子"),
    ("p", "pig", "猪"),
    ("r", "rabbit", "兔子"),
    ("s", "sun", "太阳"),
    ("t", "top", "陀螺"),
    ("v", "van", "面包车"),
    ("w", "water", "水"),
    ("y", "yellow", "黄色"),
    ("z", "zebra", "斑马"),
)
CVC_WORDS = (
    "cat",
    "hat",
    "map",
    "man",
    "bag",
    "fan",
    "bed",
    "red",
    "hen",
    "pen",
    "pig",
    "sit",
    "fin",
    "lip",
    "dog",
    "log",
    "hop",
    "top",
    "sun",
    "cup",
)


def _phonics_seeds() -> tuple[EnglishSeed, ...]:
    seeds: list[EnglishSeed] = []
    for symbol, example, meaning in SHORT_VOWELS:
        seeds.append(
            EnglishSeed(
                kind="phonics",
                text=symbol,
                normalized_text=f"short-{symbol}",
                meaning_zh=f"短元音 {symbol} 的声音",
                category="short-vowel",
                child_hint_zh=f"听 {example}，留意字母 {symbol} 的声音。",
                parent_tip="如果没有正式音素音频，只播放示例词，不用字母名称代替音素。",
                example_text=example,
                example_meaning_zh=meaning,
                visual_key=next(
                    (row[2] for rows in WORD_GROUPS.values() for row in rows if row[0] == example),
                    "🔊",
                ),
                metadata={
                    "grapheme": symbol,
                    "example_word": example,
                    "audio_role": "safe_example_word",
                },
            )
        )
    for symbol, example, meaning in CONSONANT_SOUNDS:
        seeds.append(
            EnglishSeed(
                kind="phonics",
                text=symbol,
                normalized_text=f"consonant-{symbol}",
                meaning_zh=f"字母 {symbol} 的开头音",
                category="consonant-sound",
                child_hint_zh=f"听 {example}，留意开头的声音。",
                parent_tip=f"播放示例词 {example}；缺少正式音素音频时绝不播放字母名称代替。",
                example_text=example,
                example_meaning_zh=meaning,
                visual_key=next(
                    (row[2] for rows in WORD_GROUPS.values() for row in rows if row[0] == example),
                    "🔊",
                ),
                metadata={
                    "grapheme": symbol,
                    "example_word": example,
                    "audio_role": "safe_example_word",
                },
            )
        )
    for word in CVC_WORDS:
        seeds.append(
            EnglishSeed(
                kind="phonics",
                text=word,
                normalized_text=f"cvc-{word}",
                meaning_zh=f"拼读 {word}",
                category="cvc",
                child_hint_zh=f"把 {' · '.join(word)} 慢慢连起来，再听完整的 {word}。",
                parent_tip="先分音，再自然连读；不要求孩子背音标或追求速度。",
                example_text=word,
                example_meaning_zh=next(
                    (row[1] for rows in WORD_GROUPS.values() for row in rows if row[0] == word),
                    "简单拼读词",
                ),
                image_key=(f"/english/visuals/{word}.svg" if word in STATIC_VISUAL_WORDS else None),
                visual_key=next(
                    (row[2] for rows in WORD_GROUPS.values() for row in rows if row[0] == word),
                    "🔤",
                ),
                visual_type=("static_image" if word in STATIC_VISUAL_WORDS else "emoji_fallback"),
                metadata={
                    "segments": list(word),
                    "example_word": word,
                    "audio_role": "blend_word",
                    "cvc": True,
                },
            )
        )
    return tuple(seeds)


PHRASE_ROWS = (
    ("hello", "Hello.", "你好。", "greetings", "👋"),
    ("goodbye", "Goodbye.", "再见。", "greetings", "👋"),
    ("thank-you", "Thank you.", "谢谢。", "greetings", "💛"),
    ("good-morning", "Good morning.", "早上好。", "greetings", "🌅"),
    ("i-like-it", "I like it.", "我喜欢它。", "functional-phrase", "👍"),
    ("give-me-the-ball", "Give me the ball.", "请把球给我。", "functional-phrase", "⚽"),
    ("sit-down", "Sit down.", "请坐下。", "functional-phrase", "🪑"),
    ("stand-up", "Stand up.", "请站起来。", "functional-phrase", "🧍"),
    ("look-at-me", "Look at me.", "看着我。", "functional-phrase", "👀"),
    ("this-is-a-dog", "This is a dog.", "这是一只狗。", "functional-phrase", "🐶"),
    ("i-see-a-cat", "I see a cat.", "我看见一只猫。", "short-reading", "🐱"),
    ("a-red-ball", "A red ball.", "一个红色的球。", "short-reading", "🔴"),
    ("i-like-milk", "I like milk.", "我喜欢牛奶。", "short-reading", "🥛"),
    ("it-is-blue", "It is blue.", "它是蓝色的。", "short-reading", "🔵"),
    ("the-sun-is-hot", "The sun is hot.", "太阳很热。", "short-reading", "☀️"),
)
PHRASE_SEEDS = tuple(
    EnglishSeed(
        kind="phrase",
        text=text,
        normalized_text=key,
        meaning_zh=meaning,
        category=category,
        child_hint_zh="先听整句话，再看图片或动作理解，不需要逐词翻译。",
        parent_tip="在真实情境中自然重复这句话；先听懂和使用，不讲复杂语法。",
        example_text=text,
        example_meaning_zh=meaning,
        visual_key=visual,
        metadata={"audio_role": "phrase", "template_generated": True},
    )
    for key, text, meaning, category, visual in PHRASE_ROWS
)

WORD_SEEDS = _word_seeds()
PHONICS_SEEDS = _phonics_seeds()
ENGLISH_SEEDS = WORD_SEEDS + LETTER_SEEDS + PHONICS_SEEDS + PHRASE_SEEDS
assert len(WORD_SEEDS) == 132
assert len(LETTER_SEEDS) == 26
assert len(PHONICS_SEEDS) == 44
assert len(PHRASE_SEEDS) == 15
assert len({seed.canonical_key for seed in ENGLISH_SEEDS}) == len(ENGLISH_SEEDS)


def _keys(kind: str | None = None, category: str | None = None) -> tuple[str, ...]:
    return tuple(
        seed.canonical_key
        for seed in ENGLISH_SEEDS
        if (kind is None or seed.kind == kind) and (category is None or seed.category == category)
    )


COURSE_UNITS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Hello! 基本问候", _keys("phrase", "greetings") + _keys("word", "daily-life")),
    ("Animals 动物", _keys("word", "animals")),
    ("My Body 身体", _keys("word", "body")),
    ("Colors 颜色", _keys("word", "colors")),
    ("My Family 家庭", _keys("word", "family")),
    (
        "Toys & Things 玩具和物品",
        _keys("word", "toys") + _keys("word", "home") + _keys("word", "shapes"),
    ),
    ("Food & Drink 食物饮料", _keys("word", "food")),
    ("Actions 动作", _keys("word", "actions")),
    ("Numbers 1～10 英语表达", _keys("word", "numbers")),
    ("Nature 自然", _keys("word", "nature")),
    ("Feelings 简单感受", _keys("word", "feelings")),
    ("Letters A～F", tuple(seed.canonical_key for seed in LETTER_SEEDS[:6])),
    ("Letters G～L", tuple(seed.canonical_key for seed in LETTER_SEEDS[6:12])),
    ("Letters M～R", tuple(seed.canonical_key for seed in LETTER_SEEDS[12:18])),
    ("Letters S～Z", tuple(seed.canonical_key for seed in LETTER_SEEDS[18:])),
    ("Short Vowels", _keys("phonics", "short-vowel")),
    ("Basic Consonant Sounds", _keys("phonics", "consonant-sound")),
    ("CVC Blending 1", tuple(seed.canonical_key for seed in PHONICS_SEEDS[24:34])),
    ("CVC Blending 2", tuple(seed.canonical_key for seed in PHONICS_SEEDS[34:])),
    ("Simple Phrases", _keys("phrase", "functional-phrase")),
    ("Very Short Reading", _keys("phrase", "short-reading")),
)
assert len(COURSE_UNITS) == 21


@dataclass
class EnglishImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    practice_items_created: int = 0
    catalog_version: str = ENGLISH_CATALOG_VERSION
    catalog_size: int = len(ENGLISH_SEEDS)
    letter_count: int = len(LETTER_SEEDS)
    word_count: int = len(WORD_SEEDS)
    phonics_count: int = len(PHONICS_SEEDS)
    phrase_count: int = len(PHRASE_SEEDS)
    practice_item_count: int = 0
    course_created: bool = False
    errors: list[str] = field(default_factory=list)


def stable_english_point_id(canonical_key: str) -> uuid.UUID:
    return uuid.uuid5(ENGLISH_NAMESPACE, canonical_key)


def stable_english_template_id(template_key: str) -> uuid.UUID:
    return uuid.uuid5(ENGLISH_TEMPLATE_NAMESPACE, template_key)


def practice_kinds(seed: EnglishSeed) -> tuple[str, ...]:
    if seed.kind == "word":
        return ("listen_choose_visual", "visual_choose_audio")
    if seed.kind == "letter":
        return ("letter_match", "case_match")
    if seed.kind == "phonics":
        return ("blending",) if seed.category == "cvc" else ("phonics_choose",)
    return ("phrase_listening",)


def distractor_keys(seed: EnglishSeed) -> list[str]:
    peers = [
        item.canonical_key
        for item in ENGLISH_SEEDS
        if item.kind == seed.kind
        and item.canonical_key != seed.canonical_key
        and (item.category == seed.category or seed.kind in {"letter", "phrase"})
    ]
    if len(peers) < 2:
        peers.extend(
            item.canonical_key
            for item in ENGLISH_SEEDS
            if item.kind == seed.kind
            and item.canonical_key != seed.canonical_key
            and item.canonical_key not in peers
        )
    return peers


async def _seed_course(session: AsyncSession, point_ids: dict[str, uuid.UUID]) -> bool:
    existing = await session.scalar(
        select(Course.id).where(Course.system_key == ENGLISH_COURSE_KEY)
    )
    if existing is not None:
        return False
    course = Course(
        subject=CourseSubject.ENGLISH,
        title="英语启蒙",
        description="Growth Learning 项目设计的声音与视觉优先英语启蒙路径。",
        source_type=CourseSourceType.SYSTEM,
        status=CourseStatus.ENABLED,
        version=1,
        system_key=ENGLISH_COURSE_KEY,
        recommended_age_min=3,
        recommended_age_max=9,
        reference_metadata={
            "catalog_version": ENGLISH_CATALOG_VERSION,
            "project_curated": True,
            "official_standard": False,
        },
    )
    session.add(course)
    await session.flush()
    for unit_order, (title, keys) in enumerate(COURSE_UNITS):
        unit = CourseUnit(
            course_id=course.id,
            title=title,
            description="从听声音、看图和动作理解开始，再逐渐连接字母与拼读。",
            order_index=unit_order,
            status=CourseStatus.ENABLED,
        )
        session.add(unit)
        await session.flush()
        activity = LearningActivity(
            course_unit_id=unit.id,
            activity_type=ActivityType.GUIDED_PRACTICE,
            title=f"听一听 · {title}",
            instructions="一次一个核心内容；重播声音不算提示，中文答案提示才算。",
            order_index=0,
            status=CourseStatus.ENABLED,
            content_metadata={
                "catalog_version": ENGLISH_CATALOG_VERSION,
                "audio_first": True,
                "default_accent": DEFAULT_ENGLISH_ACCENT,
            },
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


async def import_english_foundation(session: AsyncSession) -> EnglishImportResult:
    """Import stable English identities, templates, and the 21-unit project path."""

    result = EnglishImportResult()
    point_ids: dict[str, uuid.UUID] = {}
    for order_index, seed in enumerate(ENGLISH_SEEDS):
        try:
            point = await session.scalar(
                select(KnowledgePoint).where(KnowledgePoint.canonical_key == seed.canonical_key)
            )
            created = point is None
            if point is None:
                point = KnowledgePoint(
                    id=stable_english_point_id(seed.canonical_key),
                    subject=Subject.ENGLISH,
                    type=seed.knowledge_type,
                    status=KnowledgeStatus.ACTIVE,
                    title=seed.title,
                    canonical_key=seed.canonical_key,
                    source_type="project_curated",
                    source_reference=ENGLISH_CATALOG_VERSION,
                )
                session.add(point)
                await session.flush()
            item = await session.get(EnglishItem, point.id)
            if item is None:
                item = EnglishItem(knowledge_point_id=point.id)
                session.add(item)
                created = True
            point_values = {
                "subject": Subject.ENGLISH,
                "type": seed.knowledge_type,
                "status": KnowledgeStatus.ACTIVE,
                "title": seed.title,
                "source_type": "project_curated",
                "source_reference": ENGLISH_CATALOG_VERSION,
            }
            item_values = {
                "kind": seed.kind,
                "text": seed.text,
                "normalized_text": seed.normalized_text,
                "meaning_zh": seed.meaning_zh,
                "child_hint_zh": seed.child_hint_zh,
                "parent_tip": seed.parent_tip,
                "category": seed.category,
                "example_text": seed.example_text,
                "example_meaning_zh": seed.example_meaning_zh,
                "image_key": seed.image_key,
                "visual_key": seed.visual_key,
                "visual_type": seed.visual_type,
                "audio_key": seed.audio_key,
                "audio_accent": seed.audio_accent,
                "order_index": order_index,
                "catalog_version": ENGLISH_CATALOG_VERSION,
                "metadata_json": seed.metadata,
            }
            changed = created
            for target, values in ((point, point_values), (item, item_values)):
                for name, value in values.items():
                    if getattr(target, name, None) != value:
                        setattr(target, name, value)
                        changed = True
            result.created += int(created)
            if not created:
                result.updated += int(changed)
                result.skipped += int(not changed)
            point_ids[seed.canonical_key] = point.id
            for template_order, practice_kind in enumerate(practice_kinds(seed)):
                template_key = f"{seed.canonical_key}:{practice_kind}:v1"
                practice = await session.scalar(
                    select(EnglishPracticeItem).where(
                        EnglishPracticeItem.template_key == template_key
                    )
                )
                if practice is None:
                    practice = EnglishPracticeItem(
                        id=stable_english_template_id(template_key),
                        knowledge_point_id=point.id,
                        template_key=template_key,
                    )
                    session.add(practice)
                    result.practice_items_created += 1
                practice.practice_kind = practice_kind
                practice.generator_version = ENGLISH_GENERATOR_VERSION
                practice.config_json = {
                    "target_key": seed.canonical_key,
                    "distractor_keys": distractor_keys(seed),
                    "dimension": {
                        "listen_choose_visual": "listening",
                        "visual_choose_audio": "meaning",
                        "letter_match": "letter_name",
                        "case_match": "case_matching",
                        "phonics_choose": "sound_recognition",
                        "blending": "decoding",
                        "phrase_listening": "listening",
                    }[practice_kind],
                }
                practice.status = KnowledgeStatus.ACTIVE
                practice.order_index = template_order
        except Exception as error:
            result.errors.append(f"{seed.canonical_key}: {type(error).__name__}: {error}")
    if result.errors:
        await session.rollback()
        return result

    result.practice_item_count = int(
        await session.scalar(
            select(func.count())
            .select_from(EnglishPracticeItem)
            .where(EnglishPracticeItem.status == KnowledgeStatus.ACTIVE)
        )
        or 0
    )
    release = await session.scalar(
        select(EnglishCatalogRelease).where(
            EnglishCatalogRelease.catalog_version == ENGLISH_CATALOG_VERSION
        )
    )
    if release is None:
        release = EnglishCatalogRelease(catalog_version=ENGLISH_CATALOG_VERSION)
        session.add(release)
    release.source_name = "Growth Learning project-curated English Foundation"
    release.source_reference = "docs/ENGLISH_LEARNING_MODEL_V1.md"
    release.imported_at = datetime.now(UTC)
    release.item_count = len(ENGLISH_SEEDS)
    release.practice_item_count = result.practice_item_count
    release.is_current = True
    release.metadata_json = {
        "subject": "english",
        "knowledge_types": [
            "english_letter",
            "english_word",
            "english_phonics",
            "english_phrase",
        ],
        "default_accent": DEFAULT_ENGLISH_ACCENT,
        "project_curated": True,
        "official_standard": False,
    }
    result.course_created = await _seed_course(session, point_ids)
    await session.commit()
    return result


async def english_catalog_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(select(EnglishItem.kind, func.count()).group_by(EnglishItem.kind))
    ).all()
    return {str(kind): int(count) for kind, count in rows}


async def list_english_items(
    session: AsyncSession,
    *,
    kind: str | None = None,
    category: str | None = None,
    status: str | None = None,
    audio_status: str | None = None,
    visual_status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 100,
    public_only: bool = False,
) -> tuple[list[tuple[KnowledgePoint, EnglishItem]], int, int]:
    statement = select(KnowledgePoint, EnglishItem).join(
        EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id
    )
    filters = [KnowledgePoint.subject == Subject.ENGLISH]
    if public_only:
        filters.append(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
    elif status:
        filters.append(KnowledgePoint.status == status)
    if kind:
        filters.append(EnglishItem.kind == kind)
    if category:
        filters.append(EnglishItem.category == category)
    if audio_status == "curated":
        filters.append(EnglishItem.audio_key.is_not(None))
    elif audio_status == "tts":
        filters.extend([EnglishItem.audio_key.is_(None), EnglishItem.kind != "phonics"])
    elif audio_status == "phonics_missing":
        filters.extend([EnglishItem.audio_key.is_(None), EnglishItem.kind == "phonics"])
    if visual_status == "static":
        filters.append(EnglishItem.visual_type == "static_image")
    elif visual_status == "fallback":
        filters.append(EnglishItem.visual_type == "emoji_fallback")
    elif visual_status == "missing":
        filters.extend([EnglishItem.image_key.is_(None), EnglishItem.visual_key.is_(None)])
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                EnglishItem.text.ilike(pattern),
                EnglishItem.meaning_zh.ilike(pattern),
                KnowledgePoint.canonical_key.ilike(pattern),
            )
        )
    statement = statement.where(*filters)
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await session.execute(
            statement.order_by(EnglishItem.order_index)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return list(rows), total, max(1, math.ceil(total / page_size))
