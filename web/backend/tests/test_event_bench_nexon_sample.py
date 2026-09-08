from datetime import date

from bs4 import BeautifulSoup

from app.event_bench.nexon_sample import _date_parts_md, _event_format, _parse_cashshop_date


def test_date_parts_md_parses_month_day_range_within_same_year():
    starts, ends = _date_parts_md("9/3 점검 후 ~ 9/22 점검 전", reference=date(2026, 9, 7))
    assert (starts, ends) == ("2026-09-03", "2026-09-22")


def test_date_parts_md_handles_time_of_day_suffix():
    # "9/30 23:59"처럼 종료일에 시:분이 붙는 형식도 있다.
    starts, ends = _date_parts_md("9/3 점검 후 ~ 9/30 23:59", reference=date(2026, 9, 7))
    assert (starts, ends) == ("2026-09-03", "2026-09-30")


def test_date_parts_md_rolls_over_new_year_when_date_would_be_in_the_past():
    # 오늘이 12월 말인데 범위가 "1/2 ~ 1/10"이면, 그 1월은 이미 지난 올해가
    # 아니라 다음 해다 — 이벤트 목록은 항상 진행/예정 캠페인만 보여준다.
    starts, ends = _date_parts_md("1/2 점검 후 ~ 1/10 점검 전", reference=date(2026, 12, 28))
    assert (starts, ends) == ("2027-01-02", "2027-01-10")


def test_date_parts_md_returns_none_when_no_range_present():
    assert _date_parts_md("상시 진행") == (None, None)


def test_event_format_marks_cyphers_dedicated_landing_page_as_full_page():
    assert _event_format("https://cyphers.nexon.com/pages/events/welcome") == "full_page"
    assert _event_format("https://cyphers.nexon.com/pages/events/contest/2026") == "full_page"


def test_event_format_marks_cyphers_board_post_as_board():
    assert _event_format("https://cyphers.nexon.com/article/event/topic/28611384") == "board"


def _cashshop_date_node(html: str):
    return BeautifulSoup(html, "html.parser").select_one("dd.date p")


def test_parse_cashshop_date_combines_year_span_and_month_day_text():
    node = _cashshop_date_node('<dd class="date"><p><span>2026</span>08-27</p></dd>')
    assert _parse_cashshop_date(node) == date(2026, 8, 27)


def test_parse_cashshop_date_returns_none_for_missing_node():
    assert _parse_cashshop_date(None) is None


def test_parse_cashshop_date_returns_none_when_year_span_missing():
    node = _cashshop_date_node('<dd class="date"><p>08-27</p></dd>')
    assert _parse_cashshop_date(node) is None
