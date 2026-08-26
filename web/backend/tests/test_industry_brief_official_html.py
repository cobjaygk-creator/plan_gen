from app.industry_brief.official_html import (
    NAVER_SECTION_SOURCES,
    OFFICIAL_HTML_SOURCES,
    _parse_kocca,
    _parse_mcst,
    _parse_korea_policy,
    _parse_grac,
    _parse_krafton,
    _parse_nexon_games,
    _parse_netmarble,
    _mcst_pdf_url,
    _page_url,
    collect_official_html,
    collect_naver_section,
)
from app.industry_brief.models import Article


def test_kocca_parser_keeps_game_policy_and_filters_unrelated_content():
    html = """
    <div class="board_list03"><ul>
      <li><a href="/kocca/koccanews/reportview.do?nttNo=1"><div class="txt_wrap">
        <div class="title">K-인디게임 해외 진출 지원</div>
        <div class="txt"><span>국내 게임기업의 경쟁력을 강화한다.</span></div>
        <div class="info"><p>발간일 : 2026-08-13</p></div>
      </div></a></li>
      <li><a href="/fashion"><div class="txt_wrap">
        <div class="title">K-패션 전시 개최</div><div class="txt"><span>패션 소식</span></div>
      </div></a></li>
    </ul></div>
    """
    entries = _parse_kocca(html, "https://www.kocca.kr/list")
    assert len(entries) == 1
    assert entries[0]["title"] == "K-인디게임 해외 진출 지원"
    assert entries[0]["published_at"].date().isoformat() == "2026-08-13"


def test_mcst_parser_reads_title_date_and_filters_unrelated_content():
    html = """
    <table><tr><td><a href="pressView.jsp?pSeq=10" title="게임산업 진흥 정책 발표">기사</a></td>
      <td aria-label="게시일">2026.08.14.</td></tr>
    <tr><td><a href="pressView.jsp?pSeq=11" title="한복 전시 개최">기사</a></td>
      <td aria-label="게시일">2026.08.14.</td></tr></table>
    """
    entries = _parse_mcst(html, "https://www.mcst.go.kr/site/s_notice/press/pressList.jsp")
    assert len(entries) == 1
    assert entries[0]["url"].endswith("pressView.jsp?pSeq=10")


def test_korea_policy_parser_keeps_relevant_other_ministry_and_skips_mcst():
    html = """
    <ul>
      <li><a href="/briefing/pressReleaseView.do?newsId=1"><span class="text">
        <strong>생성형 AI 보안 가이드라인 시행</strong>
        <span class="lead">인공지능 서비스의 안전 기준을 마련한다.</span>
        <span class="source"><span>2026.08.18</span><span>과학기술정보통신부</span></span>
      </span></a></li>
      <li><a href="/briefing/pressReleaseView.do?newsId=2"><span class="text">
        <strong>게임산업 지원 정책 발표</strong><span class="lead">게임 기업 지원</span>
        <span class="source"><span>2026.08.18</span><span>문화체육관광부</span></span>
      </span></a></li>
      <li><a href="/briefing/pressReleaseView.do?newsId=3"><span class="text">
        <strong>농산물 유통 개선</strong><span class="lead">농업 소식</span>
        <span class="source"><span>2026.08.18</span><span>농림축산식품부</span></span>
      </span></a></li>
      <li><a href="/briefing/pressReleaseView.do?newsId=4"><span class="text">
        <strong>일반 산업 정책 발표</strong><span class="lead">본문에서 AI를 참고 사례로 언급한다.</span>
        <span class="source"><span>2026.08.18</span><span>산업통상부</span></span>
      </span></a></li>
    </ul>
    """
    entries = _parse_korea_policy(html, "https://www.korea.kr/briefing/pressReleaseList.do")
    assert len(entries) == 1
    assert entries[0]["publisher"] == "과학기술정보통신부"
    assert entries[0]["published_at"].date().isoformat() == "2026-08-18"


def test_grac_parser_keeps_policy_news_and_filters_general_activity():
    html = """
    <table>
      <tr><td>1</td><td class="subject"><a href="/Board/NewsData.aspx?type=view&amp;bno=10">
        게임위, 확률형 아이템 표시의무 위반 이용 주의</a></td>
        <td>2026-08-07</td><td>관리자</td><td>10</td></tr>
      <tr><td>2</td><td class="subject"><a href="/Board/NewsData.aspx?type=view&amp;bno=9">
        게임위, 혈액 부족 시기 단체 헌혈</a></td>
        <td>2026-08-06</td><td>관리자</td><td>10</td></tr>
    </table>
    """
    entries = _parse_grac(html, "https://www.grac.or.kr/Board/NewsData.aspx")
    assert len(entries) == 1
    assert "bno=10" in entries[0]["url"]
    assert entries[0]["published_at"].date().isoformat() == "2026-08-07"


def test_krafton_parser_reads_first_party_press_card():
    html = """
    <div class="NewsListItem">
      <a class="NewsListItem-link" href="/news/press/project-nova/">
        <div class="NewsListItem-content">
          <span class="category">게임</span>
          <h3 class="title"><span>크래프톤, 프로젝트 노바 공개</span></h3>
          <span class="date">2026. 08. 18</span>
          <p class="NewsListItem-text">신규 게임의 핵심 플레이를 공개했다.</p>
        </div>
      </a>
    </div>
    """
    entries = _parse_krafton(html, "https://www.krafton.com/news/press/")
    assert entries == [{
        "title": "크래프톤, 프로젝트 노바 공개",
        "url": "https://www.krafton.com/news/press/project-nova/",
        "summary": "신규 게임의 핵심 플레이를 공개했다.",
        "published_at": entries[0]["published_at"],
    }]
    assert entries[0]["published_at"].date().isoformat() == "2026-08-18"


def test_nexon_games_parser_reads_official_press_card():
    html = """
    <li class="gall_li"><span class="wr_date">2026.08.14</span>
      <a class="bo_tit" href="/bbs/board.php?bo_table=media_event&amp;wr_id=507&amp;page=1">
        넥슨, 서든어택 신규 전장 업데이트
      </a>
    </li>
    """
    entries = _parse_nexon_games(
        html, "https://www.nexongames.co.kr/bbs/board.php?bo_table=media_event&page=1"
    )
    assert entries[0]["title"] == "넥슨, 서든어택 신규 전장 업데이트"
    assert "wr_id=507" in entries[0]["url"]
    assert entries[0]["published_at"].date().isoformat() == "2026-08-14"


def test_netmarble_parser_builds_verified_detail_url():
    html = """
    <li class="list_item"><div class="cont_b">
      <a onclick="ContentsClickEvent('user', '1014', '6937', '게임')">
        <p class="title">넷마블, 신규 캐릭터 업데이트</p>
      </a>
      <div class="date">2026.08.07</div>
    </div></li>
    """
    entries = _parse_netmarble(html, "https://ch.netmarble.com/Newsroom/PressRelease/List")
    assert entries[0]["url"] == (
        "https://ch.netmarble.com/Newsroom/PressRelease/Detail"
        "?bbs_code=1014&post_seq=6937"
    )
    assert entries[0]["published_at"].date().isoformat() == "2026-08-07"


def test_official_collector_stores_and_deduplicates(db_factory, monkeypatch):
    db = db_factory()
    html = """
    <table><tr><td><a href="pressView.jsp?pSeq=10" title="이스포츠 지원 정책">기사</a></td>
      <td aria-label="게시일">2026.08.14.</td></tr></table>
    """
    monkeypatch.setattr("app.industry_brief.official_html._fetch_html", lambda _: html)
    monkeypatch.setattr(
        "app.industry_brief.official_html._fetch_mcst_summary",
        lambda _: "정부는 게임산업 지원 정책을 9월부터 시행한다.",
    )
    source = OFFICIAL_HTML_SOURCES[1]
    first = collect_official_html(db, source)
    second = collect_official_html(db, source)
    assert first.new == 1
    assert second.duplicates == 1
    stored = db.query(Article).one()
    assert stored.source_type == "official"
    assert stored.source == "문화체육관광부"
    assert "9월부터 시행" in stored.summary


def test_mcst_pdf_download_url_uses_verified_official_endpoint():
    html = """
    <div class="add_file">
      <div class="down_file pdf_down">보도자료.pdf</div>
      <a href="#" onclick="file_download('%EB%B3%B4%EB%8F%84.pdf', 'saved.pdf', '0302000000');return false;">내려받기</a>
    </div>
    """
    url = _mcst_pdf_url(html, "https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pSeq=1")
    assert url.startswith(
        "https://www.mcst.go.kr/servlets/eduport/front/upload/UplDownloadFile?"
    )
    assert "pRealName=saved.pdf" in url


def test_verified_page_urls_keep_required_menu_parameters():
    assert _page_url(OFFICIAL_HTML_SOURCES[0], 2).endswith("menuNo=204767&pageIndex=2")
    assert _page_url(OFFICIAL_HTML_SOURCES[1], 3).endswith("pCurrentPage=3")
    assert "pageIndex=4" in _page_url(OFFICIAL_HTML_SOURCES[2], 4)
    assert _page_url(OFFICIAL_HTML_SOURCES[3], 0).endswith("pageindex=0")
    assert _page_url(OFFICIAL_HTML_SOURCES[4], 2).endswith("var_page=2")
    assert "bo_table=media_event&page=2" in _page_url(OFFICIAL_HTML_SOURCES[5], 2)


def test_official_collector_backfills_existing_mcst_summary(db_factory, monkeypatch):
    db = db_factory()
    url = "https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pSeq=10"
    db.add(Article(
        source="문화체육관광부",
        source_type="official",
        category="GAME",
        title="게임산업 진흥 정책 발표",
        url=url,
        summary=None,
    ))
    db.commit()
    html = """
    <table><tr><td><a href="pressView.jsp?pSeq=10" title="게임산업 진흥 정책 발표">기사</a></td>
      <td aria-label="게시일">2026.08.14.</td></tr></table>
    """
    monkeypatch.setattr("app.industry_brief.official_html._fetch_html", lambda _: html)
    monkeypatch.setattr(
        "app.industry_brief.official_html._fetch_mcst_summary",
        lambda _: "정책 대상과 시행 시점이 포함된 공식 보도자료 본문 " * 20,
    )
    result = collect_official_html(db, OFFICIAL_HTML_SOURCES[1])
    assert result.duplicates == 1
    assert len(db.query(Article).one().summary) >= 500


def test_naver_section_dedups_a_url_repeated_within_the_same_fetch(db_factory, monkeypatch):
    # Naver's own listing repeats an entry (e.g. a "Hot" pick also shown in
    # the regular list) within a single page fetch — this must not hit the
    # url column's unique constraint when both rows are new in this run.
    db = db_factory()
    html = """
    <ul>
      <li class="sa_item">
        <a class="sa_text_title" href="https://n.news.naver.com/mnews/article/000/0000001">
          <strong class="sa_text_strong">중복되는 기사 제목</strong>
        </a>
        <div class="sa_text_lede">요약문</div>
        <div class="sa_text_press">테스트언론사</div>
        <div class="sa_text_datetime">1시간전</div>
      </li>
      <li class="sa_item">
        <a class="sa_text_title" href="https://n.news.naver.com/mnews/article/000/0000001">
          <strong class="sa_text_strong">중복되는 기사 제목</strong>
        </a>
        <div class="sa_text_lede">요약문</div>
        <div class="sa_text_press">테스트언론사</div>
        <div class="sa_text_datetime">1시간전</div>
      </li>
    </ul>
    """
    monkeypatch.setattr("app.industry_brief.official_html._fetch_html", lambda _: html)
    result = collect_naver_section(db, NAVER_SECTION_SOURCES[0])
    assert result.new == 1
    assert result.duplicates == 1
    assert db.query(Article).count() == 1
