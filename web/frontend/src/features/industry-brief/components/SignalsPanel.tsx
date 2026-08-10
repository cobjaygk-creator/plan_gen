import type { Signal } from "../types";
import { DIRECTION_CLASS, DIRECTION_SYMBOL } from "../utils/format";

export function SignalsPanel({ signals }: { signals: Signal[] }) {
  return (
    <div className="card ib-signals">
      <h2>Today's Signals</h2>
      {signals.map((s) => (
        <div className="ib-signal-row" key={s.topic}>
          <span className="topic">{s.topic}</span>
          <span className="ib-signal-bar-track">
            <span className="ib-signal-bar-fill" style={{ width: `${s.weight}%` }} />
          </span>
          <span className={`dir ${DIRECTION_CLASS[s.direction]}`}>{DIRECTION_SYMBOL[s.direction]}</span>
        </div>
      ))}
    </div>
  );
}
