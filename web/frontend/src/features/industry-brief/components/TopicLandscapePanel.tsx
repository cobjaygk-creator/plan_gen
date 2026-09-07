import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { IndustryBrief } from "../types";
import { useInView } from "../hooks/useInView";
import { SectionBar } from "./CategoryTag";

type Analytics = NonNullable<IndustryBrief["analytics"]>;

// GAME=주황·AI=파랑 — 이 페이지 다른 차트(이슈 관심도 변화 등)와 같은
// 배색을 써서 카테고리 색이 화면 전체에서 일관되게 읽히도록 한다.
const CATEGORY_COLORS = { GAME: "var(--cat-game)", AI: "var(--cat-ai)" } as const;

// 같은 좌표를 공유하는 원끼리 정확히 포개면 밑에 깔린 게 안 보인다 —
// 반투명으로 겹쳐도 형태가 드러날 만큼만 살짝 벌린다.
function fanOffset(index: number, total: number, spread: number): [number, number] {
  if (total <= 1) return [0, 0];
  const angle = (index / total) * Math.PI * 2 - Math.PI / 2;
  return [Math.cos(angle) * spread, Math.sin(angle) * spread];
}

/** 디자인 리뉴얼 5단계 때 표로 바꿨다가, "겹침을 숫자+반투명으로 이미
 * 해결했었잖아" 피드백으로 원래 버블 차트를 되살렸다 — 같은 좌표를
 * 공유하는 토픽은 반투명 원을 살짝 벌려 겹쳐 보이게 하고, 그 위에 검정
 * 숫자 배지를 올려 클릭하면 목록이 뜨는 구조(3차례 피드백으로 다듬은
 * 형태)를 그대로 유지한다. */
function TopicBubbleChart({ data: allData }: { data: Analytics["topicLandscape"] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [openGroup, setOpenGroup] = useState<{ key: string; x: number; y: number } | null>(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0]?.contentRect.width;
      if (measured) setWidth(measured);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const inView = useInView(containerRef);

  if (allData.length === 0) {
    return <p className="ib-chart-empty">이 기간엔 비교할 만큼 활성 토픽이 없습니다.</p>;
  }

  const data = [...allData].sort((a, b) => b.articleCount - a.articleCount).slice(0, 12);

  // 텍스트를 일부만 생략하는 대신, 같은 (출처 수, 지속일수) 좌표를 공유하는
  // 항목은 숫자 배지 하나로 묶는다 — 어떤 이름도 화면에서 조용히 빠지지
  // 않고, 배지를 클릭하면 그 자리에 겹친 토픽 목록이 전부 펼쳐진다.
  const groups = new Map<string, typeof data>();
  data.forEach((d) => {
    const key = `${d.sources}-${d.days}`;
    groups.set(key, [...(groups.get(key) ?? []), d]);
  });

  const height = 300;
  const left = 16, right = 20, top = 20, bottom = 30;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maxSources = Math.max(1, ...data.map((d) => d.sources)) + 1;
  const maxDays = Math.max(1, ...data.map((d) => d.days)) + 1;
  const maxCount = Math.max(1, ...data.map((d) => d.articleCount));
  const x = (v: number) => left + (v / maxSources) * plotWidth;
  const y = (v: number) => top + plotHeight - (v / maxDays) * plotHeight;
  const r = (v: number) => 8 + (v / maxCount) * 22;

  const openGroupTopics = openGroup ? groups.get(openGroup.key) ?? null : null;

  return (
    <div className="ib-chart-wrap" ref={containerRef} style={{ position: "relative" }}>
      <svg className="ib-bubble-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="토픽 지형도: 출처 수 대 지속일수 버블 차트">
        {[0, .25, .5, .75, 1].map((ratio) => (
          <line key={ratio} x1={left} x2={width - right} y1={top + plotHeight * (1 - ratio)} y2={top + plotHeight * (1 - ratio)} className="ib-chart-grid" />
        ))}
        <text x={left} y={height - 8} className="ib-bubble-axis-label">독립 출처 수 →</text>
        <text x={left} y={top + 10} className="ib-bubble-axis-label">지속일수 ↑</text>
        {[...groups.entries()].flatMap(([key, group], groupIndex) => {
          const [sources, days] = key.split("-").map(Number);
          const cx = x(sources), cy = y(days);
          const delay = `${groupIndex * 0.04}s`;

          // 반투명 원(들) — 겹치는 자리는 살짝 벌려서 포개진 형태 자체가
          // 드러나게 한다. 겹치지 않는 자리는 그대로 하나만 그린다.
          const bubbles = group.map((d, index) => {
            const [dx, dy] = fanOffset(index, group.length, group.length > 1 ? 9 : 0);
            return (
              <g key={d.name}>
                <circle cx={cx + dx} cy={cy + dy} r={r(d.articleCount)} fill={CATEGORY_COLORS[d.category]} className={`ib-anim-pop${inView ? " is-visible" : ""}`} style={{ animationDelay: delay, "--ib-target-opacity": d.isMarketing ? 0.28 : 0.55 } as CSSProperties}>
                  <title>{d.name} · 출처 {d.sources}곳 · {d.days}일 지속 · 기사 {d.articleCount}건{d.isMarketing ? " · 마케팅 지표 위주(도배성 가능성)" : ""}</title>
                </circle>
                {group.length === 1 && (
                  <text x={cx} y={cy - r(d.articleCount) - 5} textAnchor="middle" className="ib-bubble-label">{d.name}</text>
                )}
              </g>
            );
          });

          if (group.length === 1) return bubbles;

          // 겹친 자리를 알려주는 표식 — 밑에 깔린 반투명 원 색과 상관없이
          // 항상 또렷하게 보이도록 검정 계열 원 + 흰 숫자로 최상단에 그린다.
          const isOpen = openGroup?.key === key;
          const badge = (
            <g
              key={`${key}-badge`}
              className={`ib-bubble-cluster ib-anim-pop${inView ? " is-visible" : ""}`}
              style={{ animationDelay: delay }}
              tabIndex={0}
              role="button"
              aria-expanded={isOpen}
              aria-label={`겹친 토픽 ${group.length}개 보기`}
              onClick={() => setOpenGroup(isOpen ? null : { key, x: cx, y: cy })}
              onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setOpenGroup(isOpen ? null : { key, x: cx, y: cy }); }}
            >
              <circle cx={cx} cy={cy} r={11} className="ib-bubble-cluster-badge" stroke={isOpen ? "#fff" : "none"} strokeWidth={2}>
                <title>{group.map((d) => `${d.name}(${d.articleCount}건)`).join(", ")}</title>
              </circle>
              <text x={cx} y={cy + 4} textAnchor="middle" className="ib-bubble-cluster-count">{group.length}</text>
            </g>
          );
          return [...bubbles, badge];
        })}
      </svg>
      {openGroupTopics && openGroup && (
        <div className="ib-bubble-popover" style={{ left: openGroup.x, top: openGroup.y }}>
          <div className="ib-bubble-popover-head">
            <strong>겹친 토픽 {openGroupTopics.length}개</strong>
            <button type="button" onClick={() => setOpenGroup(null)} aria-label="닫기">×</button>
          </div>
          <ul>
            {openGroupTopics.map((d) => (
              <li key={d.name}>
                <i style={{ background: CATEGORY_COLORS[d.category] }} />
                {d.name}
                <span>{d.articleCount}건{d.isMarketing ? " · 마케팅성" : ""}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="ib-bubble-note">검정 숫자 원은 여러 토픽이 겹친 자리입니다 — 클릭하면 목록이 뜹니다.</p>
    </div>
  );
}

type FreshnessItem = Analytics["topicFreshness"]["fresh"][number];

/** 버블 차트만으로는 "이 토픽이 오늘 처음 떴는지, 며칠째 이어지는지"가
 * 한눈에 안 들어와서 별도로 뒀던 목록 — 5단계 리뉴얼 때 버블 차트와
 * 함께 없어졌다가, "그 목록 왜 지웠냐"는 피드백으로 같이 되살렸다.
 * 항목을 누르면 버블 차트의 겹침 배지와 같은 방식(클릭 → 팝업)으로
 * 그 토픽의 근거 기사를 띄운다. */
function FreshnessColumn({
  label, color, items, openName, onOpenChange,
}: {
  label: string; color: string; items: FreshnessItem[];
  openName: string | null; onOpenChange: (name: string | null) => void;
}) {
  const openItem = items.find((item) => item.name === openName) ?? null;
  return (
    <div className="ib-topic-freshness-column">
      <div className="ib-topic-freshness-head">
        <span className="ib-panel-color-bar" aria-hidden="true" style={{ background: color }} />
        <h3>{label}</h3>
        <span className="ib-panel-count">토픽 {items.length}개</span>
      </div>
      {items.length === 0 ? (
        <p className="ib-chart-empty">해당하는 토픽이 없습니다.</p>
      ) : (
        <ul className="ib-topic-freshness-list">
          {items.map((item) => {
            const isOpen = openName === item.name;
            return (
              <li key={item.name} style={{ position: "relative" }}>
                <button
                  type="button"
                  className="ib-topic-freshness-row"
                  aria-expanded={isOpen}
                  onClick={() => onOpenChange(isOpen ? null : item.name)}
                >
                  <i style={{ background: CATEGORY_COLORS[item.category] }} />
                  <span className="name">{item.name}</span>
                  <span className="count">기사 {item.articleCount}건</span>
                </button>
                {isOpen && openItem && (
                  <div className="ib-bubble-popover ib-topic-freshness-popover">
                    <div className="ib-bubble-popover-head">
                      <strong>{openItem.name} · 기사 {openItem.articleCount}건</strong>
                      <button type="button" onClick={() => onOpenChange(null)} aria-label="닫기">×</button>
                    </div>
                    <ul>
                      {openItem.articles.map((article) => (
                        <li key={article.url}>
                          <a href={article.url} target="_blank" rel="noreferrer">
                            <span className="outlet">{article.source.replace(/^NAVER · /, "")}</span>
                            <span className="title">{article.title}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function TopicFreshnessColumns({ freshness }: { freshness: Analytics["topicFreshness"] }) {
  // 두 열이 팝업 열림 상태를 공유해야 "다른 키워드를 고르면 전에 열려
  // 있던 팝업이 자동으로 닫힌다"가 열 경계를 넘어서도 성립한다 — 열마다
  // 따로 상태를 들고 있으면 신규 진입에서 하나, 지속 중에서 하나가 동시에
  // 열린 채로 남을 수 있었다.
  const [open, setOpen] = useState<{ column: "fresh" | "ongoing"; name: string } | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  // 바탕(팝업·트리거 버튼 바깥 아무 곳) 클릭 시 자동으로 닫는다.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (gridRef.current && !gridRef.current.contains(event.target as Node)) {
        setOpen(null);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  if (freshness.fresh.length === 0 && freshness.ongoing.length === 0) return null;
  return (
    <div className="ib-topic-freshness-grid" ref={gridRef}>
      <FreshnessColumn
        label="신규 진입" color="var(--ink-faint)" items={freshness.fresh}
        openName={open?.column === "fresh" ? open.name : null}
        onOpenChange={(name) => setOpen(name ? { column: "fresh", name } : null)}
      />
      <FreshnessColumn
        label="지속 중" color="var(--ink-faint)" items={freshness.ongoing}
        openName={open?.column === "ongoing" ? open.name : null}
        onOpenChange={(name) => setOpen(name ? { column: "ongoing", name } : null)}
      />
    </div>
  );
}

export function TopicLandscapePanel({ analytics }: { analytics: Analytics }) {
  return (
    <section className="card ib-topic-landscape-panel">
      <div className="ib-section-heading"><div><SectionBar color="var(--success)" />토픽 지형도</div></div>
      <TopicBubbleChart data={analytics.topicLandscape} />
      <TopicFreshnessColumns freshness={analytics.topicFreshness} />
    </section>
  );
}
