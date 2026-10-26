import { useState } from "react";
import type { GameCollection } from "../types";
import { dayLabel, recentDates, shortDay } from "../utils";

interface Props {
  games: GameCollection[];
  today: string;
  selected: string | null;
  onSelect: (game: string) => void;
}

const RANGES = [7, 14, 30] as const;

export function DateMatrix({ games, today, selected, onSelect }: Props) {
  const [range, setRange] = useState<(typeof RANGES)[number]>(14);
  const dates = recentDates(today, range);

  const countsByGame = new Map(
    games.map((game) => [game.game, new Map(game.daily.map((day) => [day.date, day.count]))]),
  );
  const peak = Math.max(1, ...games.flatMap((game) => dates.map((date) => countsByGame.get(game.game)?.get(date) ?? 0)));

  return (
    <section className="ch-panel">
      <header className="ch-panel-head">
        <h2>게임별 날짜별 수집 이력</h2>
        <div className="ch-tabs" role="tablist" aria-label="조회 기간">
          {RANGES.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={range === value}
              className={range === value ? "active" : ""}
              onClick={() => setRange(value)}
            >
              최근 {value}일
            </button>
          ))}
        </div>
      </header>
      <div className="ch-scroll">
        <table className="ch-table ch-matrix">
          <thead>
            <tr>
              <th scope="col">게임</th>
              {dates.map((date) => (
                <th key={date} scope="col" className={"num" + (date === today ? " today" : "")} title={dayLabel(date)}>
                  {shortDay(date)}
                </th>
              ))}
              <th scope="col" className="num">합계</th>
            </tr>
          </thead>
          <tbody>
            {games.map((game) => {
              const counts = countsByGame.get(game.game);
              const sum = dates.reduce((acc, date) => acc + (counts?.get(date) ?? 0), 0);
              return (
                <tr key={game.game} className={selected === game.game ? "active" : ""}>
                  <th scope="row">
                    <button type="button" className="ch-link" onClick={() => onSelect(game.game)}>
                      {game.game}
                    </button>
                  </th>
                  {dates.map((date) => {
                    const count = counts?.get(date) ?? 0;
                    return (
                      <td
                        key={date}
                        className={"num cell" + (count ? " has" : "")}
                        style={count ? { ["--heat" as string]: `${Math.round(18 + (count / peak) * 62)}%` } : undefined}
                        title={`${game.game} · ${dayLabel(date)} · ${count}건`}
                      >
                        {count || "·"}
                      </td>
                    );
                  })}
                  <td className="num sum">{sum}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
