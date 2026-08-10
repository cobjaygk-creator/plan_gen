import type { IndustryPanel } from "../types";
import { DIRECTION_CLASS, DIRECTION_SYMBOL } from "../utils/format";

interface Props {
  icon: string;
  title: string;
  panel: IndustryPanel;
}

export function IndustryPanelCard({ icon, title, panel }: Props) {
  return (
    <div className="card ib-panel">
      <div className="ib-panel-head">
        <span className="ic">{icon}</span>
        <h2>{title}</h2>
      </div>

      <div className="eyebrow">오늘의 핵심 한 줄</div>
      <p className="headline">{panel.headline}</p>

      <div className="briefing">
        {panel.briefing.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>

      <div className="section-label">오늘 달라진 것</div>
      <div className="ib-change-list">
        {panel.changes.map((c) => (
          <div className="ib-change-item" key={c.topic}>
            <span className={`dir ${DIRECTION_CLASS[c.direction]}`}>{DIRECTION_SYMBOL[c.direction]}</span>
            <div className="body">
              <div className="topic">{c.topic}</div>
              <div className="desc">{c.description}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="section-label">앞으로 볼 것</div>
      <div className="ib-watch-list">
        {panel.watchList.map((w) => (
          <div className="ib-watch-item" key={w.rank}>
            <span className="rank tabular">{w.rank}</span>
            <div className="body">
              <div className="topic">{w.topic}</div>
              <div className="desc">{w.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
