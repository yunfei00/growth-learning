import pytest

from app.services.gdl_picture_books import (
    GDLImportError,
    _book_summary,
    _safe_official_url,
    parse_h5p_pages,
)


def _book(*, license_name: str = "CC-BY-4.0", level: str = "Level 1") -> dict:
    return {
        "postId": 42,
        "title": "小熊回家",
        "description": "一本文字很短的故事。",
        "postLink": "https://digitallibrary.io/zh-cn/book/xiao-xiong-hui-jia/",
        "h5pId": "123",
        "thumbnail": "https://digitallibrary.io/wp-content/uploads/cover.jpg",
        "language": [{"slug": "zh-cn", "name": "Chinese"}],
        "level": [{"slug": "level-1", "name": level}],
        "license": [{"slug": "cc-by-4-0", "name": license_name}],
        "publisher": "Open Publisher",
        "authors": [{"name": "作者甲"}],
    }


def test_book_summary_accepts_allowlisted_level_and_license() -> None:
    summary = _book_summary(_book())
    assert summary is not None
    assert summary.source_book_id == "42"
    assert summary.reading_level == "1"
    assert summary.license_name == "CC-BY-4.0"
    assert summary.authors == ["作者甲"]


def test_book_summary_rejects_missing_or_unsupported_license() -> None:
    assert _book_summary(_book(license_name="All Rights Reserved")) is None
    item = _book()
    item["license"] = []
    assert _book_summary(item) is None


def test_gdl_url_validation_rejects_ssrf_and_non_https() -> None:
    assert _safe_official_url("https://digitallibrary.io/path") == (
        "https://digitallibrary.io/path"
    )
    with pytest.raises(GDLImportError):
        _safe_official_url("http://digitallibrary.io/path")
    with pytest.raises(GDLImportError):
        _safe_official_url("https://127.0.0.1/private")
    with pytest.raises(GDLImportError):
        _safe_official_url("https://digitallibrary.io.evil.example/path")


def test_parse_h5p_pages_extracts_ordered_text_and_images() -> None:
    payload = {
        "chapters": [
            {
                "params": {
                    "content": [
                        {
                            "content": {
                                "params": {
                                    "file": {
                                        "path": "images/page-1.jpg",
                                        "mime": "image/jpeg",
                                    }
                                }
                            }
                        },
                        {"content": {"params": {"text": "<p>小猫来到窗边。</p>"}}},
                    ]
                }
            },
            {
                "params": {
                    "content": [
                        {"content": {"params": {"file": {"path": "images/page-2.png"}}}},
                        {"content": {"params": {"text": "<p>太阳暖暖的，小猫开心地坐下来。</p>"}}},
                    ]
                }
            },
        ]
    }
    pages = parse_h5p_pages(payload, h5p_id="123")
    assert [page.text for page in pages] == [
        "小猫来到窗边。",
        "太阳暖暖的，小猫开心地坐下来。",
    ]
    assert pages[0].image_url == (
        "https://digitallibrary.io/wp-content/uploads/h5p/content/123/images/page-1.jpg"
    )


def test_parse_h5p_pages_refuses_unreliable_single_page_shape() -> None:
    with pytest.raises(GDLImportError):
        parse_h5p_pages({"chapters": [{"params": {"text": "<p>只有一页。</p>"}}]}, h5p_id="123")
