"""Project-owned English visual metadata and deterministic fallback resolution."""

from dataclasses import dataclass

from app.models import EnglishItem


@dataclass(frozen=True)
class EnglishVisual:
    visual_type: str
    image_url: str | None
    visual_key: str | None
    source: str
    license: str
    attribution: str | None
    fallback: bool


class EnglishVisualProvider:
    def resolve(self, item: EnglishItem) -> EnglishVisual:
        metadata = item.metadata_json or {}
        visual_type = item.visual_type
        if item.image_key:
            visual_type = "static_image"
        if not item.image_key and not item.visual_key:
            visual_type = "emoji_fallback"
        return EnglishVisual(
            visual_type=visual_type,
            image_url=item.image_key,
            visual_key=item.visual_key or "🔊",
            source=str(metadata.get("source", "Growth Learning project-curated")),
            license=str(metadata.get("license", "project-owned")),
            attribution=(str(metadata["attribution"]) if metadata.get("attribution") else None),
            fallback=visual_type == "emoji_fallback",
        )


english_visual_provider = EnglishVisualProvider()
