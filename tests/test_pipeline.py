import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.classification_schema import ClassificationOutput, Section, Item
from tools.classify_month import ClassifyResult
from tools.locate_items import LocatedItem
from tools import pipeline

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def _fake_classify(month, raw_text, **kwargs):
    output = ClassificationOutput(sections=[
        Section(section_title="기간제 패키지", block_type="grid",
                items=[Item(name="[이벤트] 고대의 서 30일 상자"), Item(name="[이벤트] 세레스의 가호 습득서"),
                       Item(name="그림자 스킨(30일) 교환권"), Item(name="길드의 가호 습득서(기간제)"),
                       Item(name="[이벤트] 피크닉 타이틀 습득서 (30일)"), Item(name="헌터의 힘 스킬 습득서 (30일)")],
                footnote="(구성품)", confidence=0.95),
    ])
    return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)


def test_process_month_renders_grid_section_end_to_end(tmp_path):
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert result.needs_human_review is None
    assert result.fatal_error is None
    assert len(result.sections) == 1
    section = result.sections[0]
    assert section.render_error is None
    assert section.item_count == 6
    assert len(section.pages) >= 1
    summary = pipeline.summarize(result)
    assert "[OK]" in summary or "[OVERLAP]" in summary


def test_process_month_records_render_error_without_crashing(tmp_path):
    def fake_classify_bad_paired(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="이상한 섹션", block_type="paired_columns",
                    items=[Item(name="아이템 하나뿐")], footnote=None, confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_bad_paired):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert len(result.sections) == 1
    assert result.sections[0].render_error is not None  # paired_columns needs exactly 2
    summary = pipeline.summarize(result)
    assert "[ERROR]" in summary


def test_process_month_propagates_needs_human_review(tmp_path):
    from tools.classify_month import NeedsHumanReview

    def fake_classify_raises(month, raw_text, **kwargs):
        raise NeedsHumanReview(month, "confidence too low", raw_text)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_raises):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))

    assert result.needs_human_review is not None
    assert "202605" in pipeline.summarize(result)


def test_process_month_icon_only_finds_real_image_by_row_range(tmp_path):
    # Real 202602 case: "[이벤트] 고양이 모자 선택권" (title row 40, footnote
    # row 41) has zero item names — 9 cat-hat icons are one combined image
    # anchored to rows 42-50 with no cell text at all. icon_only sections
    # skip the usual AI-name -> locate -> match flow entirely (there are no
    # names to locate); process_month must instead find that image by
    # scanning the section's own row range directly.
    def fake_classify_icon_only(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="[이벤트] 고양이 모자 선택권", block_type="icon_only",
                    items=[], footnote="(교환 리스트 중 택1)", confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_icon_only):
        path = os.path.join(SAMPLES_DIR, "202602_request.xlsx")
        result = pipeline.process_month("202602", path, image_out_dir=str(tmp_path))

    assert len(result.sections) == 1
    section = result.sections[0]
    assert section.render_error is None
    assert section.item_count == 1  # the 9 icons are one combined image file
    assert len(section.items) == 1
    assert section.items[0]["image"] is not None
    assert os.path.exists(section.items[0]["image"])
    assert len(section.pages) == 1
    assert len(section.pages[0]) == 1  # one "icon" placement, no caption
    assert section.pages[0][0].kind == "icon"


def test_process_month_icon_only_excludes_title_adjacent_decoration_202508(tmp_path):
    # Real bug (user-reported, screenshots + real file): if "배틀패스 의상
    # 교환권" is ever misclassified as icon_only again (the actual trigger
    # was a separate text-extraction bug, already fixed in
    # extract_special_reward.py — this test guards the icon_only fallback
    # itself as defense in depth), the row-range image sweep used to grab
    # the "WEAR" exchange-ticket badge anchored right on the section's own
    # title row (17-18, title_row=17) as if it were a content item. A real
    # content icon (202602's cat-hat icons, see the test above) always
    # starts strictly after its title row — this is a structural,
    # zero-AI-cost rule, not a vision judgment call.
    def fake_classify_icon_only(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="배틀패스 의상 교환권", block_type="icon_only",
                    items=[], footnote="아래 패션 세트 중 택 1 (거래 불가)", confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_icon_only):
        path = os.path.join(SAMPLES_DIR, "202508_request.xlsx")
        result = pipeline.process_month("202508", path, image_out_dir=str(tmp_path))

    section = result.sections[0]
    assert section.render_error is None
    image_paths = [item["image"] for item in section.items if item["image"]]
    assert image_paths  # sanity: real content icons past the title row are still found
    assert not any(os.path.basename(p).startswith("rId1.") for p in image_paths), (
        "the title-adjacent WEAR badge (rId1) was swept in as a content item"
    )


def test_process_month_icon_only_does_not_steal_images_from_next_section(tmp_path):
    # Real bug (user-reported, downloaded .pptx): 202509's "할로윈 호박
    # 동작 선택 상자" is an empty icon_only section immediately followed
    # by a real few_preview section ("할로윈 펌킨 버킷 등록권") whose 2
    # portraits anchor at rows 36-50 — starting inside the icon_only run
    # (34-49) but ending at the few_preview items' own row 50. A
    # partial-overlap row-range test let icon_only grab both portraits
    # too, so the same 2 images appeared twice in the rendered deck under
    # two different captions. icon_only must only take images that fit
    # *entirely* within its own row range.
    def fake_classify(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="할로윈 호박 동작 선택 상자", block_type="icon_only",
                    items=[], footnote="아래 동작 꾸미기 중 택 1 (거래 불가)", confidence=0.9),
            Section(section_title="할로윈 펌킨 버킷 등록권", block_type="few_preview", items=[
                Item(name="할로윈 펌킨 버킷 등록권"), Item(name="할로윈 잭 오 랜턴 등록권"),
            ], footnote=None, confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify):
        path = os.path.join(SAMPLES_DIR, "202509_request.xlsx")
        result = pipeline.process_month("202509", path, image_out_dir=str(tmp_path))

    icon_only_section, few_preview_section = result.sections
    assert icon_only_section.render_error is not None  # legitimately 0 images of its own
    assert len(icon_only_section.items) == 0

    few_preview_images = [i["image"] for i in few_preview_section.items if i["image"]]
    assert len(few_preview_images) == 2
    assert len(set(few_preview_images)) == 2  # the two items must not share one image


def test_process_month_paired_columns_matches_set_names_not_sub_items(tmp_path):
    # Real 202606 bug: "자켓 세트"/"치마 세트" portraits are anchored at
    # column C/D while their own text sits in column B/D — outside
    # match_images' default col_tolerance=0. Widening tolerance blindly
    # would let a sub-item (whose row sits exactly inside the portrait
    # anchor's row span, distance 0) win the anchor away from the actual
    # set name (row 18, distance >0) via the nearest-first tiebreak.
    # process_month must exclude sub-items from paired_columns matching
    # entirely so only the 2 set-name items ever compete for portraits.
    def fake_classify_202606(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="배틀패스 신규 의상", block_type="paired_columns", items=[
                Item(name="20th 파티 자켓 세트", pair_group=None),
                Item(name="20th 파티 치마 세트", pair_group=None),
                Item(name="20th 파티 연미복", pair_group=0),
                Item(name="20th 파티 흰꽃 머리띠", pair_group=1),
            ], footnote="* 각주", confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_202606):
        path = os.path.join(SAMPLES_DIR, "202606_request.xlsx")
        result = pipeline.process_month("202606", path, image_out_dir=str(tmp_path))

    section = result.sections[0]
    assert section.render_error is None
    items_by_name = {i["name"]: i for i in section.items}
    assert items_by_name["20th 파티 자켓 세트"]["image"] is not None
    assert items_by_name["20th 파티 치마 세트"]["image"] is not None
    # sub-items must never receive an image even though match_images would
    # gladly hand one to them if they were left in the matching pool
    assert items_by_name["20th 파티 연미복"]["image"] is None
    assert items_by_name["20th 파티 흰꽃 머리띠"]["image"] is None


def test_process_month_reports_progress_through_all_3_stages(tmp_path):
    # web/backend's SSE progress stream depends on these exact 3 calls in
    # order — 4 is reported separately by whoever calls render_from_template()
    calls = []
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        pipeline.process_month(
            "202605", path, image_out_dir=str(tmp_path),
            on_progress=lambda step, msg: calls.append((step, msg)),
        )

    assert [c[0] for c in calls] == [1, 2, 3]
    assert all(isinstance(c[1], str) and c[1] for c in calls)


def test_process_month_works_without_on_progress_callback(tmp_path):
    # on_progress is optional — must not require passing a no-op lambda
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path, image_out_dir=str(tmp_path))
    assert result.needs_human_review is None


def test_process_month_defaults_to_real_local_image_paths():
    # Regression: omitting image_out_dir used to leave in-archive paths
    # (e.g. "xl/media/image8.PNG") on matched items, which render_pptx.py's
    # os.path.exists() check silently treats as "no image" — a fully-
    # matched section could render with zero pictures and no error at all.
    with patch("tools.pipeline.classify_month", side_effect=_fake_classify):
        path = os.path.join(SAMPLES_DIR, "202605_request.xlsx")
        result = pipeline.process_month("202605", path)  # no image_out_dir

    section = result.sections[0]
    for page in section.pages:
        for placement in page:
            if placement.kind == "icon" and isinstance(placement.ref, dict):
                image_path = placement.ref.get("image")
                if image_path:
                    assert os.path.exists(image_path), f"matched image path is not a real file: {image_path}"


def test_process_month_icon_only_filters_decorative_badge_202512(tmp_path):
    # Real user-reported bug (screenshots + web-generated 202512 output):
    # "신규 배틀패스 헤어 출시" is icon_only with no item names, and its
    # image-only row range (57-66) anchors BOTH the real two-pose character
    # photo (rId12) AND a decorative PASS-ribbon badge (rId13) with no
    # title-row adjacency to structurally exclude it by (unlike the 202508
    # WEAR-badge case). Confirmed on the actual file: without the vision
    # filter, both images rendered as separate cards.
    from tools.vision_match import IconFilterResult

    def fake_classify_icon_only(month, raw_text, **kwargs):
        output = ClassificationOutput(sections=[
            Section(section_title="신규 배틀패스 헤어 출시", block_type="icon_only", items=[],
                    footnote="배틀패스 쿠폰을 통해         '[이벤트] 배틀패스 머리모양 영구 변경권' 획득 가능",
                    confidence=0.9),
        ])
        return ClassifyResult(month, output, "claude-haiku-4-5-20251001", from_cache=False)

    def fake_filter(images):
        # real content is always listed first by row order (rId12 before
        # rId13) in _icon_only_items' anchor scan
        assert len(images) == 2
        return [0]

    with patch("tools.pipeline.classify_month", side_effect=fake_classify_icon_only), \
         patch("tools.pipeline.filter_decorative_icons", side_effect=fake_filter) as filter_mock:
        path = os.path.join(SAMPLES_DIR, "202512_request.xlsx")
        result = pipeline.process_month("202512", path, image_out_dir=str(tmp_path))

    filter_mock.assert_called_once()
    section = result.sections[0]
    assert section.render_error is None
    assert len(section.items) == 1
    assert os.path.basename(section.items[0]["image"]).startswith("rId12")
