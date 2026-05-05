"""Tests for URL hallucination guard."""
import pytest
from backend.core.accuracy.citation_validator import strip_hallucinated_urls


class TestStripHallucinatedUrls:
    def test_empty_allowed_strips_all_hyperlinks(self):
        """When no sources exist, ALL markdown links must be stripped."""
        text = "Contact [Beta Consultants](https://betaconsultants.ae) for help."
        result = strip_hallucinated_urls(text, set())
        assert result == "Contact Beta Consultants for help."
        assert "http" not in result

    def test_empty_allowed_strips_multiple_links(self):
        text = "See [Deloitte](https://deloitte.com) or [PwC](https://pwc.com)."
        result = strip_hallucinated_urls(text, set())
        assert "http" not in result
        assert "Deloitte" in result
        assert "PwC" in result

    def test_allowed_url_is_kept(self):
        allowed = {"https://realdoc.ae/source.pdf"}
        text = "See [source](https://realdoc.ae/source.pdf) for details."
        result = strip_hallucinated_urls(text, allowed)
        assert "https://realdoc.ae/source.pdf" in result

    def test_disallowed_url_stripped_when_allowed_set_nonempty(self):
        allowed = {"https://realdoc.ae/source.pdf"}
        text = "See [fake](https://invented.com) or [real](https://realdoc.ae/source.pdf)."
        result = strip_hallucinated_urls(text, allowed)
        assert "https://invented.com" not in result
        assert "https://realdoc.ae/source.pdf" in result

    def test_plain_text_unchanged(self):
        result = strip_hallucinated_urls("No links here at all.", set())
        assert result == "No links here at all."

    def test_url_with_parentheses_stripped_cleanly(self):
        """Parentheses inside URLs must not corrupt output."""
        text = "See [Tax](https://en.wikipedia.org/wiki/Tax_(UAE)) for details."
        result = strip_hallucinated_urls(text, set())
        assert result == "See Tax for details."
        assert ")" not in result.replace(" details.", "")  # no stray paren

    def test_image_links_not_mangled(self):
        """Image links (![alt](url)) should not be touched by the strip."""
        text = "Here is an image: ![logo](https://example.com/logo.png)"
        result = strip_hallucinated_urls(text, set())
        # Image link must survive — should not become "!logo"
        assert "![logo]" in result or "logo" in result
        assert result != "Here is an image: !logo"


    def test_url_with_parentheses_nonempty_set(self):
        """Parens-in-URL bug must not occur on the non-empty allowed_urls path."""
        allowed = {"https://legit.ae/doc.pdf"}
        text = "See [Tax](https://en.wikipedia.org/wiki/Tax_(UAE)) for info."
        result = strip_hallucinated_urls(text, allowed)
        assert result == "See Tax for info."
        assert ")" not in result.rstrip(".")  # no stray paren

    def test_image_links_not_mangled_nonempty_set(self):
        """Image links must be preserved on the non-empty allowed_urls path."""
        allowed = {"https://legit.ae/doc.pdf"}
        text = "Image: ![logo](https://example.com/logo.png)"
        result = strip_hallucinated_urls(text, allowed)
        assert "!logo" not in result
