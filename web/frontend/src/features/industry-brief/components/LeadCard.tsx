import type { CSSProperties, ReactNode } from "react";

interface Ground {
  label: string;
  body: ReactNode;
}

interface CategoryBadge {
  label: string;
  color: string;
}

interface LeadCardProps {
  /** dot 색 — 탭마다 다름(오늘=--success, 정책=--warning, 기술 레이더=--cat-ai). */
  dotColor: string;
  eyebrow: string;
  headline: ReactNode;
  /** 정책 탭 전용: 헤드라인을 40px 대신 34px로, max-width 제한 없이. */
  compact?: boolean;
  /** 헤드라인 폰트 20% 축소(32px) + 말줄임. 줄 수는 clampLines(기본 2). */
  clamped?: boolean;
  clampLines?: 1 | 2;
  categoryBadge?: CategoryBadge;
  /** 3~4칸 근거 구획. 트렌드 탭처럼 KPI/본문을 직접 넣을 땐 생략하고 children을 쓴다. */
  grounds?: Ground[];
  children?: ReactNode;
}

/** 4개 탭 공통 리드 카드 — design_handoff_industry_brief 4단계 신설.
 * "오늘 무슨 일이 있었는지"를 한 줄 판단 + 근거로 요약해, 이 카드만 캡처해도
 * 보고에 쓸 수 있게 하는 게 목적이다. */
export function LeadCard({ dotColor, eyebrow, headline, compact, clamped, clampLines = 2, categoryBadge, grounds, children }: LeadCardProps) {
  return (
    <section className="ib-lead" style={{ "--dot-color": dotColor } as CSSProperties}>
      <div className="ib-lead-eyebrow">{eyebrow}</div>
      {categoryBadge && <span className="ib-lead-category-badge" style={{ background: categoryBadge.color }}>{categoryBadge.label}</span>}
      <p
        className={`ib-lead-headline${compact ? " is-compact" : ""}${clamped ? " is-clamped" : ""}`}
        style={clamped ? { WebkitLineClamp: clampLines } : undefined}
      >
        {headline}
      </p>
      {grounds && grounds.length > 0 && (
        <div className="ib-lead-grounds" style={{ "--ground-count": grounds.length } as CSSProperties}>
          {grounds.map((ground) => (
            <div key={ground.label}>
              <span>{ground.label}</span>
              <p>{ground.body}</p>
            </div>
          ))}
        </div>
      )}
      {children}
    </section>
  );
}
