"""Helper methods for the HealthChecks.io integration."""

from __future__ import annotations

import re
from urllib.parse import ParseResult, urlparse, urlunparse

from homeassistant.config_entries import ConfigEntry


def get_entity_type_option(config_entry: ConfigEntry, option: str, default: bool) -> bool:
    """Return an entity-type option, falling back to legacy entry data."""
    return config_entry.options.get(option, config_entry.data.get(option, default))


def clean_url(url: str) -> str:
    """Cleanup slashes from URL."""
    parsed: ParseResult = urlparse(url)

    if not parsed.scheme:
        parsed = urlparse("https://" + url)

    cleaned_path: str = re.sub(r"/+", "/", parsed.path)
    if cleaned_path != "/":
        cleaned_path = cleaned_path.rstrip("/")

    cleaned: ParseResult = parsed._replace(path=cleaned_path)
    return urlunparse(cleaned)
