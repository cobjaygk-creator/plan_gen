import { useState } from "react";
import { SectionBar } from "./CategoryTag";
import type { PolicyUpdate } from "../types";

const CATEGORY_FILTERS: Array<{ key: "ALL" | "GAME" | "AI"; label: string }> = [
  { key: "ALL", label: "전체" },
  { key: "GAME", label: "게임" },
  { key: "AI", label: "AI" },
];

const TYPE_FILTERS: Array<{ key: "ALL" | PolicyUpdate["type"]; label: string }> = [
  { key: "ALL", label: "전체" },
  { key: "REGULATION", label: "규제 시행" },
  { key: "ENFORCEMENT", label: "단속·집행" },
  { key: "FUNDING", label: "지원사업" },
  { key: "TALENT", label: "인재" },
  { key: "GLOBAL", label: "해외 진출" },
  { key: "PARTNERSHIP", label: "협력" },
];

// publishedDate는 "YYYY.MM.DD" 날짜만 있고 시각이 없다 — 정확한 48시간이
// 아니라 "오늘/어제 날짜인가"로 근사한다. 실제 발표 시각까지 갖고 있지
// 않은 이상 이게 낼 수 있는 최선의 근사치다.
function isWithin48Hours(publishedDate: string): boolean {
  const [year, month, day] = publishedDate.split(".").map(Number);
  if (!year || !month || !day) return false;
  const published = new Date(year, month - 1, day).getTime();
  const diffMs = Date.now() - published;
  return diffMs >= 0 && diffMs <= 48 * 60 * 60 * 1000;
}

export function PolicyUpdatesPanel({ timeline }: { timeline: PolicyUpdate[] }) {
  const [category, setCategory] = useState<"ALL" | "GAME" | "AI">("ALL");
  const [typeFilter, setTypeFilter] = useState<"ALL" | PolicyUpdate["type"]>("ALL");
  const inCategory = category === "ALL" ? timeline : timeline.filter((item) => item.category === category);
  const visible = typeFilter === "ALL" ? inCategory : inCategory.filter((item) => item.type === typeFilter);

  return <section className="card ib-policy-panel">
    <div className="ib-section-heading">
      <div><SectionBar color="var(--warning)" />정책·제도 업데이트</div>
    </div>
    <div className="ib-policy-view-tabs">
      {CATEGORY_FILTERS.map((item) => (
        <button className={category === item.key ? "is-active" : ""} key={item.key} onClick={() => setCategory(item.key)} type="button">{item.label}</button>
      ))}
    </div>
    {inCategory.length > 0 && <div className="ib-policy-filters">{TYPE_FILTERS.map((item) => (
      <button className={typeFilter === item.key ? "is-active" : ""} key={item.key} onClick={() => setTypeFilter(item.key)} type="button">{item.label}</button>
    ))}</div>}
    {visible.length === 0 ? <p className="ib-policy-empty">{inCategory.length === 0 ? "선택한 카테고리에는 공식 정책 발표가 없습니다." : "선택한 유형의 공식 정책 발표가 없습니다."}</p> : <ol className="ib-policy-timeline">{visible.map((item) => (
      <li key={`timeline-${item.id}`}>
        <time>{item.publishedDate}</time><span className={`ib-policy-timeline-dot${isWithin48Hours(item.publishedDate) ? " is-recent" : ""}`} />
        <div><div><span className={`ib-policy-category cat-${item.category.toLowerCase()}`}>{item.category}</span><strong>{item.changeLabel}</strong><span>{item.typeLabel}</span><em>{item.urgencyLabel}</em></div>
        <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
        <p>{item.policyKey}{item.historyCount > 0 ? ` · 이전 발표 ${item.historyCount}건과 연결` : ""}</p></div>
      </li>
    ))}</ol>}
  </section>;
}
