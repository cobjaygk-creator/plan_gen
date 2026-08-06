"""Interface stub for an item-name/ID-keyed image asset repository.

Status: UNCONFIRMED whether this repository exists (design doc open
question 9.1). Until confirmed, lookup_image_by_name() always returns
None — every item without a position-matched image in the request.xlsx
simply stays text-only (no image), which is a valid and expected state,
not an error.

When the repository is confirmed, implement the lookup here (e.g. a
network path glob, an S3/DB query, whatever it turns out to be) without
touching match_images.py — it already calls this function as its second-
pass fallback after position-matching.
"""


def lookup_image_by_name(item_name: str) -> str | None:
    """Return a local/resolvable image path for item_name, or None if no
    asset repository is configured (current default) or the name isn't
    found in it."""
    return None
