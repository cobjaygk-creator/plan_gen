"""Final step: write the block engine's Placement coordinates (step 3) and
the fixed fields (step 5) out as a real .pptx file. Everything upstream of
this module only ever computed layout math or classified text — this is
the one place that actually touches python-pptx shape-creation calls.

Deliberately does not try to pixel-match the original master template's
exact XML styling (theme colors, precise borders) — that's excess
precision for what the block engine/regression scorer actually check
(text present, image present, no overlap). Uses the confirmed values from
master_template.md (slide size, body font, content box) and otherwise
keeps shapes plain.
"""
import os
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

from tools.blocks.geometry import Placement

SLIDE_WIDTH_PT = 960
SLIDE_HEIGHT_PT = 540
BODY_FONT = "맑은 고딕"

PLACEHOLDER_FILL = RGBColor(0xE7, 0xE6, 0xE6)  # theme lt2
PLACEHOLDER_LINE = RGBColor(0xA5, 0xA5, 0xA5)  # theme accent3
BADGE_FILL = RGBColor(0xFF, 0x00, 0x00)


def _item_name(ref) -> str:
    if isinstance(ref, dict):
        return ref.get("name", "")
    return str(ref) if ref is not None else ""


def _add_placement(slide, placement: Placement):
    left, top = Pt(placement.left), Pt(placement.top)
    width, height = Pt(placement.width), Pt(placement.height)

    if placement.kind in ("icon", "image"):
        image_path = placement.ref.get("image") if isinstance(placement.ref, dict) else None
        if image_path and os.path.exists(image_path):
            slide.shapes.add_picture(image_path, left, top, width, height)
            return
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
        box.fill.solid()
        box.fill.fore_color.rgb = PLACEHOLDER_FILL
        box.line.color.rgb = PLACEHOLDER_LINE
        tf = box.text_frame
        tf.word_wrap = True
        tf.text = _item_name(placement.ref)[:24]
        p = tf.paragraphs[0]
        p.font.size = Pt(6)
        p.font.name = BODY_FONT
        return

    if placement.kind == "badge":
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        box.fill.solid()
        box.fill.fore_color.rgb = BADGE_FILL
        tf = box.text_frame
        tf.text = _item_name(placement.ref) or "NEW"
        p = tf.paragraphs[0]
        p.font.size = Pt(7)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        p.font.name = BODY_FONT
        return

    # caption / text
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = _item_name(placement.ref)
    p = tf.paragraphs[0]
    p.font.size = Pt(8)
    p.font.name = BODY_FONT


def _add_section_header(slide, text: str):
    tb = slide.shapes.add_textbox(Pt(20), Pt(20), Pt(600), Pt(30))
    tf = tb.text_frame
    tf.text = text
    p = tf.paragraphs[0]
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.name = BODY_FONT


def _add_fixed_fields_slide(prs, blank_layout, fixed: dict):
    slide = prs.slides.add_slide(blank_layout)
    y = Pt(20)
    for line in fixed["title_lines"]:
        tb = slide.shapes.add_textbox(Pt(20), y, Pt(600), Pt(28))
        tb.text_frame.text = line
        tb.text_frame.paragraphs[0].font.size = Pt(20)
        tb.text_frame.paragraphs[0].font.bold = True
        tb.text_frame.paragraphs[0].font.name = BODY_FONT
        y += Pt(30)

    tb = slide.shapes.add_textbox(Pt(20), y, Pt(600), Pt(20))
    tb.text_frame.text = fixed["period"]
    tb.text_frame.paragraphs[0].font.size = Pt(11)
    tb.text_frame.paragraphs[0].font.name = BODY_FONT
    y += Pt(30)

    grade = fixed["grade_table"]
    rows, cols = 2, len(grade["tiers"])
    table_shape = slide.shapes.add_table(rows, cols, Pt(20), y, Pt(400), Pt(50))
    table = table_shape.table
    for c, tier in enumerate(grade["tiers"]):
        table.cell(0, c).text = tier
        table.cell(1, c).text = grade["prices"][c]


def _add_notices_slide(prs, blank_layout, fixed: dict):
    if not fixed["notices"]:
        return
    slide = prs.slides.add_slide(blank_layout)
    _add_section_header(slide, "유의사항")
    y = Pt(60)
    for line in fixed["notices"]:
        tb = slide.shapes.add_textbox(Pt(20), y, Pt(880), Pt(20))
        tb.text_frame.text = line
        tb.text_frame.paragraphs[0].font.size = Pt(10)
        tb.text_frame.paragraphs[0].font.name = BODY_FONT
        y += Pt(22)


def render_pptx(fixed: dict, month_result, out_path: str) -> str:
    """fixed: parse_fixed_fields() output. month_result: pipeline.MonthResult
    (sections with .pages already computed — this function does no
    classification/matching itself, just draws what it's given)."""
    prs = Presentation()
    prs.slide_width = Pt(SLIDE_WIDTH_PT)
    prs.slide_height = Pt(SLIDE_HEIGHT_PT)
    blank_layout = prs.slide_layouts[6]

    _add_fixed_fields_slide(prs, blank_layout, fixed)

    for section in month_result.sections:
        if section.render_error:
            continue
        for page in section.pages:
            slide = prs.slides.add_slide(blank_layout)
            _add_section_header(slide, section.title)
            for placement in page:
                _add_placement(slide, placement)

    _add_notices_slide(prs, blank_layout, fixed)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    prs.save(out_path)
    return out_path
