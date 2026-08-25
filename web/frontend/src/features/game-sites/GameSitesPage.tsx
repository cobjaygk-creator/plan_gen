import { useEffect, useMemo, useState } from "react";
import "./game-sites.css";

type SiteType = "OFFICIAL" | "PREREGISTRATION" | "TEASER" | "MICROSITE" | "PROMOTION";
type GameSite = {
  id: string;
  game_name: string;
  site_name: string;
  site_type: SiteType;
  url: string;
  thumbnail_url: string | null;
  publisher: string | null;
  platform: string[];
  discovered_at: string | null;
  source: string;
  status: string;
};
type Payload = { types: SiteType[]; total: number; last_refreshed_at: string | null; refreshed_site_count: number; sites: GameSite[] };

const ALL = "ALL" as const;
const TYPE_LABEL: Record<SiteType | typeof ALL, string> = {
  ALL: "\uc804\uccb4",
  OFFICIAL: "\uacf5\uc2dd \uc0ac\uc774\ud2b8",
  PREREGISTRATION: "\uc0ac\uc804\uc608\uc57d",
  TEASER: "\ud2f0\uc800",
  MICROSITE: "\ub9c8\uc774\ud06c\ub85c\uc0ac\uc774\ud2b8",
  PROMOTION: "\ud504\ub85c\ubaa8\uc158",
};

function hostFor(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}

function dateFor(value: string | null) {
  if (!value) return "\ubc1c\uacac\uc77c \uc815\ubcf4 \uc5c6\uc74c";
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function formatRefreshedAt(value: string | null): string {
  if (!value) return "\uac31\uc2e0 \uae30\ub85d \uc5c6\uc74c";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(value));
}

function SiteThumbnail({ item }: { item: GameSite }) {
  const [failed, setFailed] = useState(false);
  return <a href={item.url} target="_blank" rel="noreferrer" className="game-site-thumbnail">
    {item.thumbnail_url && !failed
      ? <img src={item.thumbnail_url} alt="" onError={() => setFailed(true)} />
      : <div className="game-site-no-image"><span>GAME SITE</span><strong>NO IMAGE</strong></div>}
  </a>;
}

type RefreshResult = { portals: number; discovered: number; new_sites: number; errors: Record<string, string>; refreshed_at: string };

// GitHub Pages has no backend to run a live collection against — data refreshes
// automatically on the workflow's own schedule instead.
const IS_STATIC_SITE = import.meta.env.VITE_STATIC_SITE === "true";

export function GameSitesPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [failed, setFailed] = useState(false);
  const [activeType, setActiveType] = useState<SiteType | typeof ALL>(ALL);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<RefreshResult | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  function loadSites() {
    return fetch("/game-sites/data", { credentials: "include" })
      .then((response) => { if (!response.ok) throw new Error("failed"); return response.json() as Promise<Payload>; })
      .then(setData);
  }

  useEffect(() => {
    loadSites().catch(() => setFailed(true));
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const response = await fetch("/game-sites/refresh", { method: "POST", credentials: "include" });
      if (!response.ok) throw new Error("failed");
      const result = (await response.json()) as RefreshResult;
      setRefreshResult(result);
      await loadSites();
    } catch {
      setRefreshError("수집에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setRefreshing(false);
    }
  }

  const sites = useMemo(() => data?.sites.filter((item) => activeType === ALL || item.site_type === activeType) ?? [], [activeType, data]);
  if (failed) return <main className="game-sites-page"><p className="game-sites-empty">{"사이트 목록을 불러오지 못했습니다."}</p></main>;
  if (!data) return <main className="game-sites-page"><p className="game-sites-empty">{"사이트 목록을 불러오는 중입니다."}</p></main>;
  return <main className="game-sites-page">
    <header className="game-sites-header">
      <h1>{"사이트 모음"}</h1>
      <div className="game-sites-header-actions">
        <span className="game-sites-refresh-pill">
          <span>{"마지막 갱신 "}{formatRefreshedAt(data.last_refreshed_at)}</span>
          <strong>{data.refreshed_site_count}{"건 추가"}</strong>
        </span>
        {!IS_STATIC_SITE && (
          <button type="button" className="game-sites-refresh-btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "수집 중..." : "지금 수집"}
          </button>
        )}
      </div>
    </header>
    {refreshResult && !refreshError && (
      <p className="game-sites-refresh-note">
        {`포털 ${refreshResult.portals}곳 확인, 신규 사이트 ${refreshResult.new_sites}개 발견`}
        {Object.keys(refreshResult.errors).length > 0 && ` (실패: ${Object.keys(refreshResult.errors).join(", ")})`}
      </p>
    )}
    {refreshError && <p className="game-sites-refresh-note is-error">{refreshError}</p>}
    <nav className="game-sites-tabs" aria-label={"\uc0ac\uc774\ud2b8 \uc720\ud615 \ud544\ud130"}>{[ALL, ...data.types].map((type) => <button type="button" key={type} className={activeType === type ? "is-active" : ""} onClick={() => setActiveType(type as SiteType | typeof ALL)}>{TYPE_LABEL[type as SiteType | typeof ALL]}<span>{type === ALL ? data.sites.length : data.sites.filter((item) => item.site_type === type).length}</span></button>)}</nav>
    {sites.length ? <section className="game-sites-grid">{sites.map((item) => <article className="game-site-card" key={item.id}><SiteThumbnail item={item} /><div className="game-site-body"><div className="game-site-meta"><span>{item.game_name}</span><b>{TYPE_LABEL[item.site_type]}</b></div><h2><a href={item.url} target="_blank" rel="noreferrer">{item.site_name}</a></h2><p>{hostFor(item.url)}</p><div className="game-site-footer"><time>{dateFor(item.discovered_at)}</time><a href={item.url} target="_blank" rel="noreferrer">{"\uc0ac\uc774\ud2b8 \uc5f4\uae30"} &gt;</a></div></div></article>)}</section> : <p className="game-sites-empty">{"\uc120\ud0dd\ud55c \uc720\ud615\uc758 \uc0ac\uc774\ud2b8\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."}</p>}
  </main>;
}
