"""Global Digital Library discovery/import with strict licensing and URL controls."""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.object_storage import PrivateObjectStorage
from app.models import (
    Child,
    ChineseCharacter,
    KnowledgePoint,
    Story,
    StoryGenerationRun,
    StoryGenerationStatus,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.models.picture_book import PictureBookImport
from app.schemas.picture_book import OpenPictureBookSummary, PictureBookDetail, OpenPictureBookPage
from app.services.daily_reading import attach_story_to_today
from app.services.manual_story import _snapshot_payload
from app.services.review_planning import get_or_create_daily_plan
from app.services.story_analysis import (
    ANALYZER_VERSION,
    COVERAGE_POLICY_VERSION,
    analyze_story_coverage,
    extract_han,
)
from app.services.story_generation import build_mastery_snapshot
from app.services.story_pinyin import annotate_paragraph_pinyin

GDL_API_ROOT = "https://content.digitallibrary.io"
GDL_LANGUAGE = "zh-cn"
GDL_PROVIDER = "gdl"
GDL_PROMPT_VERSION = "gdl-import-v1"
GDL_THEME = "open_picture_book"
SUPPORTED_LICENSES = {"CC-BY-4.0", "CC-BY-SA-4.0"}
OFFICIAL_HOSTS = {"content.digitallibrary.io", "digitallibrary.io", "www.digitallibrary.io"}
MAX_JSON_BYTES = 6 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 32
MAX_PAGE_TEXT = 500
_IMAGE_RE = re.compile(r"\.(?:jpe?g|png|webp)(?:\?.*)?$", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class GDLImportError(RuntimeError):
    """Safe user-facing failure while discovering or importing an open book."""


@dataclass(frozen=True)
class ParsedPage:
    text: str
    image_url: str | None
    image_alt: str | None


def _safe_official_url(value: str, *, allow_api_host: bool = True) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GDLImportError("绘本来源地址不安全")
    allowed = OFFICIAL_HOSTS if allow_api_host else OFFICIAL_HOSTS - {"content.digitallibrary.io"}
    if parsed.hostname.lower() not in allowed:
        raise GDLImportError("绘本资源不是来自受信任的 GDL 域名")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise GDLImportError("绘本来源地址不安全")
    return value


def _plain_text(value: str) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value))
    return _SPACE_RE.sub(" ", text).strip()


def _terms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for key in ("name", "slug"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate:
                    result.append(candidate)
    return result


def _license_name(book: dict[str, Any]) -> str | None:
    for value in _terms(book.get("license")):
        normalized = value.upper().replace("_", "-").replace(" ", "-")
        normalized = normalized.replace("CC-BY-SA-4-0", "CC-BY-SA-4.0").replace(
            "CC-BY-4-0", "CC-BY-4.0"
        )
        if normalized in SUPPORTED_LICENSES:
            return normalized
    return None


def _reading_level(book: dict[str, Any]) -> str | None:
    candidates = _terms(book.get("level")) + _terms(book.get("topic"))
    joined = " ".join(candidates).lower().replace("_", "-")
    if any(token in joined for token in ("level 1", "level-1", "level1", "emergent-reader")):
        return "1"
    if any(token in joined for token in ("level 2", "level-2", "level2")):
        return "2"
    return None


def _author_names(book: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("author", "authors", "creator", "creators"):
        value = book.get(key)
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        names.append(name.strip())
    return list(dict.fromkeys(names))


def _book_summary(book: dict[str, Any]) -> OpenPictureBookSummary | None:
    license_name = _license_name(book)
    level = _reading_level(book)
    if license_name is None or level not in {"1", "2"}:
        return None
    post_id = book.get("postId")
    title = _plain_text(str(book.get("title") or ""))
    source_url = str(book.get("postLink") or "")
    if not post_id or not title or not source_url:
        return None
    try:
        _safe_official_url(source_url)
        thumbnail = str(book.get("thumbnail") or "") or None
        if thumbnail:
            _safe_official_url(thumbnail)
    except GDLImportError:
        return None
    publisher = book.get("publisher")
    return OpenPictureBookSummary(
        source_book_id=str(post_id),
        title=title,
        description=_plain_text(str(book.get("description") or "")),
        reading_level=level,
        license_name=license_name,
        source_url=source_url,
        thumbnail_url=thumbnail,
        publisher=str(publisher).strip() if publisher else None,
        authors=_author_names(book),
    )


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    _safe_official_url(url)
    response = await client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        raise GDLImportError("GDL 返回了无法识别的数据格式")
    if len(response.content) > MAX_JSON_BYTES:
        raise GDLImportError("GDL 返回的数据过大")
    try:
        return response.json()
    except ValueError as error:
        raise GDLImportError("GDL 返回的数据无法解析") from error


async def _all_books(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    data = await _fetch_json(client, f"{GDL_API_ROOT}/wp-json/content-api/v1/books/{GDL_LANGUAGE}")
    books = data.get("books") if isinstance(data, dict) else None
    if not isinstance(books, list):
        raise GDLImportError("GDL 中文绘本目录暂时不可用")
    return [item for item in books if isinstance(item, dict)]


async def discover_gdl_books(*, level: str | None = None) -> list[OpenPictureBookSummary]:
    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        books = await _all_books(client)
    summaries = [summary for book in books if (summary := _book_summary(book)) is not None]
    if level in {"1", "2"}:
        summaries = [item for item in summaries if item.reading_level == level]
    return sorted(summaries, key=lambda item: (item.reading_level, item.title))


def _walk_strings(node: Any, *, key_hint: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_walk_strings(value, key_hint=str(key).lower()))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk_strings(value, key_hint=key_hint))
    elif isinstance(node, str):
        found.append((key_hint, node))
    return found


def _resolve_image_url(value: str, *, h5p_id: str) -> str | None:
    value = html.unescape(value).strip()
    if not value or not _IMAGE_RE.search(value):
        return None
    if value.startswith("https://"):
        return _safe_official_url(value)
    value = value.lstrip("/")
    if value.startswith("wp-content/"):
        return _safe_official_url(urljoin("https://digitallibrary.io/", value))
    return _safe_official_url(
        f"https://digitallibrary.io/wp-content/uploads/h5p/content/{h5p_id}/{value}"
    )


def parse_h5p_pages(payload: Any, *, h5p_id: str) -> list[ParsedPage]:
    if not isinstance(payload, dict) or not isinstance(payload.get("chapters"), list):
        raise GDLImportError("这个 GDL 绘本的页面结构暂时不受支持")
    pages: list[ParsedPage] = []
    for chapter in payload["chapters"][:MAX_PAGES]:
        strings = _walk_strings(chapter)
        texts: list[str] = []
        image_urls: list[str] = []
        image_alt: str | None = None
        for key, raw in strings:
            if any(token in key for token in ("alt", "description")) and raw.strip() and image_alt is None:
                candidate_alt = _plain_text(raw)
                if candidate_alt and len(candidate_alt) <= 160:
                    image_alt = candidate_alt
            try:
                image = _resolve_image_url(raw, h5p_id=h5p_id)
            except GDLImportError:
                image = None
            if image:
                image_urls.append(image)
                continue
            if key in {"text", "html", "content", "description"} or "text" in key:
                candidate = _plain_text(raw)
                if extract_han(candidate) and 1 <= len(candidate) <= MAX_PAGE_TEXT:
                    texts.append(candidate)
        text = " ".join(dict.fromkeys(texts)).strip()
        if not text:
            continue
        pages.append(ParsedPage(text=text, image_url=image_urls[0] if image_urls else None, image_alt=image_alt))
    if len(pages) < 2:
        raise GDLImportError("这个 GDL 绘本暂时无法可靠提取为分页阅读内容")
    return pages


async def _download_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    _safe_official_url(url)
    response = await client.get(url)
    response.raise_for_status()
    mime = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise GDLImportError("绘本页面包含不支持的图片格式")
    if len(response.content) > MAX_IMAGE_BYTES:
        raise GDLImportError("绘本页面图片过大")
    return response.content, mime


def _image_extension(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]


async def _book_by_id(client: httpx.AsyncClient, source_book_id: str) -> dict[str, Any]:
    books = await _all_books(client)
    for book in books:
        if str(book.get("postId")) == source_book_id:
            if _book_summary(book) is None:
                raise GDLImportError("这本绘本的级别或开放许可不符合导入要求")
            return book
    raise GDLImportError("没有找到这本 GDL 中文绘本")


async def import_gdl_picture_book(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    child: Child,
    imported_by_user_id: uuid.UUID,
    source_book_id: str,
) -> tuple[PictureBookImport, StoryVersion, bool]:
    existing = await session.scalar(
        select(PictureBookImport).where(
            PictureBookImport.child_id == child.id,
            PictureBookImport.source_provider == GDL_PROVIDER,
            PictureBookImport.source_book_id == source_book_id,
        )
    )
    if existing is not None:
        version = await session.get(StoryVersion, existing.story_version_id)
        if version is None:
            raise GDLImportError("绘本导入记录损坏，请联系管理员")
        return existing, version, False

    timeout = httpx.Timeout(15.0, connect=5.0)
    stored_keys: list[str] = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        book = await _book_by_id(client, source_book_id)
        summary = _book_summary(book)
        assert summary is not None
        h5p_id = str(book.get("h5pId") or "").strip()
        if not h5p_id.isdigit():
            raise GDLImportError("这本绘本缺少可读取的 H5P 内容")
        h5p = await _fetch_json(client, f"{GDL_API_ROOT}/wp-json/content-api/v1/h5p/{h5p_id}")
        pages = parse_h5p_pages(h5p, h5p_id=h5p_id)

        snapshot = await build_mastery_snapshot(session, child.id)
        paragraphs = [page.text for page in pages]
        analysis = analyze_story_coverage(
            title=summary.title,
            paragraphs=paragraphs,
            strong_known=set(snapshot.strong),
            usable_recognizing=set(snapshot.recognizing),
            targets=set(),
        )
        story = Story(
            child_id=child.id,
            created_by_user_id=imported_by_user_id,
            theme=GDL_THEME,
            custom_theme=None,
        )
        session.add(story)
        await session.flush()
        run = StoryGenerationRun(
            child_id=child.id,
            requested_by_user_id=imported_by_user_id,
            story_id=story.id,
            request_key=f"gdl:{source_book_id}",
            status=StoryGenerationStatus.SUCCEEDED,
            difficulty="beginner" if summary.reading_level == "1" else "normal",
            theme=GDL_THEME,
            target_knowledge_point_ids=[],
            provider=GDL_PROVIDER,
            model=f"h5p:{h5p_id}",
            prompt_version=GDL_PROMPT_VERSION,
            attempt_count=0,
            latency_ms=0,
        )
        session.add(run)
        await session.flush()
        version = StoryVersion(
            story_id=story.id,
            generation_run_id=run.id,
            version_number=1,
            title=summary.title,
            paragraphs=paragraphs,
            summary=summary.description or None,
            theme=GDL_THEME,
            custom_theme=None,
            difficulty=run.difficulty,
            requested_known_coverage=0.0,
            actual_strong_known_coverage=analysis.strong_known_coverage,
            actual_usable_known_coverage=analysis.usable_known_coverage,
            actual_target_coverage=0.0,
            actual_unexpected_coverage=analysis.unexpected_coverage,
            unique_known_coverage=analysis.unique_known_coverage,
            total_han_occurrences=analysis.total_han_occurrences,
            unique_han_count=analysis.unique_han_count,
            unexpected_characters=list(analysis.unexpected_characters),
            target_characters=[],
            mastery_snapshot=_snapshot_payload(snapshot),
            snapshot_at=snapshot.at,
            coverage_policy_version=COVERAGE_POLICY_VERSION,
            analyzer_version=ANALYZER_VERSION,
            prompt_version=GDL_PROMPT_VERSION,
            provider=GDL_PROVIDER,
            model=f"h5p:{h5p_id}",
        )
        session.add(version)
        await session.flush()

        catalog_rows = list(
            (
                await session.execute(
                    select(KnowledgePoint.id, ChineseCharacter)
                    .join(ChineseCharacter)
                    .where(ChineseCharacter.character.in_(set(analysis.occurrences)))
                )
            ).all()
        )
        snapshot_by_char = {item.character: item for item in snapshot.characters}
        for point_id, char in catalog_rows:
            if char.character in snapshot.strong:
                role = StoryKnowledgeRole.STRONG_KNOWN
            elif char.character in snapshot.recognizing:
                role = StoryKnowledgeRole.USABLE_RECOGNIZING
            else:
                role = StoryKnowledgeRole.UNEXPECTED
            session.add(
                StoryKnowledgePoint(
                    story_version_id=version.id,
                    knowledge_point_id=point_id,
                    role=role,
                    occurrence_count=analysis.occurrence_counts[char.character],
                    mastery_level_at_generation=(
                        snapshot_by_char[char.character].mastery_level
                        if char.character in snapshot_by_char
                        else None
                    ),
                )
            )

        page_payloads: list[dict[str, object]] = []
        try:
            for position, page in enumerate(pages):
                object_key: str | None = None
                mime: str | None = None
                if page.image_url:
                    image_bytes, mime = await _download_image(client, page.image_url)
                    extension = _image_extension(mime)
                    object_key = (
                        f"picture-books/{child.id}/{version.id}/pages/{position:03d}.{extension}"
                    )
                    await storage.put(object_key, image_bytes, mime)
                    stored_keys.append(object_key)
                page_payloads.append(
                    {
                        "position": position,
                        "text": page.text,
                        "image_object_key": object_key,
                        "image_mime_type": mime,
                        "image_alt": page.image_alt,
                        "source_image_url": page.image_url,
                    }
                )
        except Exception:
            for key in stored_keys:
                try:
                    await storage.remove(key)
                except Exception:
                    pass
            await session.rollback()
            raise

        attribution: dict[str, object] = {
            "title": summary.title,
            "authors": summary.authors,
            "publisher": summary.publisher,
            "source": "Global Digital Library",
            "source_url": summary.source_url,
            "license": summary.license_name,
        }
        picture_book = PictureBookImport(
            child_id=child.id,
            story_version_id=version.id,
            imported_by_user_id=imported_by_user_id,
            source_provider=GDL_PROVIDER,
            source_book_id=source_book_id,
            source_h5p_id=h5p_id,
            source_url=summary.source_url,
            license_name=summary.license_name,
            reading_level=summary.reading_level,
            attribution=attribution,
            pages=page_payloads,
            cover_object_key=(
                next(
                    (
                        str(page["image_object_key"])
                        for page in page_payloads
                        if page.get("image_object_key")
                    ),
                    None,
                )
            ),
        )
        session.add(picture_book)
        run.story_version_id = version.id
        await get_or_create_daily_plan(session, child.id)
        await attach_story_to_today(session, child.id, version.id)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            for key in stored_keys:
                try:
                    await storage.remove(key)
                except Exception:
                    pass
            raise
        await session.refresh(picture_book)
        await session.refresh(version)
        return picture_book, version, True


async def picture_book_detail(
    session: AsyncSession, *, child_id: uuid.UUID, story_version_id: uuid.UUID
) -> PictureBookDetail | None:
    picture = await session.scalar(
        select(PictureBookImport).where(
            PictureBookImport.child_id == child_id,
            PictureBookImport.story_version_id == story_version_id,
        )
    )
    if picture is None:
        return None
    version = await session.get(StoryVersion, story_version_id)
    if version is None:
        return None
    pages: list[OpenPictureBookPage] = []
    for index, text in enumerate(version.paragraphs):
        stored = picture.pages[index] if index < len(picture.pages) else {}
        pages.append(
            OpenPictureBookPage(
                position=index,
                text=text,
                image_available=bool(stored.get("image_object_key")),
                image_alt=(str(stored.get("image_alt")) if stored.get("image_alt") else None),
                pinyin=annotate_paragraph_pinyin(text),
            )
        )
    return PictureBookDetail(
        id=picture.id,
        story_version_id=version.id,
        title=version.title,
        source_provider=picture.source_provider,
        source_book_id=picture.source_book_id,
        source_url=picture.source_url,
        license_name=picture.license_name,
        reading_level=picture.reading_level,
        attribution=picture.attribution,
        pages=pages,
    )


def picture_page_object(picture: PictureBookImport, page_index: int) -> tuple[str, str] | None:
    if page_index < 0 or page_index >= len(picture.pages):
        return None
    page = picture.pages[page_index]
    key = page.get("image_object_key")
    mime = page.get("image_mime_type")
    if not key or not mime:
        return None
    return str(key), str(mime)
