import type { GameCollection } from "../types";
import { dateTimeText, freshnessOf } from "../utils";

interface Props {
  games: GameCollection[];
  selected: string | null;
  now: number;
  onSelect: (game: string) => void;
}

const FRESHNESS_TITLE = {
  ok: "정상",
  warn: "24시간 넘게 갱신 없음",
  late: "48시간 넘게 갱신 없음 — 수집 점검 필요",
  none: "수집 기록 없음",
} as const;

export function GameTable({ games, selected, now, onSelect }: Props) {
  return (
    <section className="ch-panel">
      <header className="ch-panel-head">
        <h2>게임별 현황</h2>
        <span>신규 수집 = 해당 이벤트를 처음 수집한 시점 기준</span>
      </header>
      <div className="ch-scroll">
        <table className="ch-table">
          <thead>
            <tr>
              <th scope="col">게임</th>
              <th scope="col">마지막 수집</th>
              <th scope="col" className="num">진행 중</th>
              <th scope="col" className="num">1일</th>
              <th scope="col" className="num">7일</th>
              <th scope="col" className="num">30일</th>
              <th scope="col" className="num">올해</th>
              <th scope="col" className="num">전체</th>
            </tr>
          </thead>
          <tbody>
            {games.map((game) => {
              const fresh = freshnessOf(game.lastSuccessAt, now);
              return (
                <tr key={game.game} className={selected === game.game ? "active" : ""}>
                  <th scope="row">
                    <button type="button" className="ch-link" onClick={() => onSelect(game.game)}>
                      {game.game}
                    </button>
                  </th>
                  <td>
                    <span className={`ch-chip ${fresh.level}`} title={FRESHNESS_TITLE[fresh.level]}>
                      {fresh.label}
                    </span>
                    <span className="ch-time">{dateTimeText(game.lastSuccessAt)}</span>
                  </td>
                  <td className="num">{game.active}</td>
                  <td className="num">{game.d1 || "·"}</td>
                  <td className="num">{game.d7 || "·"}</td>
                  <td className="num">{game.d30 || "·"}</td>
                  <td className="num">{game.ytd || "·"}</td>
                  <td className="num">{game.total}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
