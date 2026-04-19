"""Template renderer — renders a template string with sample or real data."""
import json
import logging
from pathlib import Path
from string import Template

logger = logging.getLogger(__name__)

_FIXTURE_PATH = Path(__file__).parent / "sample_fixture.json"


def load_sample_data() -> dict:
    """Load the sample fixture data."""
    try:
        with open(_FIXTURE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("sample_fixture.json missing or invalid: %s", e)
        return {}


def render_template(template_body: str, data: dict | None = None) -> str:
    """
    Render a template string using Python string.Template.

    Supports ${variable} and $variable syntax.
    Nested data is flattened: company.name → company_name.
    """
    if data is None:
        data = load_sample_data()

    flat = _flatten(data)
    try:
        return Template(template_body).safe_substitute(flat)
    except Exception as e:
        logger.warning("Template render failed: %s", e)
        return template_body


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict for Template substitution."""
    items: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
        if isinstance(v, dict):
            items.update(_flatten(v, key))
        elif isinstance(v, list):
            items[key] = json.dumps(v)
        else:
            items[key] = str(v)
    return items
