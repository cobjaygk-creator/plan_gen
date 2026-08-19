import { useEffect, useMemo, useState } from "react";
import "./event-bench.css";

type Candidate = {
  game: string;
  title: string;
  event_url: string;
  hero_image_url: string | null;
  starts_on: string | null;
  ends_on: string | null;
  published_on: string | null;
  status: string | null;
  event_format: "full_page" | "board";
  collected_at: string;
  first_collected_at?: string;
  last_seen_at?: string;
};

type EventBenchPayload = {
  mode: "test";
  source: string;
  description: string;
  last_refreshed_at: string | null;
  refreshed_event_count: number;
  candidates: Candidate[];
};
type StatusFilter = "all" | "ongoing" | "ended";
type FormatFilter = "all" | "board" | "full_page";

const LABEL = { all: "\uc804\uccb4", ongoing: "\uc9c4\ud589 \uc911", ended: "\uc885\ub8cc" } as const;
const FORMAT_LABEL: Record<FormatFilter, string> = { all: "\uc804\uccb4", board: "\uac8c\uc2dc\ud310\ud615", full_page: "\ud480\ud398\uc774\uc9c0" };
// \ub9e4\uc77c \ud6d1\uc5b4\ubcf4\ub294 \uc2b5\uad00\uc5d0 \ub9de\ucd98 "\uc2e0\uaddc" \uae30\uc900 \u2014 \uc5b4\uc81c \ud558\ub8e8\ub97c \ubabb \ubd10\ub3c4 \ub193\uce58\uc9c0 \uc54a\ub3c4\ub85d 3\uc77c \uc5ec\uc720
const NEW_WINDOW_DAYS = 3;

function statusFor(item: Candidate): StatusFilter {
  return item.status === LABEL.ended ? "ended" : "ongoing";
}

function isNew(item: Candidate): boolean {
  const first = item.first_collected_at ?? item.collected_at;
  if (!first) return false;
  const ageMs = Date.now() - new Date(first).getTime();
  return ageMs >= 0 && ageMs <= NEW_WINDOW_DAYS * 24 * 60 * 60 * 1000;
}

function formatRefreshedAt(value: string | null): string {
  if (!value) return "\uac31\uc2e0 \uae30\ub85d \uc5c6\uc74c";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}


export function EventBenchPage() {
  const [data, setData] = useState<EventBenchPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [activeGame, setActiveGame] = useState<string>(LABEL.all);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ongoing");
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("all");
  const [newOnly, setNewOnly] = useState(false);
  const [latestRefreshOnly, setLatestRefreshOnly] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);

  useEffect(() => {
    fetch("/event-bench/candidates", { credentials: "include" })
      .then((response) => { if (!response.ok) throw new Error("failed"); return response.json() as Promise<EventBenchPayload>; })
      .then(setData).catch(() => setFailed(true));
  }, []);

  const handleManualRefresh = async () => {
    setRefreshing(true);
    setRefreshFailed(false);
    try {
      const response = await fetch("/event-bench/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) throw new Error("refresh failed");
      const refreshed = await response.json() as EventBenchPayload;
      setData(refreshed);
      setLatestRefreshOnly(false);
    } catch {
      setRefreshFailed(true);
    } finally {
      setRefreshing(false);
    }
  };

  const candidates = data?.candidates ?? [];
  const games = useMemo(() => [LABEL.all, ...Array.from(new Set(candidates.map((item) => item.game)))], [candidates]);
  const newCount = useMemo(() => candidates.filter(isNew).length, [candidates]);
  const candidatesForGameTabs = useMemo(() => candidates
    .filter((item) => statusFilter === "all" || statusFor(item) === statusFilter)
    .filter((item) => formatFilter === "all" || item.event_format === formatFilter)
    .filter((item) => !newOnly || isNew(item))
    .filter((item) => !latestRefreshOnly || item.first_collected_at === data?.last_refreshed_at)
, [candidates, statusFilter, formatFilter, newOnly, latestRefreshOnly, data?.last_refreshed_at]);
  const visibleCandidates = useMemo(() => candidatesForGameTabs
    .filter((item) => activeGame === LABEL.all || item.game === activeGame)
    .sort((left, right) => {
      const rightCollectedAt = right.first_collected_at ?? right.collected_at;
      const leftCollectedAt = left.first_collected_at ?? left.collected_at;
      const collectedOrder = rightCollectedAt.localeCompare(leftCollectedAt);
      if (collectedOrder !== 0) return collectedOrder;

      const rightPublishedOn = right.published_on ?? "";
      const leftPublishedOn = left.published_on ?? "";
      const publishedOrder = rightPublishedOn.localeCompare(leftPublishedOn);
      return publishedOrder !== 0 ? publishedOrder : left.title.localeCompare(right.title, "ko");
    }), [candidatesForGameTabs, activeGame]);


  if (failed) return <main className="event-bench-page"><p className="event-bench-empty">{"\uc218\uc9d1 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4."}</p></main>;
  if (!data) return <main className="event-bench-page"><p className="event-bench-empty">{"\uc218\uc9d1 \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."}</p></main>;

  return <main className="event-bench-page">
    <header className="event-bench-header">
      <h1>이벤트 모음</h1>
    <div className="event-bench-refresh-summary">
      <button
        type="button"
        className={latestRefreshOnly ? "is-active" : ""}
        disabled={!data.last_refreshed_at}
        onClick={() => {
          setLatestRefreshOnly((value) => !value);
          setActiveGame(LABEL.all);
          setStatusFilter("all");
          setFormatFilter("all");
          setNewOnly(false);
        }}
        aria-pressed={latestRefreshOnly}
      >
        <span>{"\ub9c8\uc9c0\ub9c9 \uac31\uc2e0"} {formatRefreshedAt(data.last_refreshed_at)}</span>
        <strong>{data.refreshed_event_count}{"\uac74 \ucd94\uac00"}</strong>
      </button>
      <button
        type="button"
        className="event-bench-manual-refresh"
        disabled={refreshing}
        onClick={handleManualRefresh}
      >
        {refreshing ? "\uc218\uc9d1 \uc911..." : "\uc218\ub3d9 \uc218\uc9d1"}
      </button>
      {refreshFailed && <span className="event-bench-refresh-error">{"\uc218\uc9d1 \uc2e4\ud328"}</span>}
    </div>
    </header>
    <div className="event-bench-filter-row">
      <nav className="event-bench-status-tabs" aria-label={"\uc774\ubca4\ud2b8 \uc0c1\ud0dc \ud544\ud130"}>{(["all", "ongoing", "ended"] as const).map((filter) => <button type="button" key={filter} className={statusFilter === filter ? "is-active" : ""} onClick={() => setStatusFilter(filter)}>{LABEL[filter]}</button>)}</nav>
      <nav className="event-bench-format-tabs" aria-label={"\uc774\ubca4\ud2b8 \ud615\uc2dd \ud544\ud130"}>{(["all", "board", "full_page"] as const).map((filter) => <button type="button" key={filter} className={formatFilter === filter ? "is-active" : ""} onClick={() => setFormatFilter(filter)}>{FORMAT_LABEL[filter]}</button>)}</nav>
      <button type="button" className={`event-bench-new-toggle${newOnly ? " is-active" : ""}`} onClick={() => setNewOnly((v) => !v)}>
        {"\uc2e0\uaddc\ub9cc"} <span>{newCount}</span>
      </button>
    </div>
    <nav className="event-bench-tabs" aria-label={"\uac8c\uc784\ubcc4 \uc774\ubca4\ud2b8 \ud544\ud130"}>{games.map((game) => <button type="button" key={game} className={activeGame === game ? "is-active" : ""} onClick={() => setActiveGame(game)}>{game}<span>{game === LABEL.all ? candidatesForGameTabs.length : candidatesForGameTabs.filter((item) => item.game === game).length}</span></button>)}</nav>
    <section className="event-bench-grid" aria-label={"\uc218\uc9d1\ub41c \uc774\ubca4\ud2b8 \ubaa9\ub85d"}>{visibleCandidates.map((item) => <article className="event-bench-card" key={item.event_url}><a className="event-bench-thumbnail-link" href={item.event_url} target="_blank" rel="noreferrer">{item.hero_image_url ? <img src={item.hero_image_url} alt="" /> : <div className="event-bench-image-placeholder" />}{isNew(item) && <b className="event-bench-thumbnail-new">NEW</b>}</a><div className="event-bench-card-body"><div className="event-bench-card-meta"><span>{item.game}</span><div className="event-bench-card-tags"><i className={item.event_format === "full_page" ? "format-full-page" : "format-board"}>{item.event_format === "full_page" ? "\ud480\ud398\uc774\uc9c0" : "\uac8c\uc2dc\ud310\ud615"}</i><b className={statusFor(item) === "ended" ? "status-ended" : ""}>{statusFor(item) === "ended" ? LABEL.ended : LABEL.ongoing}</b></div></div><h2><a href={item.event_url} target="_blank" rel="noreferrer">{item.title}</a></h2><time>{item.starts_on && item.ends_on ? `${item.starts_on} ~ ${item.ends_on}` : "\uae30\uac04 \uc815\ubcf4 \uc5c6\uc74c"}</time><a href={item.event_url} target="_blank" rel="noreferrer">{"\uacf5\uc2dd \uc774\ubca4\ud2b8 \ubcf4\uae30"} <span aria-hidden="true">&gt;</span></a></div></article>)}</section>
    {!visibleCandidates.length && <p className="event-bench-empty">{"\uc120\ud0dd\ud55c \uc870\uac74\uc5d0 \ud574\ub2f9\ud558\ub294 \uc774\ubca4\ud2b8\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}</p>}
    <section className="event-bench-source"><span>{"\uc218\uc9d1 \ucd9c\ucc98"}</span><strong>{data.source}</strong></section>
  </main>;
}


