"""Tests for lore.validators._validate_content_nonempty (G15 — amendment Section C3).

Spec:
  lore codex show transient-public-api-facade-plan        (### G15)
  lore codex show transient-public-api-facade-create-stdz (Section C3)

Signature under test:
    def _validate_content_nonempty(content: str) -> str | None:
        '''Return error message if content is empty or whitespace-only, else None.'''

Internal (leading underscore) — lives in lore.validators but is NOT facade-exported.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------


class TestValidateContentNonemptyImportable:
    def test_validator_is_importable_from_lore_validators(self):
        from lore.validators import _validate_content_nonempty  # noqa: F401

    def test_validator_is_callable(self):
        from lore.validators import _validate_content_nonempty

        assert callable(_validate_content_nonempty)


# ---------------------------------------------------------------------------
# Empty / whitespace -> error string
# ---------------------------------------------------------------------------


class TestRejectsEmptyOrWhitespace:
    def test_empty_string_returns_error_string(self):
        from lore.validators import _validate_content_nonempty

        result = _validate_content_nonempty("")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize(
        "ws",
        [
            " ",
            "  ",
            "\t",
            "\n",
            "\r\n",
            "   \n\t  ",
            "\n\n\n",
        ],
    )
    def test_whitespace_only_returns_error_string(self, ws: str):
        from lore.validators import _validate_content_nonempty

        result = _validate_content_nonempty(ws)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_error_message_mentions_content(self):
        """Message should signal what was wrong (mentions 'content' or 'empty')."""
        from lore.validators import _validate_content_nonempty

        msg = _validate_content_nonempty("")
        assert msg is not None
        lowered = msg.lower()
        assert "content" in lowered or "empty" in lowered


# ---------------------------------------------------------------------------
# Valid content -> None
# ---------------------------------------------------------------------------


class TestAcceptsValidContent:
    @pytest.mark.parametrize(
        "content",
        [
            "hello",
            "a",
            "0",
            "  surrounded  ",          # whitespace + real char -> still valid
            "line1\nline2",
            "---\ntitle: x\n---\nbody",
            "# Heading\n\nParagraph.",
        ],
    )
    def test_valid_content_returns_none(self, content: str):
        from lore.validators import _validate_content_nonempty

        assert _validate_content_nonempty(content) is None


# ---------------------------------------------------------------------------
# Not exported through the public facade (leading underscore → internal).
# ---------------------------------------------------------------------------


class TestValidatorIsNotFacadeExported:
    def test_validate_content_nonempty_not_in_api_all(self):
        from lore import api

        assert "_validate_content_nonempty" not in api.__all__
        assert "validate_content_nonempty" not in api.__all__
