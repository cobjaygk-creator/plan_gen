import type { Issue, Observation } from "../types";

interface RisingPanelProps {
  spikes: Issue[];
  observations: Observation[];
  onSelect: (key: string) => void;
}

/** 급상승 신호가 있으면 그걸, 없으면(신호가 약한 기간) 점수 산정에서
 * 제외된 게시글 사유 분포를 대신 보여준다 — 빈 칸으로 두는 것보다
 * "왜 지금 이슈가 안 잡히는지"를 알려주는 게 낫다는 판단. */
export function RisingPanel({ spikes, observations, onSelect }: RisingPanelProps) {
  return (
    <section className="sc-panel">
      <span className="sc-eyebrow">급상승 신호</span>
      <h2>{spikes.length ? "언급이 급격히 늘어난 이슈" : "이번 기간 제외 사유"}</h2>
      <div className="sc-spike-list">
        {spikes.length
          ? spikes.map((issue) => (
              <article
                key={issue.key}
                onClick={() => onSelect(issue.key)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onSelect(issue.key);
                }}
              >
                <strong>{issue.title}</strong>
                <span>+{issue.growth}</span>
                <p>
                  {issue.category} · 부정 {issue.negative}%
                </p>
              </article>
            ))
          : observations.map((item) => (
              <article key={item.reason}>
                <strong>{item.name}</strong>
                <span>{item.count}</span>
                <p>지수 산정에서는 제외되지만 증가 여부를 함께 관찰합니다.</p>
              </article>
            ))}
        {spikes.length === 0 && observations.length === 0 && <p className="sc-empty">표시할 데이터가 없습니다.</p>}
      </div>
    </section>
  );
}
