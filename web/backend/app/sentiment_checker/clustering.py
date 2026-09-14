from __future__ import annotations
import json,re
from collections import defaultdict
from .models import SentimentPost

def _tokens(post:SentimentPost)->set[str]:
    try: words=json.loads(post.keywords or "[]")
    except Exception: words=[]
    name=post.issue_key[3:] if post.issue_key.startswith("AI:") else post.issue_key.split(":",1)[-1]
    words += re.findall(r"[A-Za-z0-9_+-]{2,}|[\uac00-\ud7a3]{2,}",name.lower())
    return {w.lower() for w in words if len(w)>=2}

def _grams(value:str)->set[str]:
    v=re.sub(r"\s+","",value.lower())
    return {v[i:i+2] for i in range(max(0,len(v)-1))}

def _similar(a:SentimentPost,b:SentimentPost)->bool:
    if a.category!=b.category: return False
    at,bt=_tokens(a),_tokens(b)
    if at and bt and len(at&bt)/max(1,min(len(at),len(bt)))>=.5: return True
    an=a.issue_key[3:] if a.issue_key.startswith("AI:") else a.issue_key.split(":",1)[-1]
    bn=b.issue_key[3:] if b.issue_key.startswith("AI:") else b.issue_key.split(":",1)[-1]
    ag,bg=_grams(an),_grams(bn)
    return bool(ag and bg and len(ag&bg)/len(ag|bg)>=.42)

def cluster_posts(posts:list[SentimentPost])->list[list[SentimentPost]]:
    # score_eligible=False로 걸러진 글은 "주요 이슈" 목록에서도 뺀다.
    # DCInside 라테일 갤러리는 특정 이용자를 저격하는 은어("사랑짝",
    # "주딱은" 등) 드립이 많은데, AI 분석이 이런 글을 개인 공격/잡담으로
    # 정확히 판단해 score_eligible=False로 표시해도, 예전엔 여기서
    # 광고/거래/타게임만 걸러내서 저격 논쟁이 그대로 "주요 이슈"에
    # 노출됐다(사용자 확인). 광고/거래/타게임/짧은 반응 전부 score_eligible
    # =False로 이미 표시되므로 이 판단 하나로 충분하다.
    eligible=[p for p in posts if p.issue_key and p.issue_key!="OTHER" and p.score_eligible]
    parent=list(range(len(eligible)))
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i in range(len(eligible)):
        for j in range(i+1,len(eligible)):
            if _similar(eligible[i],eligible[j]): union(i,j)
    groups=defaultdict(list)
    for i,p in enumerate(eligible): groups[find(i)].append(p)
    return list(groups.values())

def representative_name(posts:list[SentimentPost])->str:
    names=[]
    for p in posts:
        name=p.issue_key[3:] if p.issue_key.startswith("AI:") else p.issue_key.split(":",1)[-1]
        if name and name!="OTHER": names.append(name)
    if not names:return "OTHER"
    ai=[p.issue_key[3:] for p in posts if p.issue_key.startswith("AI:")]
    return max(ai or names,key=lambda x:(len(x),x))
