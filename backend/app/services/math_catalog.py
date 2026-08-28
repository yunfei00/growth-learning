"""Project-curated Math Foundation V1 catalog and idempotent importer."""

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
    KnowledgePoint,
    KnowledgePointRole,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    LearningActivity,
    MathCatalogRelease,
    MathProblemTemplate,
    MathSkill,
    RelationType,
    Subject,
)

MATH_CATALOG_VERSION = "math-foundation-v1"
MATH_GENERATOR_VERSION = "math-generator-v1"
MATH_COURSE_KEY = "system-math-foundation-v1"
MATH_NAMESPACE = uuid.UUID("19f8de86-6292-54bd-84f7-29865a189612")
MATH_TEMPLATE_NAMESPACE = uuid.UUID("f2cf51f7-e0db-52a4-bf1a-160325842daa")


@dataclass(frozen=True)
class MathSkillSeed:
    domain: str
    skill_code: str
    title: str
    child_instruction: str
    parent_tip: str
    representation_types: tuple[str, ...]
    generator_key: str
    difficulty_level: int = 1
    recommended_age_min: int | None = 3
    recommended_age_max: int | None = 8
    settings: dict[str, object] = field(default_factory=dict)

    @property
    def canonical_key(self) -> str:
        return f"math:{self.domain}:{self.skill_code}"


def _seed(
    domain: str,
    code: str,
    title: str,
    instruction: str,
    tip: str,
    representations: tuple[str, ...],
    generator: str,
    *,
    difficulty: int = 1,
    settings: dict[str, object] | None = None,
) -> MathSkillSeed:
    return MathSkillSeed(
        domain=domain,
        skill_code=code,
        title=title,
        child_instruction=instruction,
        parent_tip=tip,
        representation_types=representations,
        generator_key=generator,
        difficulty_level=difficulty,
        settings=settings or {},
    )


CLASSIFICATION = (
    _seed(
        "classification",
        "match-same",
        "配对一样的物品",
        "找一找，哪两个是一样的？",
        "先让孩子说出相同的地方，再进行配对。",
        ("shape", "objects"),
        "classification_v1",
    ),
    _seed(
        "classification",
        "find-different",
        "找出不一样",
        "哪一个和其他的不一样？",
        "不要求速度，鼓励孩子说出分类理由。",
        ("shape", "objects"),
        "classification_v1",
        difficulty=2,
    ),
    _seed(
        "classification",
        "sort-by-shape",
        "按形状分类",
        "把形状相同的放在一起。",
        "可用积木、瓶盖等真实物品继续练习。",
        ("shape", "objects"),
        "classification_v1",
    ),
    _seed(
        "classification",
        "sort-by-size",
        "按大小分类",
        "把大的和小的分一分。",
        "大小需要在同类物品中比较，不把名称当答案。",
        ("objects", "shape"),
        "classification_v1",
    ),
)

QUANTITY = tuple(
    _seed(
        "quantity",
        f"recognize-{number}",
        f"感知数量 {number}",
        "这里有几个？",
        "先鼓励一眼看出数量，需要时再逐个点数。",
        ("dots", "objects"),
        "quantity_choice_v1",
        settings={"minimum": number, "maximum": number},
    )
    for number in range(1, 6)
) + (
    _seed(
        "quantity",
        "count-within-3",
        "数清 3 以内数量",
        "数一数，这里有几个？",
        "让孩子边指边数，并理解最后一个数表示总数。",
        ("objects", "dots"),
        "quantity_choice_v1",
        settings={"minimum": 0, "maximum": 3},
    ),
    _seed(
        "quantity",
        "count-within-5",
        "数清 5 以内数量",
        "数一数，这里有几个？",
        "改变物品排列，避免只记住固定点阵。",
        ("objects", "dots"),
        "quantity_choice_v1",
        difficulty=2,
        settings={"minimum": 0, "maximum": 5},
    ),
    _seed(
        "quantity",
        "count-within-10",
        "数清 10 以内数量",
        "慢慢数一数，一共有几个？",
        "可以把数过的物品移到一边，避免重复。",
        ("objects", "dots", "ten_frame"),
        "quantity_choice_v1",
        difficulty=3,
        settings={"minimum": 0, "maximum": 10},
    ),
    _seed(
        "quantity",
        "subitize-within-5",
        "一眼看出 5 以内数量",
        "不一个个数，你看到了几个？",
        "使用不同排列，建立数量感而不是背骰子图案。",
        ("dots", "objects"),
        "quantity_choice_v1",
        difficulty=2,
        settings={"minimum": 1, "maximum": 5, "subitize": True},
    ),
    _seed(
        "quantity",
        "ten-frame-within-10",
        "用十格框看数量",
        "十格框里有几个点？",
        "引导孩子看成五个和另外几个，例如 7 是 5 和 2。",
        ("ten_frame",),
        "quantity_choice_v1",
        difficulty=3,
        settings={"minimum": 5, "maximum": 10},
    ),
)

NUMBER_SYMBOL = tuple(
    _seed(
        "number_symbol",
        f"recognize-{number}",
        f"认识数字 {number}",
        f"哪个是数字 {number}？",
        ("0 表示一个也没有。" if number == 0 else "把数字符号和真实数量联系起来，不只记外形。"),
        ("numeral", "objects" if number <= 5 else "ten_frame"),
        "numeral_recognition_v1",
        difficulty=1 if number <= 5 else 2,
        settings={"target": number, "minimum": 0, "maximum": 10},
    )
    for number in range(11)
) + (
    _seed(
        "number_symbol",
        "match-symbol-quantity-within-3",
        "数字对应 3 以内数量",
        "这个数字和哪一组一样多？",
        "让孩子在数字和物品之间来回对应。",
        ("numeral", "dots", "objects"),
        "numeral_quantity_match_v1",
        settings={"minimum": 0, "maximum": 3},
    ),
    _seed(
        "number_symbol",
        "match-symbol-quantity-within-5",
        "数字对应 5 以内数量",
        "这个数字和哪一组一样多？",
        "可更换点阵、积木和生活物品。",
        ("numeral", "dots", "objects"),
        "numeral_quantity_match_v1",
        difficulty=2,
        settings={"minimum": 0, "maximum": 5},
    ),
    _seed(
        "number_symbol",
        "match-symbol-quantity-within-10",
        "数字对应 10 以内数量",
        "哪个数量和这个数字一样？",
        "十格框能帮助孩子理解 5 和 10 的结构。",
        ("numeral", "ten_frame", "objects"),
        "numeral_quantity_match_v1",
        difficulty=3,
        settings={"minimum": 0, "maximum": 10},
    ),
)

COMPARISON = (
    _seed(
        "comparison",
        "more-less-within-3",
        "比较 3 以内多和少",
        "哪一边更多？",
        "可以先一一配对，再判断是否有剩余。",
        ("objects", "dots"),
        "compare_quantity_v1",
        settings={"minimum": 0, "maximum": 3},
    ),
    _seed(
        "comparison",
        "more-less-within-5",
        "比较 5 以内多和少",
        "哪一边更多？",
        "改变排列和物品，避免只看占据空间大小。",
        ("objects", "dots"),
        "compare_quantity_v1",
        difficulty=2,
        settings={"minimum": 0, "maximum": 5},
    ),
    _seed(
        "comparison",
        "equal-quantity-within-5",
        "判断一样多",
        "哪两组一样多？",
        "让孩子通过配对确认一样多。",
        ("objects", "dots"),
        "compare_quantity_v1",
        difficulty=2,
        settings={"minimum": 1, "maximum": 5, "relation": "equal"},
    ),
    _seed(
        "comparison",
        "more-less-within-10",
        "比较 10 以内多和少",
        "哪一边更多？",
        "鼓励先估一估，再数一数验证。",
        ("objects", "dots", "ten_frame"),
        "compare_quantity_v1",
        difficulty=3,
        settings={"minimum": 0, "maximum": 10},
    ),
)

SEQUENCE = (
    _seed(
        "sequence",
        "next-number-within-10",
        "找下一个数",
        "接下来是几？",
        "可以配合数字卡片排一排。",
        ("number_line", "numeral"),
        "number_sequence_v1",
        settings={"minimum": 0, "maximum": 10, "task": "next"},
    ),
    _seed(
        "sequence",
        "previous-number-within-10",
        "找前一个数",
        "前面应该是几？",
        "先正着数，再尝试倒着找。",
        ("number_line", "numeral"),
        "number_sequence_v1",
        difficulty=2,
        settings={"minimum": 0, "maximum": 10, "task": "previous"},
    ),
    _seed(
        "sequence",
        "missing-number-within-10",
        "补全数序",
        "空白的地方应该是几？",
        "用真实数字卡片遮住一个再寻找。",
        ("number_line", "numeral"),
        "number_sequence_v1",
        difficulty=2,
        settings={"minimum": 0, "maximum": 10, "task": "missing"},
    ),
    _seed(
        "sequence",
        "order-0-to-10",
        "排列 0 到 10",
        "把这些数字按顺序排好。",
        "不要求速度，重点理解相邻数的关系。",
        ("number_line", "numeral"),
        "number_sequence_v1",
        difficulty=3,
        settings={"minimum": 0, "maximum": 10, "task": "order"},
    ),
)

COMPOSITION = tuple(
    _seed(
        "composition",
        f"compose-{number}",
        f"{number} 的分解与组合",
        f"哪两部分合起来是 {number}？",
        f"拿出 {number} 块积木，分成两堆，看看有多少种分法。",
        ("objects", "dots", "equation"),
        "composition_v1",
        difficulty=1 if number <= 5 else 3,
        settings={"total": number},
    )
    for number in range(2, 11)
)

OPERATION = (
    _seed(
        "operation",
        "add-joining-within-3",
        "3 以内加法：合起来",
        "两组合起来，一共有几个？",
        "先移动真实物品合在一起，再出现加号。",
        ("objects", "dots", "story"),
        "joining_v1",
        settings={"maximum": 3},
    ),
    _seed(
        "operation",
        "subtract-taking-away-within-3",
        "3 以内减法：拿走",
        "拿走一些以后，还剩几个？",
        "让孩子亲手拿走物品，理解剩余。",
        ("objects", "dots", "story"),
        "taking_away_v1",
        settings={"maximum": 3},
    ),
    _seed(
        "operation",
        "add-joining-within-5",
        "5 以内加法：合起来",
        "又来了一些，现在一共有几个？",
        "按实物、图形、符号的顺序逐渐抽象。",
        ("objects", "dots", "story", "equation"),
        "joining_v1",
        difficulty=2,
        settings={"maximum": 5},
    ),
    _seed(
        "operation",
        "subtract-taking-away-within-5",
        "5 以内减法：拿走",
        "拿走一些以后，还剩几个？",
        "先操作再说算式，不要求背答案。",
        ("objects", "dots", "story", "equation"),
        "taking_away_v1",
        difficulty=2,
        settings={"maximum": 5},
    ),
    _seed(
        "operation",
        "add-joining-within-10",
        "10 以内加法理解",
        "两部分合起来，一共有几个？",
        "关注合起来的含义，不做进位和竖式。",
        ("objects", "ten_frame", "story", "equation"),
        "joining_v1",
        difficulty=3,
        settings={"maximum": 10},
    ),
    _seed(
        "operation",
        "subtract-taking-away-within-10",
        "10 以内减法理解",
        "拿走一些以后，还剩几个？",
        "所有题目保证结果不小于零。",
        ("objects", "ten_frame", "story", "equation"),
        "taking_away_v1",
        difficulty=3,
        settings={"maximum": 10},
    ),
)

PATTERN = tuple(
    _seed(
        "pattern",
        code,
        title,
        "接下来应该是什么？",
        "图案同时使用形状和颜色标签，不只依赖颜色。",
        ("pattern", "shape"),
        "pattern_v1",
        difficulty=difficulty,
        settings={"pattern": code},
    )
    for code, title, difficulty in (
        ("abab", "发现 ABAB 规律", 1),
        ("aab", "发现 AAB 规律", 2),
        ("abc", "发现 ABC 规律", 2),
    )
)

GEOMETRY = tuple(
    _seed(
        "geometry",
        shape,
        title,
        f"哪个是{title.replace('认识', '')}？",
        "用边、角和曲直描述图形；平面图形与立体图形分开认识。",
        ("shape",),
        "shape_choice_v1",
        difficulty=1 if shape in {"circle", "triangle", "square", "rectangle"} else 3,
        settings={"target_shape": shape},
    )
    for shape, title in (
        ("circle", "认识圆形"),
        ("triangle", "认识三角形"),
        ("square", "认识正方形"),
        ("rectangle", "认识长方形"),
        ("sphere", "认识球体"),
        ("cube", "认识正方体"),
    )
)

SPATIAL = tuple(
    _seed(
        "spatial",
        code,
        title,
        instruction,
        tip,
        ("spatial_scene", "objects"),
        "spatial_choice_v1",
        difficulty=2 if code == "left-right" else 1,
        settings={"relation": code},
    )
    for code, title, instruction, tip in (
        ("up-down", "认识上和下", "哪个在上面？", "用身体和真实位置一起体验上、下。"),
        ("left-right", "认识左和右", "哪个在左边？", "左右发展时间不同，这只是一个独立空间技能。"),
        ("inside-outside", "认识里面和外面", "哪个在里面？", "可以把玩具放进盒子再拿出来。"),
        ("front-behind", "认识前和后", "哪个在前面？", "从不同视角观察时，先明确朝向。"),
    )
)

MEASUREMENT = tuple(
    _seed(
        "measurement",
        code,
        title,
        instruction,
        "只做直观和非标准单位比较，不引入厘米、公斤。",
        ("objects", "spatial_scene"),
        "measurement_compare_v1",
        difficulty=2,
        settings={"comparison": code},
    )
    for code, title, instruction in (
        ("long-short", "比较长和短", "哪一个更长？"),
        ("high-low", "比较高和矮", "哪一个更高？"),
        ("heavy-light", "比较轻和重", "哪一个更重？"),
        ("many-few", "生活中的多和少", "哪一组更多？"),
    )
)

MATH_SKILL_SEEDS = (
    CLASSIFICATION
    + QUANTITY
    + NUMBER_SYMBOL
    + COMPARISON
    + SEQUENCE
    + COMPOSITION
    + OPERATION
    + PATTERN
    + GEOMETRY
    + SPATIAL
    + MEASUREMENT
)
assert len(MATH_SKILL_SEEDS) == 68


COURSE_UNITS = (
    ("配对、一样和不一样", ("match-same", "find-different")),
    ("分类", ("sort-by-shape", "sort-by-size")),
    ("数量 1～3", ("recognize-1", "recognize-2", "recognize-3", "count-within-3")),
    ("数量 1～5", ("recognize-4", "recognize-5", "count-within-5", "subitize-within-5")),
    ("数字符号 0～5", tuple(f"recognize-{n}" for n in range(6))),
    ("数量和数字对应", ("match-symbol-quantity-within-3", "match-symbol-quantity-within-5")),
    ("多、少、一样多", ("more-less-within-3", "more-less-within-5", "equal-quantity-within-5")),
    (
        "数序 0～10",
        (
            "next-number-within-10",
            "previous-number-within-10",
            "missing-number-within-10",
            "order-0-to-10",
        ),
    ),
    ("数的分解与组合 2～5", tuple(f"compose-{n}" for n in range(2, 6))),
    ("加法：合起来", ("add-joining-within-3", "add-joining-within-5")),
    ("减法：拿走一些", ("subtract-taking-away-within-3", "subtract-taking-away-within-5")),
    (
        "数量 6～10",
        tuple(f"recognize-{n}" for n in range(6, 11))
        + ("count-within-10", "ten-frame-within-10", "match-symbol-quantity-within-10"),
    ),
    ("数的分解与组合 6～10", tuple(f"compose-{n}" for n in range(6, 11))),
    ("10以内加减的理解", ("add-joining-within-10", "subtract-taking-away-within-10")),
    ("找规律", ("abab", "aab", "abc")),
    ("基本图形", ("circle", "triangle", "square", "rectangle", "sphere", "cube")),
    ("空间位置", ("up-down", "left-right", "inside-outside", "front-behind")),
    ("长短、高矮、轻重等简单比较", ("long-short", "high-low", "heavy-light", "many-few")),
    (
        "综合生活数学",
        ("more-less-within-10", "add-joining-within-10", "subtract-taking-away-within-10"),
    ),
)

PREREQUISITES = (
    ("math:quantity:count-within-3", "math:quantity:count-within-5"),
    ("math:quantity:count-within-5", "math:quantity:count-within-10"),
    ("math:quantity:count-within-3", "math:number_symbol:match-symbol-quantity-within-3"),
    (
        "math:number_symbol:match-symbol-quantity-within-3",
        "math:number_symbol:match-symbol-quantity-within-5",
    ),
    ("math:number_symbol:match-symbol-quantity-within-5", "math:comparison:more-less-within-5"),
    ("math:comparison:more-less-within-5", "math:composition:compose-5"),
    ("math:composition:compose-5", "math:operation:add-joining-within-5"),
    ("math:composition:compose-5", "math:operation:subtract-taking-away-within-5"),
    ("math:quantity:count-within-10", "math:number_symbol:match-symbol-quantity-within-10"),
    ("math:number_symbol:match-symbol-quantity-within-10", "math:comparison:more-less-within-10"),
    ("math:comparison:more-less-within-10", "math:composition:compose-10"),
    ("math:composition:compose-10", "math:operation:add-joining-within-10"),
    ("math:composition:compose-10", "math:operation:subtract-taking-away-within-10"),
)


@dataclass
class MathImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    relations_created: int = 0
    templates_created: int = 0
    catalog_version: str = MATH_CATALOG_VERSION
    catalog_size: int = len(MATH_SKILL_SEEDS)
    template_count: int = 0
    course_created: bool = False
    errors: list[str] = field(default_factory=list)


def stable_math_point_id(canonical_key: str) -> uuid.UUID:
    return uuid.uuid5(MATH_NAMESPACE, canonical_key)


def stable_math_template_id(template_key: str) -> uuid.UUID:
    return uuid.uuid5(MATH_TEMPLATE_NAMESPACE, template_key)


async def _seed_course(session: AsyncSession, points: dict[str, uuid.UUID]) -> bool:
    existing = await session.scalar(select(Course.id).where(Course.system_key == MATH_COURSE_KEY))
    if existing is not None:
        return False
    course = Course(
        subject=CourseSubject.MATH,
        title="数学启蒙",
        description="Growth Learning 项目设计的儿童启蒙数学路径，重视操作、理解、表示和迁移。",
        source_type=CourseSourceType.SYSTEM,
        status=CourseStatus.ENABLED,
        version=1,
        system_key=MATH_COURSE_KEY,
        recommended_age_min=3,
        recommended_age_max=8,
        reference_metadata={"catalog_version": MATH_CATALOG_VERSION, "project_curated": True},
    )
    session.add(course)
    await session.flush()
    by_code: dict[str, list[MathSkillSeed]] = {}
    for seed in MATH_SKILL_SEEDS:
        by_code.setdefault(seed.skill_code, []).append(seed)
    used_per_code: dict[str, int] = {}
    for unit_order, (title, codes) in enumerate(COURSE_UNITS):
        unit = CourseUnit(
            course_id=course.id,
            title=title,
            description="从动手操作和图形理解开始，再逐渐过渡到数字与符号。",
            order_index=unit_order,
            status=CourseStatus.ENABLED,
        )
        session.add(unit)
        await session.flush()
        activity = LearningActivity(
            course_unit_id=unit.id,
            activity_type=ActivityType.GUIDED_PRACTICE,
            title=f"动手学 · {title}",
            instructions="一次一个能力、一道主要任务；提示和重试不会被伪装成独立答对。",
            order_index=0,
            status=CourseStatus.ENABLED,
            content_metadata={
                "catalog_version": MATH_CATALOG_VERSION,
                "concrete_visual_symbolic": True,
            },
        )
        session.add(activity)
        await session.flush()
        for position, code in enumerate(codes):
            candidates = by_code[code]
            index = used_per_code.get(code, 0)
            seed = candidates[min(index, len(candidates) - 1)]
            used_per_code[code] = index + 1
            session.add(
                ActivityKnowledgePoint(
                    activity_id=activity.id,
                    knowledge_point_id=points[seed.canonical_key],
                    role=KnowledgePointRole.PRIMARY,
                    order_index=position,
                )
            )
    return True


async def import_math_foundation(session: AsyncSession) -> MathImportResult:
    """Idempotently import stable skill IDs, templates, relations, and the 19-unit path."""

    result = MathImportResult()
    point_ids: dict[str, uuid.UUID] = {}
    for order_index, seed in enumerate(MATH_SKILL_SEEDS):
        try:
            point = await session.scalar(
                select(KnowledgePoint).where(KnowledgePoint.canonical_key == seed.canonical_key)
            )
            created = point is None
            if point is None:
                point = KnowledgePoint(
                    id=stable_math_point_id(seed.canonical_key),
                    subject=Subject.MATH,
                    type=KnowledgeType.MATH_SKILL,
                    status=KnowledgeStatus.ACTIVE,
                    title=seed.title,
                    canonical_key=seed.canonical_key,
                    source_type="project_curated",
                    source_reference=MATH_CATALOG_VERSION,
                )
                session.add(point)
                await session.flush()
            skill = await session.get(MathSkill, point.id)
            if skill is None:
                skill = MathSkill(knowledge_point_id=point.id)
                session.add(skill)
                created = True
            point_values = {
                "subject": Subject.MATH,
                "type": KnowledgeType.MATH_SKILL,
                "status": KnowledgeStatus.ACTIVE,
                "title": seed.title,
                "source_type": "project_curated",
                "source_reference": MATH_CATALOG_VERSION,
            }
            skill_values = {
                "domain": seed.domain,
                "skill_code": f"{seed.domain}:{seed.skill_code}",
                "difficulty_level": seed.difficulty_level,
                "recommended_age_min": seed.recommended_age_min,
                "recommended_age_max": seed.recommended_age_max,
                "title": seed.title,
                "child_instruction": seed.child_instruction,
                "parent_tip": seed.parent_tip,
                "representation_types": list(seed.representation_types),
                "generator_key": seed.generator_key,
                "settings_json": {**seed.settings, "offline_instruction": seed.parent_tip},
                "order_index": order_index,
                "catalog_version": MATH_CATALOG_VERSION,
            }
            changed = created
            for target, values in ((point, point_values), (skill, skill_values)):
                for name, value in values.items():
                    if getattr(target, name, None) != value:
                        setattr(target, name, value)
                        changed = True
            result.created += int(created)
            if not created:
                result.updated += int(changed)
                result.skipped += int(not changed)
            point_ids[seed.canonical_key] = point.id
            for template_order, representation in enumerate(seed.representation_types):
                template_key = f"{seed.canonical_key}:{representation}:v1"
                template = await session.scalar(
                    select(MathProblemTemplate).where(
                        MathProblemTemplate.template_key == template_key
                    )
                )
                if template is None:
                    template = MathProblemTemplate(
                        id=stable_math_template_id(template_key),
                        knowledge_point_id=point.id,
                        template_key=template_key,
                    )
                    session.add(template)
                    result.templates_created += 1
                template.representation_type = representation
                template.difficulty = seed.difficulty_level
                template.generator_version = MATH_GENERATOR_VERSION
                template.config_json = {
                    **seed.settings,
                    "generator_key": seed.generator_key,
                    "skill_code": f"{seed.domain}:{seed.skill_code}",
                    "domain": seed.domain,
                }
                template.status = KnowledgeStatus.ACTIVE
                template.order_index = template_order
        except Exception as error:
            result.errors.append(f"{seed.canonical_key}: {type(error).__name__}: {error}")
    if result.errors:
        await session.rollback()
        return result

    for source_key, target_key in PREREQUISITES:
        exists = await session.scalar(
            select(KnowledgeRelation.id).where(
                KnowledgeRelation.source_id == point_ids[source_key],
                KnowledgeRelation.target_id == point_ids[target_key],
                KnowledgeRelation.relation_type == RelationType.PREREQUISITE,
            )
        )
        if exists is None:
            session.add(
                KnowledgeRelation(
                    source_id=point_ids[source_key],
                    target_id=point_ids[target_key],
                    relation_type=RelationType.PREREQUISITE,
                )
            )
            result.relations_created += 1

    result.template_count = int(
        await session.scalar(
            select(func.count())
            .select_from(MathProblemTemplate)
            .where(MathProblemTemplate.status == KnowledgeStatus.ACTIVE)
        )
        or 0
    )
    release = await session.scalar(
        select(MathCatalogRelease).where(MathCatalogRelease.catalog_version == MATH_CATALOG_VERSION)
    )
    if release is None:
        release = MathCatalogRelease(
            catalog_version=MATH_CATALOG_VERSION,
            source_name="Growth Learning project-curated Math Foundation",
            source_reference="docs/MATH_CURRICULUM_FOUNDATION_V1.md",
            imported_at=datetime.now(UTC),
            item_count=len(MATH_SKILL_SEEDS),
            template_count=result.template_count,
            is_current=True,
            metadata_json={
                "subject": "math",
                "knowledge_type": "math_skill",
                "official_standard": False,
            },
        )
        session.add(release)
    else:
        release.item_count = len(MATH_SKILL_SEEDS)
        release.template_count = result.template_count
        release.is_current = True
    result.course_created = await _seed_course(session, point_ids)
    await session.commit()
    return result


async def math_catalog_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(select(MathSkill.domain, func.count()).group_by(MathSkill.domain))
    ).all()
    return {str(domain): count for domain, count in rows}


async def list_math_skills(
    session: AsyncSession,
    *,
    domain: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 100,
    public_only: bool = False,
) -> tuple[list[tuple[KnowledgePoint, MathSkill]], int, int]:
    filters = [
        KnowledgePoint.type == KnowledgeType.MATH_SKILL,
        KnowledgePoint.subject == Subject.MATH,
    ]
    if public_only:
        filters.append(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
    if domain:
        filters.append(MathSkill.domain == domain)
    if status:
        filters.append(KnowledgePoint.status == status)
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                MathSkill.title.ilike(term),
                MathSkill.skill_code.ilike(term),
                KnowledgePoint.canonical_key.ilike(term),
            )
        )
    total = int(
        await session.scalar(
            select(func.count()).select_from(MathSkill).join(KnowledgePoint).where(*filters)
        )
        or 0
    )
    pages = max(1, (total + page_size - 1) // page_size)
    rows = list(
        (
            await session.execute(
                select(KnowledgePoint, MathSkill)
                .join(MathSkill)
                .where(*filters)
                .order_by(MathSkill.order_index)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return rows, total, pages
