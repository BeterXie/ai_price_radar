"""Build the same classification inputs for admin repair and repair previews."""
from __future__ import annotations

from .classifier import Classification, classify_product


def classify_offer(offer) -> Classification:
    raw = offer.raw_product
    source_platform = str(offer.shop.platform or "")
    raw_json = raw.raw_json if isinstance(raw.raw_json, dict) else {}
    categories = [raw.original_category]
    descriptions = [raw_json.get("description", "")]
    if source_platform.strip().casefold() == "16688":
        category = raw_json.get("sourceCategory") or raw_json.get("source_category")
        categories.append(category.get("name", "") if isinstance(category, dict) else category)
        descriptions.extend(raw_json.get(key, "") for key in ("content", "instruction", "remark"))
    return classify_product(
        raw.original_name,
        " ".join(str(value or "") for value in categories),
        " ".join(str(value or "") for value in descriptions),
        source_platform=source_platform,
        price=offer.price,
    )
