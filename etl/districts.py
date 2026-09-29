"""
Dictionary of Kraków districts and matching raw location from the listing.
"""

import re
import unicodedata

KRAKOW_DISTRICTS = [
    "Stare Miasto",
    "Grzegórzki",
    "Prądnik Czerwony",
    "Prądnik Biały",
    "Krowodrza",
    "Bronowice",
    "Zwierzyniec",
    "Dębniki",
    "Łagiewniki-Borek Fałęcki",
    "Swoszowice",
    "Podgórze Duchackie",
    "Bieżanów-Prokocim",
    "Podgórze",
    "Czyżyny",
    "Mistrzejowice",
    "Bieńczyce",
    "Wzgórza Krzesławickie",
    "Nowa Huta",
]

ALIASES = {
    "Łagiewniki": "Łagiewniki-Borek Fałęcki",
    "Borek Fałęcki": "Łagiewniki-Borek Fałęcki",
    "Prokocim": "Bieżanów-Prokocim",
    "Bieżanów": "Bieżanów-Prokocim",
    "Kazimierz": "Stare Miasto",
}


def text_key(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


_LOOKUP = {text_key(name): name for name in KRAKOW_DISTRICTS}
_LOOKUP.update({text_key(alias): district for alias, district in ALIASES.items()})


def match_district(location_raw: str | None) -> str | None:
    """Returns the official name of the district or None if the location is not a district."""
    if not location_raw:
        return None
    return _LOOKUP.get(text_key(location_raw))
