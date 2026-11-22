from pathlib import Path

import ebooklib
from ebooklib import epub

from darsvp_scorer.extract import load_book


def _build_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Jane Doe")

    first = epub.EpubHtml(title="Chapter One", file_name="c1.xhtml", lang="en")
    first.content = (
        "<html><body><h1>Chapter One</h1>"
        "<p>It was <i>very</i> cold.<sup>1</sup></p>"
        "<p>Second para<br/>with break.</p>"
        "<p>press\ted h\tard, mag\tic.</p>"
        "<p>Thencame a bright day.</p></body></html>"
    )
    second = epub.EpubHtml(title="Chapter Two", file_name="c2.xhtml", lang="en")
    second.content = (
        "<html><body><h1>Chapter Two</h1><p>Another chapter here.</p></body></html>"
    )
    hidden = epub.EpubHtml(title="Hidden", file_name="c3.xhtml", lang="en")
    hidden.content = "<html><body><p>This should be skipped.</p></body></html>"

    for item in (first, second, hidden):
        book.add_item(item)
    book.toc = (
        epub.Link("c1.xhtml", "Chapter One", "c1"),
        epub.Link("c2.xhtml", "Chapter Two", "c2"),
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [first, second, (hidden, "no")]
    epub.write_epub(str(path), book)


def test_epub_chapters_and_cleanup(tmp_path):
    path = tmp_path / "tiny.epub"
    _build_epub(path)
    book = load_book(path, include_cover=False)

    assert book.title == "Test Book"
    assert book.author == "Jane Doe"
    assert book.language == "en"
    assert [chapter.title for chapter in book.chapters] == ["Chapter One", "Chapter Two"]

    first = book.chapters[0]
    words = [word for paragraph in first.paragraphs for word in paragraph]
    assert "very" in words
    assert "cold." in words
    assert "1" not in words
    assert "with" in words
    assert "break." in words
    assert "pressed" in words
    assert "hard," in words
    assert "magic." in words
    assert "press" not in words
    assert "ed" not in words
    assert "Then" in words
    assert "came" in words
    assert "Thencame" not in words

    all_words = [word for chapter in book.chapters for paragraph in chapter.paragraphs for word in paragraph]
    assert "skipped." not in all_words


def test_txt_paragraphs(tmp_path):
    path = tmp_path / "story.txt"
    path.write_text("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.\n", encoding="utf-8")
    book = load_book(path, include_cover=False)
    assert book.title == "story"
    assert len(book.chapters) == 1
    assert len(book.chapters[0].paragraphs) == 3
    assert book.chapters[0].paragraphs[0] == ["First", "paragraph."]
