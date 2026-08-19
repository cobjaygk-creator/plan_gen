import { useState } from "react";
import type { IssueCard as IssueCardType } from "../types";
import { CONFIDENCE_LABEL, LIFECYCLE_LABEL } from "../utils/format";

export function IssueCard({ issue }: { issue: IssueCardType }) {
  const [showSources, setShowSources] = useState(false);
  const quality = issue.evidenceQuality;
  const verificationLabel = quality?.verificationStatus === "CORROBORATED" ? "교차검증" : quality?.verificationStatus === "OFFICIAL_ONLY" ? "공식 확인" : quality?.verificationStatus === "DISCOVERY_ONLY" ? "원문 확인 필요" : "단일 출처";

  return (
    <div className="ib-issue-card">
      <div className="ib-issue-top">
        <span className={`ib-tag cat-${issue.category}`}>{issue.category}</span>
        <span className={`ib-tag importance-${issue.importance}`}>중요도 {issue.importance}</span>
        <span className="ib-tag lifecycle">{LIFECYCLE_LABEL[issue.lifecycle]}</span>
        {quality && <span className={`ib-tag verification-${quality.verificationStatus.toLowerCase()}`}>{verificationLabel}</span>}
      </div>

      <h3 className="ib-issue-title">{issue.title}</h3>
      <p className="ib-issue-summary">{issue.summary}</p>

      <div className="ib-why-matters">
        <div className="label">WHY IT MATTERS</div>
        <div className="text">{issue.whyItMatters}</div>
      </div>

      <div className="ib-issue-foot">
        <div>
          <div className="ib-confidence">
            <span className="level">{CONFIDENCE_LABEL[issue.confidence.level]}</span> · 관련 보도{" "}
            <span className="tabular">{issue.confidence.articleCount}</span>건 · 독립 출처{" "}
            <span className="tabular">{issue.confidence.independentSources}</span>개 · 공식자료{" "}
            <span className="tabular">{issue.confidence.officialCount}</span>건
          </div>
          {quality && <div className={`ib-evidence-quality ${quality.synthesisEligible ? "verified" : "unverified"}`}>{quality.synthesisEligible ? "핵심 브리핑 근거 사용" : "추가 확인 필요 · 핵심 브리핑 근거 제외"}</div>}
          <div className="related">브리핑 반영: {issue.relatedBriefing}</div>
        </div>
        <button type="button" className="ib-source-toggle" onClick={() => setShowSources((v) => !v)}>
          {showSources ? "관련 기사 접기" : `관련 기사 보기 (${issue.sources.length})`}
        </button>
      </div>

      {showSources && (
        <div className="ib-source-cluster">
          {issue.sources.map((s) => (
            <div className="ib-source-item" key={s.url + s.title}>
              <span className="outlet">{s.outlet}</span>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
              <span className="ago">{s.publishedAgo}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
