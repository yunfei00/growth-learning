"""Small deterministic registry for child-friendly Math Foundation problems."""

import random
from collections.abc import Callable
from dataclasses import dataclass

from app.models import MathProblemTemplate
from app.services.math_catalog import MATH_GENERATOR_VERSION


@dataclass(frozen=True)
class GeneratedMathProblem:
    template_key: str
    generator_version: str
    seed: int
    representation_type: str
    render_payload: dict[str, object]
    expected_answer: object


Generator = Callable[[random.Random, MathProblemTemplate], tuple[dict[str, object], object]]


def _nearby_options(rng: random.Random, answer: int, *, low: int = 0, high: int = 10) -> list[int]:
    candidates = [
        value for value in range(max(low, answer - 2), min(high, answer + 2) + 1) if value != answer
    ]
    for value in range(low, high + 1):
        if value != answer and value not in candidates:
            candidates.append(value)
    rng.shuffle(candidates)
    options = [answer, *candidates[:2]]
    rng.shuffle(options)
    return options


def _numeric_payload(
    instruction: str,
    representation: str,
    answer: int,
    options: list[int],
    **visual: object,
) -> tuple[dict[str, object], object]:
    return (
        {
            "kind": "number_choice",
            "instruction": instruction,
            "representation_type": representation,
            "visual": visual,
            "options": [{"value": value, "label": str(value)} for value in options],
        },
        answer,
    )


def _quantity_choice(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    config = template.config_json
    minimum = int(config.get("minimum", 0))
    maximum = int(config.get("maximum", 5))
    count = rng.randint(minimum, maximum)
    options = _nearby_options(rng, count, low=0, high=max(5, maximum))
    layout = (
        rng.choice(("cluster", "rows", "arc"))
        if template.representation_type != "ten_frame"
        else "ten_frame"
    )
    return _numeric_payload(
        "这里有几个？",
        template.representation_type,
        count,
        options,
        count=count,
        layout=layout,
        aria_label=f"{count}个圆点"
        if template.representation_type != "objects"
        else f"{count}个积木",
    )


def _numeral_recognition(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    target = int(template.config_json.get("target", 0))
    options = _nearby_options(rng, target, low=0, high=10)
    return _numeric_payload(
        f"哪个是数字 {target}？",
        template.representation_type,
        target,
        options,
        numeral=target,
        empty_meaning=target == 0,
        aria_label=("盘子里一个也没有，用0表示" if target == 0 else f"数字{target}"),
    )


def _numeral_quantity_match(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    minimum = int(template.config_json.get("minimum", 0))
    maximum = int(template.config_json.get("maximum", 5))
    target = rng.randint(minimum, maximum)
    counts = _nearby_options(rng, target, low=0, high=max(5, maximum))
    return (
        {
            "kind": "quantity_group_choice",
            "instruction": "哪一组和这个数字一样多？",
            "representation_type": template.representation_type,
            "visual": {"numeral": target},
            "options": [
                {
                    "value": count,
                    "count": count,
                    "label": f"{count}个",
                    "aria_label": f"{count}个圆点",
                }
                for count in counts
            ],
        },
        target,
    )


def _compare_quantity(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    minimum = int(template.config_json.get("minimum", 0))
    maximum = int(template.config_json.get("maximum", 5))
    equal = template.config_json.get("relation") == "equal"
    left = rng.randint(minimum, maximum)
    right = left if equal else rng.randint(minimum, maximum)
    while not equal and right == left:
        right = rng.randint(minimum, maximum)
    expected = "equal" if left == right else ("left" if left > right else "right")
    options = [
        {"value": "left", "label": "左边"},
        {"value": "right", "label": "右边"},
        {"value": "equal", "label": "一样多"},
    ]
    rng.shuffle(options)
    return (
        {
            "kind": "compare_groups",
            "instruction": "哪一边更多？" if not equal else "这两组一样多吗？",
            "representation_type": template.representation_type,
            "visual": {
                "left_count": left,
                "right_count": right,
                "left_layout": rng.choice(("row", "cluster")),
                "right_layout": rng.choice(("row", "cluster")),
            },
            "options": options,
        },
        expected,
    )


def _number_sequence(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    task = str(template.config_json.get("task", "missing"))
    maximum = int(template.config_json.get("maximum", 10))
    if task == "next":
        start = rng.randint(0, maximum - 3)
        sequence: list[int | None] = [start, start + 1, start + 2, None]
        answer = start + 3
    elif task == "previous":
        start = rng.randint(1, maximum - 2)
        sequence = [None, start, start + 1, start + 2]
        answer = start - 1
    else:
        start = rng.randint(0, maximum - 3)
        missing = rng.choice((1, 2))
        sequence = [start, start + 1, start + 2, start + 3]
        answer = int(sequence[missing])
        sequence[missing] = None
    return _numeric_payload(
        "空白的地方应该是几？",
        template.representation_type,
        answer,
        _nearby_options(rng, answer, low=0, high=maximum),
        sequence=sequence,
        aria_label="一列数字中有一个空白",
    )


def _composition(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    total = int(template.config_json["total"])
    known = rng.randint(0, total)
    missing = total - known
    return _numeric_payload(
        f"{known} 和几合起来是 {total}？",
        template.representation_type,
        missing,
        _nearby_options(rng, missing, low=0, high=total),
        total=total,
        known_part=known,
        missing_part=True,
        groups=[known, missing],
    )


def _joining(rng: random.Random, template: MathProblemTemplate) -> tuple[dict[str, object], object]:
    maximum = int(template.config_json.get("maximum", 5))
    left = rng.randint(0, maximum)
    right = rng.randint(0, maximum - left)
    answer = left + right
    return _numeric_payload(
        "两组合起来，一共有几个？",
        template.representation_type,
        answer,
        _nearby_options(rng, answer, low=0, high=maximum),
        first_count=left,
        second_count=right,
        story=f"原来有{left}个，又来了{right}个。",
        equation=f"{left} + {right} = ?",
    )


def _taking_away(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    maximum = int(template.config_json.get("maximum", 5))
    start = rng.randint(0, maximum)
    removed = rng.randint(0, start)
    answer = start - removed
    return _numeric_payload(
        "拿走一些以后，还剩几个？",
        template.representation_type,
        answer,
        _nearby_options(rng, answer, low=0, high=maximum),
        start_count=start,
        removed_count=removed,
        remaining_count=answer,
        story=f"原来有{start}个，拿走{removed}个。",
        equation=f"{start} - {removed} = ?",
    )


PATTERN_TOKENS = (
    {"key": "blue-circle", "color": "blue", "shape": "circle", "label": "蓝色圆形"},
    {"key": "red-triangle", "color": "red", "shape": "triangle", "label": "红色三角形"},
    {"key": "green-square", "color": "green", "shape": "square", "label": "绿色正方形"},
)


def _pattern(rng: random.Random, template: MathProblemTemplate) -> tuple[dict[str, object], object]:
    pattern_key = str(template.config_json.get("pattern", "abab"))
    cycle_length = {"abab": 2, "aab": 3, "abc": 3}[pattern_key]
    tokens = list(PATTERN_TOKENS[:cycle_length])
    cycle = [tokens[0], tokens[0], tokens[1]] if pattern_key == "aab" else tokens
    sequence = [cycle[index % len(cycle)] for index in range(5)]
    answer = cycle[len(sequence) % len(cycle)]["key"]
    options = [{"value": token["key"], "label": token["label"], "token": token} for token in tokens]
    rng.shuffle(options)
    return (
        {
            "kind": "pattern_choice",
            "instruction": "接下来应该是什么？",
            "representation_type": "pattern",
            "visual": {"sequence": sequence},
            "options": options,
        },
        answer,
    )


SHAPES = ("circle", "triangle", "square", "rectangle", "sphere", "cube")
SHAPE_LABELS = {
    "circle": "圆形",
    "triangle": "三角形",
    "square": "正方形",
    "rectangle": "长方形",
    "sphere": "球体",
    "cube": "正方体",
}


def _shape_choice(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    target = str(template.config_json["target_shape"])
    distractors = [shape for shape in SHAPES if shape != target]
    rng.shuffle(distractors)
    choices = [target, *distractors[:2]]
    rng.shuffle(choices)
    return (
        {
            "kind": "shape_choice",
            "instruction": f"哪个是{SHAPE_LABELS[target]}？",
            "representation_type": "shape",
            "visual": {},
            "options": [
                {"value": shape, "label": SHAPE_LABELS[shape], "shape": shape} for shape in choices
            ],
        },
        target,
    )


def _classification(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    code = str(template.config_json["skill_code"]).split(":", 1)[-1]
    if code == "match-same":
        options = ["circle", "triangle", "square"]
        rng.shuffle(options)
        answer: object = options.index("circle")
        instruction = "哪个和上面的圆形一样？"
    elif code == "find-different":
        options = ["square", "square", "circle"]
        rng.shuffle(options)
        answer = options.index("circle")
        instruction = "哪一个不一样？"
    else:
        odd = "small-square" if code == "sort-by-shape" else "large-triangle"
        options = [
            "small-circle",
            "large-circle" if code == "sort-by-shape" else "small-square",
            odd,
        ]
        rng.shuffle(options)
        answer = options.index(odd)
        instruction = "哪一个应该分到另一组？"
    labels = {
        "circle": "圆形",
        "triangle": "三角形",
        "square": "正方形",
        "small-circle": "小圆形",
        "large-circle": "大圆形",
        "small-square": "小正方形",
        "large-triangle": "大三角形",
    }
    return (
        {
            "kind": "classification_choice",
            "instruction": instruction,
            "representation_type": template.representation_type,
            "visual": {},
            "options": [
                {"value": index, "label": labels[value], "shape": value}
                for index, value in enumerate(options)
            ],
        },
        answer,
    )


def _spatial_choice(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    relation = str(template.config_json["relation"])
    relation_labels = {
        "up-down": "上面",
        "left-right": "左边",
        "inside-outside": "里面",
        "front-behind": "前面",
    }
    label = relation_labels[relation]
    answer = rng.choice(("a", "b"))
    options = [
        {"value": "a", "label": "蓝色圆形"},
        {"value": "b", "label": "黄色正方形"},
    ]
    rng.shuffle(options)
    return (
        {
            "kind": "spatial_choice",
            "instruction": f"哪个在{label}？",
            "representation_type": "spatial_scene",
            "visual": {"relation": relation, "answer_object": answer},
            "options": options,
        },
        answer,
    )


def _measurement_compare(
    rng: random.Random, template: MathProblemTemplate
) -> tuple[dict[str, object], object]:
    comparison = str(template.config_json["comparison"])
    left = rng.randint(2, 5)
    right = rng.randint(6, 9)
    if rng.choice((True, False)):
        left, right = right, left
    desired = "right" if right > left else "left"
    label = {"long-short": "更长", "high-low": "更高", "heavy-light": "更重", "many-few": "更多"}[
        comparison
    ]
    return (
        {
            "kind": "measurement_compare",
            "instruction": f"哪一个{label}？",
            "representation_type": template.representation_type,
            "visual": {"comparison": comparison, "left_value": left, "right_value": right},
            "options": [{"value": "left", "label": "左边"}, {"value": "right", "label": "右边"}],
        },
        desired,
    )


class MathProblemGeneratorRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Generator] = {}

    def register(self, key: str, handler: Generator) -> None:
        if key in self._handlers:
            raise ValueError(f"Math generator already registered: {key}")
        self._handlers[key] = handler

    def generate(self, template: MathProblemTemplate, seed: int) -> GeneratedMathProblem:
        if template.generator_version != MATH_GENERATOR_VERSION:
            raise ValueError("Unsupported math generator version")
        generator_key = str(template.config_json.get("generator_key", ""))
        handler = self._handlers.get(generator_key)
        if handler is None:
            raise LookupError(f"Unknown math generator: {generator_key}")
        payload, expected = handler(random.Random(seed), template)
        return GeneratedMathProblem(
            template_key=template.template_key,
            generator_version=template.generator_version,
            seed=seed,
            representation_type=template.representation_type,
            render_payload=payload,
            expected_answer=expected,
        )


math_problem_generators = MathProblemGeneratorRegistry()
for key, handler in (
    ("classification_v1", _classification),
    ("quantity_choice_v1", _quantity_choice),
    ("numeral_recognition_v1", _numeral_recognition),
    ("numeral_quantity_match_v1", _numeral_quantity_match),
    ("compare_quantity_v1", _compare_quantity),
    ("number_sequence_v1", _number_sequence),
    ("composition_v1", _composition),
    ("joining_v1", _joining),
    ("taking_away_v1", _taking_away),
    ("pattern_v1", _pattern),
    ("shape_choice_v1", _shape_choice),
    ("spatial_choice_v1", _spatial_choice),
    ("measurement_compare_v1", _measurement_compare),
):
    math_problem_generators.register(key, handler)
