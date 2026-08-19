import { useState } from "react";
import type { Signal } from "../types";
import { DIRECTION_SYMBOL } from "../utils/format";

type Domain = "ALL" | "GAME" | "AI" | "GAME_AI";

function SignalCards({ signals, onSelect }: { signals: Signal[]; onSelect: (topic: string) => void }) {
  return <div className="ib-signal-grid">{signals.map((signal) => (
    <button type="button" className="ib-signal-tile is-keyword" key={signal.topic} onClick={() => onSelect(signal.topic)}>
      <span className="ib-signal-event">{signal.eventType ?? "업계 이슈"}</span><span className="topic">{signal.topic}</span>
      <span className="ib-signal-metric"><b>{signal.todayCount}</b><span className="dir">{DIRECTION_SYMBOL[signal.direction]}</span></span>
      <span className={`ib-signal-state state-${signal.state.toLowerCase()}`}>{signal.stateLabel}</span><span className="ib-signal-priority">{signal.priorityReason ?? "최근 포착"}</span>
    </button>
  ))}</div>;
}

export function SignalsPanel({ signals }: { signals: Signal[] }) {
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [domain, setDomain] = useState<Domain>("ALL");
  const selected = signals.find((signal) => signal.topic === selectedTopic);
  const filtered = domain === "ALL" ? signals : signals.filter((signal) => signal.domain === domain);
  const close = () => setSelectedTopic(null);
  const filters: Array<[Domain, string]> = [["ALL", "전체"], ["GAME", "게임"], ["AI", "AI"], ["GAME_AI", "게임×AI"]];

  return (
    <section className="card ib-signals ib-signal-board">
      <div className="ib-section-heading"><div>주요 시그널</div><span>파급도 높은 사건 순</span></div>
      <div className="ib-signal-filters" role="tablist" aria-label="시그널 영역 필터">
        {filters.map(([value, label]) => <button key={value} type="button" className={domain === value ? "is-active" : ""} onClick={() => setDomain(value)}>{label}</button>)}
      </div>
      {filtered.length ? <SignalCards signals={filtered.slice(0, 8)} onSelect={setSelectedTopic} /> : <p className="ib-signal-empty">이 기간에는 해당 영역의 주요 신호가 없습니다.</p>}
      {selected && <div className="ib-signal-modal-backdrop" role="presentation" onClick={close}>
        <section className="ib-signal-modal" role="dialog" aria-modal="true" aria-label={`${selected.topic} 변화 상세`} onClick={(event) => event.stopPropagation()}>
          <button type="button" className="ib-signal-modal-close" onClick={close} aria-label="닫기">×</button>
          <p className="ib-signal-modal-eyebrow">{selected.eventType ?? selected.kindLabel} · {selected.stateLabel}</p>
          <h3>{selected.topic}</h3><p>{selected.reason}</p><p className="ib-signal-priority-detail">상단 노출 근거: {selected.priorityReason ?? "최근 포착"}</p>
          <div className="ib-signal-comparison"><span>최근 24시간 <b>{selected.todayCount}건</b></span><span>직전 7일 일평균 <b>{selected.baselineAverage}건</b></span><span>확인 매체 <b>{selected.sourceCount}개</b></span></div>
          {selected.evidence.length > 0 && <div className="ib-signal-evidence"><h4>근거 기사</h4>{selected.evidence.map((article) => <a key={article.url} href={article.url} target="_blank" rel="noreferrer"><span>{article.outlet}</span>{article.title}</a>)}</div>}
        </section>
      </div>}
    </section>
  );
}