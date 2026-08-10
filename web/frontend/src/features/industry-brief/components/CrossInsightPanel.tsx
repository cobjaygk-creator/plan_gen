import type { CrossInsight } from "../types";

export function CrossInsightPanel({ insight }: { insight: CrossInsight }) {
  return (
    <div className={`card ib-cross${insight.hasSignal ? "" : " empty"}`}>
      <div className="ib-cross-head">
        <h2>GAME × AI</h2>
        <span className="sub">게임과 AI 업계 사이에서 나타나는 교차 흐름</span>
      </div>
      {insight.hasSignal ? (
        insight.summary.map((p, i) => <p key={i}>{p}</p>)
      ) : (
        <p>오늘은 두 산업을 연결할 만큼 뚜렷한 공통 신호가 확인되지 않았습니다.</p>
      )}
    </div>
  );
}
