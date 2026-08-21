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
    # Score exclusion and issue discovery are separate concerns. Questions and
    # short reactions still reveal which topics are active.
    hard_exclusions={"ADVERTISEMENT","TRADE","OFFTOPIC"}
    eligible=[p for p in posts if p.issue_key and p.issue_key!="OTHER" and p.exclusion_reason not in hard_exclusions]
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
