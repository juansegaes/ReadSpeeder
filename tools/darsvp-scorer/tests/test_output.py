import base64
import copy
import json

import pytest

from darsvp_scorer.output import validate_document


def valid_document():
    return {
        "format": "darsvp",
        "version": 1,
        "title": "Test Book",
        "author": "Jane Doe",
        "language": "en",
        "generator": {
            "tool": "darsvp-scorer",
            "toolVersion": "0.1.0",
            "backend": "unigram",
            "model": "wordfreq",
            "normalize": "content",
            "created": "2026-11-22T12:00:00Z",
        },
        "text": "Hello world.\n\nAnother paragraph.",
        "chapters": [{"title": "Chapter One", "startWord": 0}],
        "weights": [100, 150, 100, 120],
        "cover": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x").decode("ascii"),
    }


def test_valid_document_passes():
    validate_document(valid_document())


def test_round_trip_passes():
    document = valid_document()
    validate_document(json.loads(json.dumps(document)))


def broken(mutator):
    document = copy.deepcopy(valid_document())
    mutator(document)
    return document


@pytest.mark.parametrize(
    "mutator",
    [
        lambda document: document.update(format="other"),
        lambda document: document.update(version=2),
        lambda document: document.update(title=""),
        lambda document: document.update(language="xx"),
        lambda document: document.update(text=""),
        lambda document: document.update(text="Hello  world.\n\nAnother paragraph."),
        lambda document: document.update(text="Hello\tworld.\n\nAnother paragraph."),
        lambda document: document.update(weights=[100, 150, 100]),
        lambda document: document.update(weights=[100, 150, 100, 5000]),
        lambda document: document.update(weights=[100, 150, 100, "120"]),
        lambda document: document.update(chapters=[{"title": "A", "startWord": 2}, {"title": "B", "startWord": 1}]),
        lambda document: document.update(chapters=[{"title": "A", "startWord": 4}]),
        lambda document: document.update(cover="not base64!"),
        lambda document: document.update(cover=base64.b64encode(b"hello").decode("ascii")),
    ],
)
def test_broken_documents_raise(mutator):
    with pytest.raises(ValueError):
        validate_document(broken(mutator))
