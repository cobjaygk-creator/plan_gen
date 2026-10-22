from __future__ import annotations

import html

from .converter import SlideDoc

_CSS = """
:root{--bg:#f4f6f7;--surface:#fff;--ink:#132022;--muted:#5b6f73;--accent:#0e7c86;--accent-soft:#dcf0f0;--border:#d7dfe0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Pretendard","Malgun Gothic",-apple-system,"Segoe UI",sans-serif}
.wf-nav{position:sticky;top:0;z-index:10;display:flex;gap:6px;flex-wrap:wrap;padding:10px 16px;background:var(--surface);border-bottom:1px solid var(--border)}
.wf-nav a{padding:3px 10px;border-radius:999px;border:1px solid var(--border);color:var(--muted);text-decoration:none;font-size:12px}
.wf-nav a:hover{border-color:var(--accent);color:var(--accent)}
.wf-slide{max-width:1400px;margin:24px auto;padding:0 16px}
.wf-head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px}
.wf-head h2{margin:0;font-size:18px}
.wf-head .meta{color:var(--muted);font-size:12px}
.wf-layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px;align-items:start}
.wf-layout.full{grid-template-columns:minmax(0,1fr)}
.wf-stage{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.wf-canvas{position:relative;transform-origin:0 0;background:#fff;overflow:hidden}
.wf-box{position:absolute;display:flex;flex-direction:column;padding:2px 6px;overflow:hidden;color:#1d2a2c;line-height:1.25;word-break:keep-all;white-space:pre-wrap}
.wf-text{overflow:visible}
.wf-image{background:repeating-linear-gradient(45deg,#e4e9ea,#e4e9ea 8px,#edf0f1 8px,#edf0f1 16px)}
.wf-table{position:absolute}
.wf-table table{border-collapse:collapse;table-layout:fixed;font-size:11px;background:#fff}
.wf-table td{border:1px solid var(--border);padding:2px 5px;vertical-align:top;color:#1d2a2c}
.wf-lines{position:absolute;left:0;top:0;pointer-events:none}
.wf-badge{position:absolute;display:flex;align-items:center;justify-content:center;border-radius:50%;background:var(--accent);color:#fff;font-size:11px;font-weight:700;cursor:pointer;z-index:5}
.wf-badge.on,.wf-note.on .n{outline:3px solid #f2b84b;outline-offset:1px}
.wf-panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:6px 0}
.wf-note{display:flex;gap:10px;padding:8px 14px;cursor:pointer;border-top:1px solid var(--border)}
.wf-note:first-child{border-top:0}
.wf-note:hover,.wf-note.on{background:var(--accent-soft)}
.wf-note .n{flex:none;width:22px;height:22px;border-radius:50%;background:var(--accent);color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center}
.wf-note .t{font-size:13px;white-space:pre-line}
@media(max-width:900px){.wf-layout{grid-template-columns:minmax(0,1fr)}}
"""

_JS = """
function fit(){document.querySelectorAll('.wf-stage').forEach(function(s){var c=s.firstElementChild,w=+c.dataset.w,h=+c.dataset.h,k=Math.min(1.6,s.clientWidth/w);c.style.transform='scale('+k+')';s.style.height=(h*k)+'px'})}
function mark(slide,n,on){slide.querySelectorAll('[data-n="'+n+'"]').forEach(function(e){e.classList.toggle('on',on)})}
document.querySelectorAll('.wf-slide').forEach(function(slide){slide.querySelectorAll('[data-n]').forEach(function(e){
e.addEventListener('mouseenter',function(){mark(slide,e.dataset.n,true)});
e.addEventListener('mouseleave',function(){mark(slide,e.dataset.n,false)})})});
window.addEventListener('resize',fit);fit();
"""


def _slide_html(doc: SlideDoc) -> str:
    label = doc.title or f"슬라이드 {doc.index}"
    meta = " · ".join(part for part in (doc.project, doc.page_id) if part)
    notes = "".join(
        f'<div class="wf-note" data-n="{a.number}"><span class="n">{a.number}</span>'
        f'<span class="t">{html.escape(a.text)}</span></div>'
        for a in doc.annotations
    )
    panel = f'<aside class="wf-panel">{notes}</aside>' if notes else ""
    layout = "wf-layout" if notes else "wf-layout full"
    return (
        f'<section class="wf-slide" id="s{doc.index}">'
        f'<div class="wf-head"><h2>{doc.index}. {html.escape(label)}</h2><span class="meta">{html.escape(meta)}</span></div>'
        f'<div class="{layout}"><div class="wf-stage">'
        f'<div class="wf-canvas" data-w="{doc.width}" data-h="{doc.height}" style="width:{doc.width}px;height:{doc.height}px">{doc.body}</div>'
        f"</div>{panel}</div></section>"
    )


def render_html(docs: list[SlideDoc], title: str) -> str:
    nav = "".join(
        f'<a href="#s{d.index}">{d.index}. {html.escape(d.title or "슬라이드")}</a>' for d in docs
    )
    sections = "".join(_slide_html(d) for d in docs)
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
        f'<body><nav class="wf-nav">{nav}</nav>{sections}<script>{_JS}</script></body></html>'
    )
