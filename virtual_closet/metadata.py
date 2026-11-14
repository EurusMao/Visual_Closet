
"""Shared upload review and naming rules."""

from .attributes import (
    CATEGORIES,
    SUBCATEGORIES,
    COLORS,
    BASE_PATTERNS,
    DECORATIONS,
    FITS,
    SLEEVE_LENGTHS,
    NECKLINES,
    CLOTHING_LENGTHS,
    UNKNOWN_ATTRIBUTE,
)


UNKNOWN = {
    "",
    "unknown",
    "none",
    "other / unspecified",
    "uncategorized"
}


# Clothing categories that support sleeves and necklines
UPPER_CATEGORIES = {
    "T-shirt",
    "Shirt",
    "Sweater",
    "Hoodie",
    "Jacket",
    "Coat",
    "Dress",
}


def clean_brand(value):
    return (value or "").strip() or None


def normalize_choice(value, candidates, fallback="Unknown"):
    """Return a valid canonical attribute label."""

    if not value:
        return fallback

    value = str(value).strip()

    for candidate in candidates:
        if candidate.casefold() == value.casefold():
            return candidate

    return fallback


def reviewed_attributes(attributes, category):
    """
    Validate clothing attributes after AI analysis
    or user editing.
    """

    attrs = dict(attributes)

    # 1. Validate Category
    category = (category or "").strip() or "Uncategorized"

    category = next(
        (
            c for c in CATEGORIES
            if c.casefold() == category.casefold()
        ),
        category
    )

    attrs["Category"] = category

    # 2. Validate Subcategory
    valid_subcategories = SUBCATEGORIES.get(category, [])

    attrs["Subcategory"] = normalize_choice(
        attrs.get("Subcategory"),
        valid_subcategories,
        fallback="Other / unspecified"
    )

    # 3. Validate existing visual attributes
    if "Color" in attrs:
        attrs["Color"] = normalize_choice(
            attrs["Color"],
            COLORS
        )

    if "Base pattern" in attrs:
        attrs["Base pattern"] = normalize_choice(
            attrs["Base pattern"],
            BASE_PATTERNS.keys()
        )

    if "Decoration" in attrs:
        attrs["Decoration"] = normalize_choice(
            attrs["Decoration"],
            DECORATIONS.keys()
        )

    # 4. Validate new attributes
    attrs["Fit"] = normalize_choice(
        attrs.get("Fit"),
        FITS.keys()
    )

    attrs["Sleeve Length"] = normalize_choice(
        attrs.get("Sleeve Length"),
        SLEEVE_LENGTHS.keys()
    )

    attrs["Neckline"] = normalize_choice(
        attrs.get("Neckline"),
        NECKLINES.keys()
    )

    attrs["Clothing Length"] = normalize_choice(
        attrs.get("Clothing Length"),
        CLOTHING_LENGTHS.keys()
    )

    # 5. Apply category-specific restrictions
    if category == "Shoes":
        attrs["Fit"] = UNKNOWN_ATTRIBUTE
        attrs["Sleeve Length"] = UNKNOWN_ATTRIBUTE
        attrs["Neckline"] = UNKNOWN_ATTRIBUTE
        attrs["Clothing Length"] = UNKNOWN_ATTRIBUTE

    elif category not in UPPER_CATEGORIES:
        attrs["Sleeve Length"] = UNKNOWN_ATTRIBUTE
        attrs["Neckline"] = UNKNOWN_ATTRIBUTE

    return attrs


def automatic_name(attributes, brand=None):
    brand = clean_brand(brand)

    color = str(attributes.get("Color") or "").strip()
    sub = str(attributes.get("Subcategory") or "").strip()
    category = str(attributes.get("Category") or "").strip()

    kind = sub if sub.casefold() not in UNKNOWN else category

    parts = [
        brand,
        color if color.casefold() not in UNKNOWN else None,
        kind if kind.casefold() not in UNKNOWN else None
    ]

    return " ".join(p for p in parts if p) or "Clothing item"


def saved_name(value, attributes, brand=None):
    return (
        (value or "").strip()
        or automatic_name(attributes, brand)
    )
