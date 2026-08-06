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

Image quality (user decision): PPT images are a reference/preview for the
designer, not a final asset — "구분만 되면 충분" (just needs to be
recognizable). Do NOT add quality validation, minimum-resolution checks,
or upscaling here or in the renderer. Just return whatever the repository
has as-is; the renderer resizes to fit the card box (design principle:
no work an image consumer doesn't need). Same applies to any future 3.3
AI-vision fallback thumbnails — no quality gate there either.
"""


def lookup_image_by_name(item_name: str) -> str | None:
    """Return a local/resolvable image path for item_name, or None if no
    asset repository is configured (current default) or the name isn't
    found in it."""
    return None
