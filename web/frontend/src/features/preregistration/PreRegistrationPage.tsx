import { useEffect, useMemo, useState } from "react";
import "./preregistration.css";

type PreRegistrationType =
  | "NEW_GAME" | "GAME_UPDATE" | "NEW_CLASS" | "NEW_CHARACTER" | "MAJOR_UPDATE"
  | "SEASON_UPDATE" | "ANNIVERSARY" | "NEW_SERVER" | "RETURN_CAMPAIGN" | "SPECIAL_EVENT" | "OTHER";
type Campaign = { id: number; game_name: string; campaign_name: string; preregistration_type: PreRegistrationType; platform: string[]; preregistration_start_date: string | null; preregistration_end_date: string | null; preregistration_url: string; thumbnail_url: string | null; };
type Payload = { types: PreRegistrationType[]; campaigns: Campaign[] };

const ALL = "ALL";
const TYPE_LABEL: Record<PreRegistrationType | typeof ALL, string> = {
  ALL: "\uc804\uccb4", NEW_GAME: "\uc2e0\uaddc \uac8c\uc784", GAME_UPDATE: "\uac8c\uc784 \uc5c5\ub370\uc774\ud2b8", NEW_CLASS: "\uc2e0\uaddc \ud074\ub798\uc2a4", NEW_CHARACTER: "\uc2e0\uaddc \uce90\ub9ad\ud130", MAJOR_UPDATE: "\ub300\uaddc\ubaa8 \uc5c5\ub370\uc774\ud2b8", SEASON_UPDATE: "\uc2dc\uc98c \uc5c5\ub370\uc774\ud2b8", ANNIVERSARY: "N\uc8fc\ub144", NEW_SERVER: "\uc2e0\uaddc \uc11c\ubc84", RETURN_CAMPAIGN: "\ubcf5\uadc0 \ucea0\ud398\uc778", SPECIAL_EVENT: "\ud2b9\ubcc4 \uc774\ubca4\ud2b8", OTHER: "\uae30\ud0c0",
};

function CampaignThumbnail({ item }: { item: Campaign }) {
  const [failed, setFailed] = useState(false);
  return <a href={item.preregistration_url} target="_blank" rel="noreferrer" className="prereg-thumbnail">
    {item.thumbnail_url && !failed
      ? <img src={item.thumbnail_url} alt="" onError={() => setFailed(true)} />
      : <div className="prereg-no-image" aria-label="No image"><span>NO</span><strong>IMAGE</strong></div>}
  </a>;
}

export function PreRegistrationPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [failed, setFailed] = useState(false);
  const [activeType, setActiveType] = useState<PreRegistrationType | typeof ALL>(ALL);
  useEffect(() => {
    fetch("/preregistrations/campaigns", { credentials: "include" })
      .then((response) => { if (!response.ok) throw new Error("failed"); return response.json() as Promise<Payload>; })
      .then(setData).catch(() => setFailed(true));
  }, []);
  const campaigns = useMemo(() => data?.campaigns.filter((item) => activeType === ALL || item.preregistration_type === activeType) ?? [], [activeType, data]);
  if (failed) return <main className="prereg-page"><p className="prereg-empty">{"\uc0ac\uc804\uc608\uc57d \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4."}</p></main>;
  if (!data) return <main className="prereg-page"><p className="prereg-empty">{"\uc0ac\uc804\uc608\uc57d \ubaa9\ub85d\uc744 \ubd88\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4."}</p></main>;
  return <main className="prereg-page">
    <header className="prereg-header"><span>PREREGISTRATION BENCHMARK</span><h1>{"\uc0ac\uc804\uc608\uc57d"}</h1><p>{"\uc2e0\uaddc \uac8c\uc784\ubfd0 \uc544\ub2c8\ub77c \uc5c5\ub370\uc774\ud2b8\u00b7\uc2dc\uc98c\u00b7\uc8fc\ub144 \ucea0\ud398\uc778\uc758 \uc2e4\uc81c \uc0ac\uc804\uc608\uc57d \ub79c\ub529\ud398\uc774\uc9c0\ub97c \uc218\uc9d1\ud569\ub2c8\ub2e4."}</p></header>
    <nav className="prereg-type-tabs" aria-label={"\uc0ac\uc804\uc608\uc57d \uc720\ud615 \ud544\ud130"}>{[ALL, ...data.types].map((type) => <button type="button" key={type} className={activeType === type ? "is-active" : ""} onClick={() => setActiveType(type as PreRegistrationType | typeof ALL)}>{TYPE_LABEL[type as PreRegistrationType | typeof ALL]}</button>)}</nav>
    {campaigns.length ? <section className="prereg-grid" aria-label={"\uc218\uc9d1\ub41c \uc0ac\uc804\uc608\uc57d \ucea0\ud398\uc778"}>{campaigns.map((item) => <article className="prereg-card" key={item.id}><CampaignThumbnail item={item} /><div className="prereg-card-body"><div className="prereg-meta"><span>{item.game_name}</span><b>{TYPE_LABEL[item.preregistration_type]}</b></div><h2><a href={item.preregistration_url} target="_blank" rel="noreferrer">{item.campaign_name}</a></h2><time>{item.preregistration_start_date ? `${item.preregistration_start_date}${item.preregistration_end_date ? ` ~ ${item.preregistration_end_date}` : ""}` : "\uae30\uac04 \uc815\ubcf4 \uc5c6\uc74c"}</time>{item.platform.length > 0 && <p>{item.platform.join(" \u00b7 ")}</p>}</div></article>)}</section> : <section className="prereg-empty prereg-empty-panel"><strong>{"\uc544\uc9c1 \ud655\uc778\ub41c \uc0ac\uc804\uc608\uc57d \ucea0\ud398\uc778\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."}</strong><span>{"\uacf5\uc2dd \ub79c\ub529\ud398\uc774\uc9c0\ub97c \ud655\uc778\ud55c \ub4a4, \uac8c\uc784 \uad00\ub828 \uc2e4\uc81c \uc0ac\uc804\uc608\uc57d\uc778 \uacbd\uc6b0\uc5d0\ub9cc \ucd94\uac00\ud569\ub2c8\ub2e4."}</span></section>}
  </main>;
}
