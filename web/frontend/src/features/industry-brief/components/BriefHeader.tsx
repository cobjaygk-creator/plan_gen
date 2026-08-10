import type { IndustryBrief } from "../types";
import { formatKoreanDateTime } from "../utils/format";

export function BriefHeader({ brief }: { brief: IndustryBrief }) {
  return (
    <div className="card ib-header">
      <div className="eyebrow">Industry Brief</div>
      <h1>게임 · AI 업계 동향</h1>
      <p>
        {brief.periodLabel} 동안 수집된 {brief.articleCount}개 자료를 분석했습니다.
      </p>
      <div className="meta tabular">{formatKoreanDateTime(brief.generatedAt)}</div>
    </div>
  );
}
