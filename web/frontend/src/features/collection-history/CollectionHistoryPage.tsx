import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { DateMatrix } from "./components/DateMatrix";
import { GameDetail } from "./components/GameDetail";
import { GameTable } from "./components/GameTable";
import { PeriodCards } from "./components/PeriodCards";
import type { CollectionHistory } from "./types";
import { dateTimeText } from "./utils";
import "./collection-history.css";

export function CollectionHistoryPage() {
  const [data, setData] = useState<CollectionHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getCollectionHistory());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "수집 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedGame = data?.games.find((game) => game.game === selected) ?? null;
  const now = data ? new Date(data.generatedAt).getTime() : Date.now();

  return (
    <div className="ch-page">
      <header className="ch-head">
        <div>
          <h1>수집 이력</h1>
          <p>게임별 이벤트 수집 현황을 기간별·날짜별로 확인합니다.</p>
        </div>
        <div className="ch-head-actions">
          {data && <span className="ch-asof">{dateTimeText(data.generatedAt)} 기준</span>}
          <button type="button" className="btn btn-ghost" onClick={() => void load()} disabled={loading}>
            {loading ? "불러오는 중…" : "새로고침"}
          </button>
        </div>
      </header>

      {error && <p className="ch-error">{error}</p>}
      {!data && loading && <p className="ch-empty">불러오는 중입니다…</p>}

      {data && (
        <>
          <PeriodCards totals={data.totals} />
          <GameTable games={data.games} selected={selected} now={now} onSelect={setSelected} />
          <DateMatrix games={data.games} today={data.today} selected={selected} onSelect={setSelected} />
          <GameDetail key={selectedGame?.game ?? "none"} game={selectedGame} />
          <p className="ch-note">
            ※ 날짜는 한국 시간 기준입니다. 서비스에 처음 적재된 날에는 기존에 진행 중이던 이벤트가 한꺼번에 들어와 건수가 많게
            보일 수 있습니다. 마지막 수집이 48시간 넘게 갱신되지 않은 게임은 수집 점검이 필요합니다.
          </p>
        </>
      )}
    </div>
  );
}
