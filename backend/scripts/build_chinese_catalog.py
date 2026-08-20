"""Build the vendored Growth Learning catalog from licensed Unicode Unihan data.

This developer tool does not run in production. It preserves the project-owned
starter entries first, then selects simplified GB characters by deterministic
kHanyuPinlu occurrence totals. The resulting stages are project curriculum,
not an official educational standard.
"""

import argparse
import json
import re
import zipfile
from pathlib import Path

TARGET_COUNT = 1200
CATALOG_VERSION = "growth-chinese-v2-unihan-2026"
PINLU_PATTERN = re.compile(r"([^\s(]+)\((\d+)\)")


def _properties(archive: zipfile.ZipFile, filename: str, property_name: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for line in archive.read(filename).decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        codepoint, name, value = line.split("\t", 2)
        if name == property_name:
            output[chr(int(codepoint[2:], 16))] = value
    return output


def build(starter_path: Path, unihan_path: Path) -> dict:
    starter = json.loads(starter_path.read_text(encoding="utf-8"))
    original = list(starter["items"])
    existing = {item["character"] for item in original}
    with zipfile.ZipFile(unihan_path) as archive:
        pinyin = _properties(archive, "Unihan_Readings.txt", "kMandarin")
        pinlu = _properties(archive, "Unihan_Readings.txt", "kHanyuPinlu")
        gb0 = _properties(archive, "Unihan_OtherMappings.txt", "kGB0")
        simplified_variants = _properties(archive, "Unihan_Variants.txt", "kSimplifiedVariant")

    candidates: list[tuple[int, int, str, str]] = []
    for character, reading_counts in pinlu.items():
        if character in existing or character not in gb0 or character in simplified_variants:
            continue
        readings = PINLU_PATTERN.findall(reading_counts)
        if not readings:
            continue
        total = sum(int(count) for _, count in readings)
        common_reading = readings[0][0] if readings else pinyin.get(character)
        if not common_reading:
            continue
        candidates.append((-total, ord(character), character, common_reading))
    candidates.sort()

    items = [
        {
            **item,
            "source_type": "project_starter",
            "source_reference": "chinese_characters_v1",
        }
        for item in original
    ]
    for frequency_rank, (_, codepoint, character, reading) in enumerate(
        candidates[: TARGET_COUNT - len(items)], start=len(items) + 1
    ):
        items.append(
            {
                "character": character,
                "pinyin": reading,
                "frequency_rank": frequency_rank,
                "common_words": [],
                "simple_meaning": None,
                "source_type": "unicode_unihan",
                "source_reference": f"Unihan kHanyuPinlu/kMandarin U+{codepoint:04X}",
            }
        )
    if len(items) != TARGET_COUNT:
        raise RuntimeError(f"Expected {TARGET_COUNT} entries, built {len(items)}")
    if len({item["character"] for item in items}) != TARGET_COUNT:
        raise RuntimeError("Catalog contains duplicate characters")
    return {
        "version": "2.0",
        "catalog_version": CATALOG_VERSION,
        "notice": (
            "Growth Learning project curriculum catalog; not an official educational "
            "standard or textbook list. Starter entries are project curated. Expansion "
            "readings and corpus occurrence counts derive from Unicode Unihan data."
        ),
        "provenance": {
            "source_type": "unicode_unihan_and_project_curated",
            "source_name": "Unicode Unihan Database and Growth Learning Starter Catalog",
            "source_reference": "https://www.unicode.org/Public/UNIDATA/Unihan.zip",
            "license": "Unicode-3.0",
            "selection_method": (
                "starter first; then simplified GB0 characters ordered by descending "
                "kHanyuPinlu occurrence total with code point tie-break"
            ),
        },
        "items": items,
        "relations": starter.get("relations", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--starter", type=Path, required=True)
    parser.add_argument("--unihan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.starter, args.unihan)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
