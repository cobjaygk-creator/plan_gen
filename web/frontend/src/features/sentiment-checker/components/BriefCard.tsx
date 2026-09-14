import { ANALYSIS_BASIS_LABEL } from "../utils";

interface BriefCardProps {
  brief: string;
  analysisBasis: string;
  analysisCount: number;
}

export function BriefCard({ brief, analysisBasis, analysisCount }: BriefCardProps) {
  return (
    <section className="sc-brief">
      <div className="sc-brief-eyebrow">지금 이 순간</div>
      <h2>
        오늘의 브리핑
        <small>
          {ANALYSIS_BASIS_LABEL[analysisBasis] ?? analysisBasis} · {analysisCount}건 기준
        </small>
      </h2>
      <p>{brief}</p>
    </section>
  );
}
