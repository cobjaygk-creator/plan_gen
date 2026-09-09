from datetime import date

from bs4 import BeautifulSoup

from app.event_bench.nexon_sample import (
    _date_parts_md,
    _event_format,
    _extract_balanced_array,
    _headers_for,
    _is_gersang_excluded,
    _parse_cashshop_date,
    _parse_eternalreturn_dates,
    _parse_lod_date_range,
    _parse_thefinals_threads,
    _thefinals_slug,
)


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


def test_is_gersang_excluded_filters_winner_shipping_address_notice():
    # 명시적 요청: "당첨자 배송지" 문구가 들어간 안내글은 이벤트 참여글이
    # 아니라 이미 끝난 이벤트의 사무 공지라 수집에서 뺀다.
    assert _is_gersang_excluded("<2026 추석맞이 이벤트> 당첨자 배송지 입력") is True


def test_is_gersang_excluded_keeps_normal_event_titles():
    assert _is_gersang_excluded("천하제일 낚시 대회!") is False


def test_parse_lod_date_range_with_explicit_end():
    assert _parse_lod_date_range("2026.08.20. 08:00 ~ 2026.09.17. 08:00") == ("2026-08-20", "2026-09-17")


def test_parse_lod_date_range_permanent_event():
    assert _parse_lod_date_range("2024.05.30. 12:30 ~ 상시") == ("2024-05-30", None)


def test_parse_lod_date_range_returns_none_when_unmatched():
    assert _parse_lod_date_range("날짜 정보 없음") == (None, None)


def test_parse_eternalreturn_dates_with_korean_range():
    text = "2026년 9월 3일(목) 점검 종료 후 ~  2026년 9월 17일(목) 점검 전까지"
    assert _parse_eternalreturn_dates(text) == ("2026-09-03", "2026-09-17")


def test_parse_eternalreturn_dates_with_single_dot_date():
    assert _parse_eternalreturn_dates("2026.08.06 OPEN") == ("2026-08-06", None)


def test_parse_eternalreturn_dates_returns_none_for_non_date_copy():
    assert _parse_eternalreturn_dates("나만의 캐릭터를 만들어보세요!") == (None, None)


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


def test_thefinals_slug_matches_real_site_convention():
    # 실측: "더 파이널스 2주년 & TFNL 그랜드 파이널 현장 이벤트 안내" ->
    # "더-파이널스-2주년-tfnl-그랜드-파이널-현장-이벤트-안내" (사이트가 실제
    # 쓰는 슬러그). "&"는 제거되고 공백은 하이픈으로, 영문은 소문자로.
    assert _thefinals_slug("더 파이널스 2주년 & TFNL 그랜드 파이널 현장 이벤트 안내") == (
        "더-파이널스-2주년-tfnl-그랜드-파이널-현장-이벤트-안내"
    )


def test_extract_balanced_array_ignores_brackets_inside_string_values():
    # summary 값 자체가 "[사전 참가 신청 바로가기]"처럼 대괄호를 포함할 수
    # 있다 — 순진하게 문자열 안까지 세면 배열이 값 중간에서 잘린다.
    text = '"threads":[{"summary":"[사전 참가 신청 바로가기]","id":1}],"pagingIndex":1'
    idx = text.find("[")
    extracted = _extract_balanced_array(text, idx)
    assert extracted == '[{"summary":"[사전 참가 신청 바로가기]","id":1}]'


def test_parse_thefinals_threads_extracts_thread_list_from_hydration_payload():
    page_html = (
        '<script>window.__RQ = window.__RQ || [];'
        'window.__RQ.push({"queries":[{"state":{"data":{"pages":[{"res":'
        '{"threads":[{"threadId":"1","title":"A"},{"threadId":"2","title":"B"}]}'
        '}]}}}]});</script>'
    )
    threads = _parse_thefinals_threads(page_html)
    assert [t["threadId"] for t in threads] == ["1", "2"]


def test_parse_thefinals_threads_returns_empty_list_when_marker_missing():
    assert _parse_thefinals_threads("<html>no data here</html>") == []


def test_headers_for_uses_browser_ua_for_tr_rhaon():
    # tr.rhaon.co.kr(테일즈런너)이 운영 서버(오라클 클라우드 IP)에서만
    # 2026-08-24 이후 계속 막히는 게 확인돼서 mabinogi와 같은 처방을
    # 적용했다 — 범용 UA가 아니라 실브라우저 UA로 요청해야 한다.
    headers = _headers_for("https://tr.rhaon.co.kr/eventb/event/SNB")
    assert "Chrome" in headers["User-Agent"]
    assert headers["Referer"] == "https://tr.rhaon.co.kr/"


def test_headers_for_uses_browser_ua_for_mabinogi():
    headers = _headers_for("https://mabinogi.nexon.com/page/news/event_list.asp")
    assert "Chrome" in headers["User-Agent"]
    assert headers["Referer"] == "https://mabinogi.nexon.com/"


def test_headers_for_uses_generic_ua_for_other_sources():
    headers = _headers_for("https://fconline.nexon.com/news/events")
    assert headers["User-Agent"] == "Mozilla/5.0 (compatible; EventBenchSample/0.1)"
    assert "Referer" not in headers
