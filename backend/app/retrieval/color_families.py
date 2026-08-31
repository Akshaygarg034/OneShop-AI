"""Color-family normalization.

The catalog stores only basic color names (black, white, gray, blue, red,
green, yellow, pink, purple, brown). This map normalizes the shade names
shoppers might *say* ("navy", "titanium", "lemon") onto that basic palette,
so phrasing never has to match the catalog vocabulary exactly.
"""
from __future__ import annotations

COLOR_FAMILY: dict[str, str] = {
    # yellow
    "lemon": "yellow",
    "gold": "yellow",
    # blue
    "navy": "blue",
    "midnight blue": "blue",
    "storm blue": "blue",
    "aqua": "blue",
    "teal": "blue",
    "cyan": "blue",
    # purple
    "violet": "purple",
    "lilac": "purple",
    "lavender": "purple",
    # pink
    "light pink": "pink",
    "rose": "pink",
    "rose gold": "pink",
    # black
    "obsidian": "black",
    "midnight": "black",
    # gray
    "graphite": "gray",
    "space gray": "gray",
    "titanium": "gray",
    "silver": "gray",
    "platinum": "gray",
    "grey": "gray",
    # white
    "starlight": "white",
    "porcelain": "white",
    "cream": "white",
    "ivory": "white",
    # green
    "mint": "green",
    "olive": "green",
    # red
    "crimson": "red",
    "maroon": "red",
    # brown
    "beige": "brown",
    "tan": "brown",
}


def color_family(name: str) -> str:
    name = name.strip().lower()
    return COLOR_FAMILY.get(name, name)


def expand_colors(colors: list[str]) -> list[str]:
    """Shade names plus their families, deduped — used for the search payload."""
    expanded: list[str] = []
    for color in colors:
        color = color.strip().lower()
        for value in (color, color_family(color)):
            if value not in expanded:
                expanded.append(value)
    return expanded


def colors_match(requested: list[str], product_colors: list[str]) -> bool:
    """True when any requested color matches any product shade, by exact name
    or by family ("yellow" matches "lemon"; "lemon" matches only lemon)."""
    wanted = {c.strip().lower() for c in requested}
    wanted |= {color_family(c) for c in wanted}
    for shade in product_colors:
        shade = shade.strip().lower()
        if shade in wanted or color_family(shade) in wanted:
            return True
    return False
