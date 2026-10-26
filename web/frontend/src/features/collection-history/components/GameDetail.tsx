import { useState } from "react";
import type { GameCollection } from "../types";
import { dayLabel } from "../utils";

interface Props {
  game: GameCollection | null;
}

const PAGE_SIZE = 14;

export function GameDetail({ game }: Props) {
  const [shown, setShown] = useState(PAGE_SIZE);

  if (!game) {
    return (
      <section className="ch-panel">
        <p className="ch-empty">위 표에서 게임을 선택하면 날짜별로 수집된 이벤트를 볼 수 있습니다.</p>
      </section>
    );
  }
  const days = game.daily.slice(0, shown);

  return (
    <section className="ch-panel">
      <header className="ch-panel-head">
        <h2>{game.game} · 올해 수집 이력</h2>
        <span>
          올해 {game.ytd}건 · 전체 {game.total}건
        </span>
      </header>
      {game.daily.length === 0 ? (
        <p className="ch-empty">올해 새로 수집된 이벤트가 없습니다.</p>
      ) : (
        <ol className="ch-days">
          {days.map((day) => (
            <li key={day.date}>
              <div className="ch-day-head">
                <strong>{dayLabel(day.date)}</strong>
                <span>{day.count}건</span>
              </div>
              <ul className="ch-events">
                {day.events.map((event) => (
                  <li key={`${event.url}-${event.collectedAt}`}>
                    {event.url ? (
                      <a href={event.url} target="_blank" rel="noreferrer">
                        {event.title ?? event.url}
                      </a>
                    ) : (
                      <span>{event.title}</span>
                    )}
                    <span className={"ch-state" + (event.active ? " on" : "")}>{event.active ? "진행 중" : "종료"}</span>
                    {event.endsOn && <span className="ch-ends">~ {event.endsOn}</span>}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
      {game.daily.length > shown && (
        <button type="button" className="btn btn-ghost ch-more" onClick={() => setShown(shown + PAGE_SIZE)}>
          날짜 더 보기 ({game.daily.length - shown}일 남음)
        </button>
      )}
    </section>
  );
}
