interface SentimentBarProps {
  positive: number;
  neutral: number;
  negative: number;
}

/** 긍정/중립/부정 비율을 한 줄짜리 막대로 보여준다. 색은 앱 공통 토큰
 * (--success/--ink-faint/--danger)만 쓴다 — 예전 버전은 하드코딩된
 * hex 색이라 다크 모드에서 대비가 안 맞았다. */
export function SentimentBar({ positive, neutral, negative }: SentimentBarProps) {
  return (
    <div className="sc-sentiment-bar" role="img" aria-label={`긍정 ${positive}%, 중립 ${neutral}%, 부정 ${negative}%`}>
      <i style={{ width: `${positive}%`, background: "var(--success)" }} />
      <i style={{ width: `${neutral}%`, background: "var(--ink-faint)" }} />
      <i style={{ width: `${negative}%`, background: "var(--danger)" }} />
    </div>
  );
}
