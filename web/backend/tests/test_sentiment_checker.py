from datetime import datetime,timezone
from app.sentiment_checker.models import SentimentPost,SentimentComment
from app.sentiment_checker.clustering import cluster_posts

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
