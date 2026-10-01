import gettext
import json
import logging
import re
from functools import cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Shipped by the "iso-codes" package (a GNOME dependency on most distros),
# along with translations in the matching gettext domains
ISO_CODES_DIR = Path("/usr/share/iso-codes/json")
# Passed explicitly: gettext's default is relative to the Python prefix, which
# isn't /usr in a virtualenv or a uv-managed interpreter
LOCALE_DIR = Path("/usr/share/locale")


@cache
def _load_languages() -> dict[str, str]:
    """Map ISO 639 codes (2-letter, 3-letter terminology and bibliographic) to names."""
    names: dict[str, str] = {}
    try:
        iso_639_2 = json.loads((ISO_CODES_DIR / "iso_639-2.json").read_text())["639-2"]
        iso_639_3 = json.loads((ISO_CODES_DIR / "iso_639-3.json").read_text())["639-3"]
    except (OSError, ValueError, KeyError) as e:
        logger.debug("Could not load ISO 639 language names: %s", e)
        return names

    # ISO 639-3 names are terser ("Spanish" rather than "Spanish; Castilian")
    translate_3 = gettext.translation("iso_639-3", LOCALE_DIR, fallback=True).gettext
    for entry in iso_639_3:
        names[entry["alpha_3"]] = translate_3(entry["name"])

    translate_2 = gettext.translation("iso_639-2", LOCALE_DIR, fallback=True).gettext
    for entry in iso_639_2:
        name = names.get(entry["alpha_3"]) or translate_2(entry["name"])
        for key in ("alpha_2", "alpha_3", "bibliographic"):
            if key in entry:
                names.setdefault(entry[key], name)
    return names


def language_name(code: str | None) -> str | None:
    """
    Return the localized name of a language tag like "fre", "fr" or "fr-CA",
    or None if it's unknown or undetermined.
    """
    if not code:
        return None
    code = code.lower().replace("_", "-").split("-")[0]
    if code in ("und", "mis", "zxx"):
        return None
    name = _load_languages().get(code)
    if not name:
        return None
    # "Grec moderne (après 1453)" -> "Grec moderne", "Malay (macrolanguage)" -> "Malay"
    return re.sub(r"\s*\(.*\)$", "", name)
