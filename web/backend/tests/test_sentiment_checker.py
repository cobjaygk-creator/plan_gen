from datetime import datetime,timezone
from bs4 import BeautifulSoup
from app.sentiment_checker.models import SentimentPost,SentimentComment
from app.sentiment_checker.clustering import cluster_posts
from app.sentiment_checker import collector,comment_collector,service

def post(post_id,issue,keywords="[]"):
 return SentimentPost(source="DCINSIDE",post_id=post_id,title=issue,url=f"https://example.com/{post_id}",created_at=datetime.now(timezone.utc),category="BUG",sentiment="NEGATIVE",sentiment_value=-1,score_eligible=True,issue_key=f"AI:{issue}",keywords=keywords)

def test_similar_ai_issue_names_cluster():
 a=post("1","\uc11c\ubc84 \uc811\uc18d \uc624\ub958",'["\uc11c\ubc84", "\uc811\uc18d"]')
 b=post("2","\uc811\uc18d \uc11c\ubc84 \uc624\ub958",'["\uc11c\ubc84", "\uc811\uc18d"]')
 assert len(cluster_posts([a,b]))==1

def test_dashboard_route_returns_sentiment_shape(client,make_user,db_factory):
 make_user(email="sentiment@example.com",password="hunter2")
 assert client.post("/auth/login",json={"email":"sentiment@example.com","password":"hunter2"}).status_code==200
 db=db_factory();db.add(post("10","\uc11c\ubc84 \uc811\uc18d \uc624\ub958"));db.commit();db.close()
 res=client.get("/sentiment-checker/dashboard?hours=24")
 assert res.status_code==200
 body=res.json()
 assert body["metrics"]["collected"]==1
 assert body["issues"][0]["title"]=="\uc11c\ubc84 \uc811\uc18d \uc624\ub958"
 assert "timeline" in body and "references" in body


def test_dashboard_all_stored_fallback_is_capped(monkeypatch, db_factory):
 # 교차 확인된 이슈가 하나도 없을 때(선택 기간·최근 7일 모두 조용한 경우)
 # 이력 전체를 통째로 다시 클러스터링하면, 보관 기간이 길어질수록
 # O(n^2) 비교 비용이 한도 없이 커진다 — 최근 N건으로 상한을 두는지 확인.
 monkeypatch.setattr(service, "_ALL_STORED_FALLBACK_LIMIT", 2)
 db = db_factory()
 for i in range(5):
  db.add(post(f"old{i}", "오래된 이슈"))
 db.commit()
 old = datetime(2000, 1, 1, tzinfo=timezone.utc)
 for row in db.query(SentimentPost).all():
  row.created_at = old
 db.commit()

 result = service.dashboard(db, hours=24)

 assert result["metrics"]["stored_total"] == 5  # 전체 개수는 정확히 세되
 assert result["analysis_basis"] == "ALL_STORED"
 assert result["analysis_count"] == 2  # 클러스터링 입력은 상한만큼만


def test_issue_detail_route_returns_grounded_posts(client,make_user,db_factory):
 make_user(email="detail@example.com",password="hunter2")
 assert client.post("/auth/login",json={"email":"detail@example.com","password":"hunter2"}).status_code==200
 db=db_factory();p=post("20","\uc11c\ubc84 \uc811\uc18d \uc624\ub958",'["\uc11c\ubc84", "\uc811\uc18d"]');db.add(p);db.commit();db.refresh(p);db.add(SentimentComment(post_db_id=p.id,comment_id="c1",source="LATALE_OFFICIAL",content="\ub9de\uc544 \ub3d9\uc758\ud574",sentiment="POSITIVE",sentiment_value=1,stance="AGREE"));db.commit();db.close()
 res=client.get("/sentiment-checker/issues/detail",params={"key":"BUG:\uc11c\ubc84 \uc811\uc18d \uc624\ub958","hours":168})
 assert res.status_code==200
 body=res.json()
 assert body["mentions"]==1
 assert body["posts"][0]["title"]=="\uc11c\ubc84 \uc811\uc18d \uc624\ub958"
 assert body["sentiment"]["negative"]==100
 assert body["comment_reaction"]["agree"]==1
 assert body["comments"][0]["content"]=="\ub9de\uc544 \ub3d9\uc758\ud574"


def test_content_uses_writing_view_box_for_dcinside_and_priring(monkeypatch):
 # DCINSIDE_PRIRING(mgallery)\ub3c4 DCInside \ud50c\ub7ab\ud3fc\uc774\ub77c
 # \uac19\uc740 .writing_view_box\ub97c \uc4f4\ub2e4(\uc9c1\uc811 \ud655\uc778)
 # \u2014 DCINSIDE \ubb38\uc790\uc5f4\ub9cc \uac80\uc0ac\ud558\ub358 \uc608\uc804
 # \ucf54\ub4dc\ub294 PRIRING \ubcf8\ubb38\uc744 \ud56d\uc0c1 \ube48 \ubb38\uc790\uc5f4\ub85c \ub9cc\ub4e4\uace0 \uc788\uc5c8\ub2e4.
 html='<div class="writing_view_box">\ubcf8\ubb38 \ub0b4\uc6a9\uc785\ub2c8\ub2e4</div>'
 monkeypatch.setattr(collector,"_get",lambda url:BeautifulSoup(html,"html.parser"))
 item=collector.Candidate(source="DCINSIDE_PRIRING",post_id="1",title="t",url="https://example.com/1",created_at=None)
 assert collector._content(item)=="\ubcf8\ubb38 \ub0b4\uc6a9\uc785\ub2c8\ub2e4"


def test_collect_splits_detail_budget_across_sources(monkeypatch, db_factory):
 # \uc774\uc804\uc5d0\ub294 LATALE_OFFICIAL\ub9cc \ubcf8\ubb38\uc744 \uac00\uc838\uc624\uace0 DCInside/\ud504\ub9ac\ub9c1\uc740
 # \uc81c\ubaa9\ub9cc \uc218\uc9d1\ub418\uc5c8\ub2e4 \u2014 \uc774\uc81c\ub294 \uc18c\uc2a4\ubcc4\ub85c \uc608\uc0b0\uc744 \ub098\ub220
 # \uc138 \uc18c\uc2a4 \ubaa8\ub450 \ubcf8\ubb38\uc744 \uac00\uc838\uc628\ub2e4.
 monkeypatch.setattr(collector,"dc_candidates",lambda pages:[collector.Candidate("DCINSIDE",f"dc{i}",f"t{i}",f"https://x/dc{i}",None) for i in range(5)])
 monkeypatch.setattr(collector,"priring_candidates",lambda pages:[collector.Candidate("DCINSIDE_PRIRING",f"pr{i}",f"t{i}",f"https://x/pr{i}",None) for i in range(5)])
 monkeypatch.setattr(collector,"latale_candidates",lambda pages:[collector.Candidate("LATALE_OFFICIAL",f"of{i}",f"t{i}",f"https://x/of{i}",None) for i in range(5)])
 monkeypatch.setattr(collector,"naver_cafe_candidates",lambda pages:[])
 monkeypatch.setattr(collector,"_content",lambda item:f"content-{item.post_id}")
 monkeypatch.setattr(collector,"collect_references",lambda db,pages=2:{"found":0,"new":0,"errors":[]})

 db=db_factory()
 result=collector.collect(db,pages=1,detail_limit=6)

 posts=db.query(SentimentPost).all()
 with_content=[p for p in posts if p.content]
 by_source={}
 for p in with_content: by_source[p.source]=by_source.get(p.source,0)+1
 assert result["details"]==6
 assert by_source=={"DCINSIDE":2,"DCINSIDE_PRIRING":2,"LATALE_OFFICIAL":2}


def test_dc_comment_date_parses_month_day_and_full_date():
 assert comment_collector._dc_comment_date("2026-09-01 10:00:00") is not None
 # "MM.DD HH:MM:SS"는 KST 표기라 UTC로 변환되면서 날짜가 하루 당겨질 수
 # 있다(KST 00~09시대) — 실제로 정상 파싱됐는지만 확인한다.
 parsed=comment_collector._dc_comment_date("09.14 08:53:06")
 assert parsed is not None and parsed.tzinfo is not None


def test_collect_dc_comments_persists_and_skips_deleted(monkeypatch, db_factory):
 db=db_factory()
 post=SentimentPost(source="DCINSIDE",post_id="764997",title="t",url="https://x/1",created_at=datetime.now(timezone.utc))
 db.add(post);db.commit();db.refresh(post)

 fake_items=[
  {"no":"1","memo":"\uc88b\ub124\uc694 \uc7ac\ubc0c\uc788\uc5b4\uc694","user_id":"a","reg_date":"09.14 08:53:06","is_delete":"0","del_yn":"N"},
  {"no":"2","memo":"\uc0ad\uc81c\ub41c \ub313\uae00\uc785\ub2c8\ub2e4","user_id":"b","reg_date":"09.14 09:00:00","is_delete":"1","del_yn":"N"},
 ]
 monkeypatch.setattr(comment_collector,"_fetch_dc_comments",lambda p:fake_items)

 result=comment_collector.collect_dc_comments(db,post_limit=10)

 comments=db.query(SentimentComment).all()
 assert len(comments)==1
 assert comments[0].content=="\uc88b\ub124\uc694 \uc7ac\ubc0c\uc788\uc5b4\uc694"
 assert result["found"]==1 and result["new"]==1


def test_naver_cafe_candidates_parses_article_list_and_stops_pagination(monkeypatch):
 # \uac8c\uc2dc\uae00 \ubaa9\ub85d\uc740 \ub85c\uadf8\uc778 \uc5c6\uc774 \uacf5\uac1c API\ub85c \uc870\ud68c\ub418\uc9c0\ub9cc, \ubcf8\ubb38\u00b7\ub313\uae00\uc740
 # \ub85c\uadf8\uc778\ud574\uc57c\ub9cc \ubcf4\uc5ec\uc11c(\uc9c1\uc811 \ud655\uc778) \uc81c\ubaa9\ub9cc \uc218\uc9d1\ud55c\ub2e4.
 page1={"message":{"result":{"hasNext":True,"articleList":[
  {"articleId":111,"subject":"\uc81c\ubaa91","writeDateTimestamp":1757800000000,"writerNickname":"a","readCount":10,"commentCount":2,"likeItCount":1},
 ]}}}
 page2={"message":{"result":{"hasNext":False,"articleList":[
  {"articleId":112,"subject":"\uc81c\ubaa92","writeDateTimestamp":1757800100000,"writerNickname":"b","readCount":5,"commentCount":0,"likeItCount":0},
 ]}}}
 calls=[page1,page2]
 monkeypatch.setattr(collector,"_get_json",lambda url,referer:calls.pop(0))

 out=collector.naver_cafe_candidates(pages=5)

 assert len(out)==2  # hasNext=False\uc5d0\uc11c \uba48\ucdb0\uc11c \uc694\uccad\ud55c 5\ud398\uc774\uc9c0\ub97c \ub2e4 \uc548 \ub3ce
 assert out[0].source=="NAVER_CAFE_LATALESIA"
 assert out[0].post_id=="111"
 assert out[0].title=="\uc81c\ubaa91"
 assert out[0].url=="https://cafe.naver.com/latalesia/111"
 assert out[0].content is None


def test_collect_never_fetches_content_for_naver_cafe(monkeypatch, db_factory):
 monkeypatch.setattr(collector,"dc_candidates",lambda pages:[])
 monkeypatch.setattr(collector,"priring_candidates",lambda pages:[])
 monkeypatch.setattr(collector,"latale_candidates",lambda pages:[])
 monkeypatch.setattr(collector,"naver_cafe_candidates",lambda pages:[collector.Candidate("NAVER_CAFE_LATALESIA","1","\uc81c\ubaa9",'https://cafe.naver.com/latalesia/1',None)])
 monkeypatch.setattr(collector,"_content",lambda item:(_ for _ in ()).throw(AssertionError("\ub124\uc774\ubc84 \uce74\ud398\ub294 \ubcf8\ubb38\uc744 \uac00\uc838\uc624\uba74 \uc548 \ub41c\ub2e4")))
 monkeypatch.setattr(collector,"collect_references",lambda db,pages=2:{"found":0,"new":0,"errors":[]})

 db=db_factory()
 result=collector.collect(db,pages=1,detail_limit=90)

 assert result["details"]==0
 post=db.query(SentimentPost).one()
 assert post.content is None
