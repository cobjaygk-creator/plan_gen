import { useEffect, useState } from "react";
import { approveEditorialRule, clearIssueFeedback, deactivateEditorialRule, fetchCoreFeedbacks, fetchEditorialRules, previewEditorialRule, type ActiveEditorialRule, type CoreFeedbackItem, type EditorialRuleHistory, type EditorialRulePreview, type EditorialRuleSuggestion } from "../api/client";

const REASON_LABEL: Record<string, string> = { PROMOTIONAL: "홍보성", LOW_IMPORTANCE: "중요도 낮음", DUPLICATE: "중복", LOW_IMPACT: "업계 영향 부족", OTHER: "기타" };
const ACTION_LABEL: Record<string, string> = { APPROVED: "승인", REACTIVATED: "재활성화", DEACTIVATED: "비활성화" };

export function EditorialFeedbackManager({ onRestore }: { onRestore: () => void }) {
  const [items, setItems] = useState<CoreFeedbackItem[]>([]);
  const [error, setError] = useState(false);
  const [suggestions, setSuggestions] = useState<EditorialRuleSuggestion[]>([]);
  const [activeRules, setActiveRules] = useState<ActiveEditorialRule[]>([]);
  const [history, setHistory] = useState<EditorialRuleHistory[]>([]);
  const [preview, setPreview] = useState<EditorialRulePreview | null>(null);
  useEffect(() => {
    const load = () => { void Promise.all([fetchCoreFeedbacks(), fetchEditorialRules()]).then(([next, rules]) => { setItems(next); setSuggestions(rules.suggestions); setActiveRules(rules.activeRules); setHistory(rules.history ?? []); setError(false); }).catch(() => setError(true)); };
    load();
    window.addEventListener("industry-feedback-changed", load);
    return () => window.removeEventListener("industry-feedback-changed", load);
  }, []);
  const restore = async (issueId: number) => {
    try {
      await clearIssueFeedback(issueId);
      setItems((current) => current.filter((item) => item.issueId !== issueId));
      window.dispatchEvent(new Event("industry-feedback-changed"));
      setError(false);
      onRestore();
    } catch { setError(true); }
  };
  const approve = async (item: EditorialRuleSuggestion) => {
    try {
      const impact = await previewEditorialRule(item.pattern, item.reason);
      if (impact.riskLevel === "CAUTION") { setPreview(impact); return; }
      await approveEditorialRule(item.pattern, item.reason);
      setPreview(null); window.dispatchEvent(new Event("industry-feedback-changed")); onRestore();
    } catch { setError(true); }
  };
  const confirmCaution = async () => {
    if (!preview) return;
    try { await approveEditorialRule(preview.pattern, preview.reason, true); setPreview(null); window.dispatchEvent(new Event("industry-feedback-changed")); onRestore(); } catch { setError(true); }
  };
  const showPreview = async (item: EditorialRuleSuggestion) => {
    try { setPreview(await previewEditorialRule(item.pattern, item.reason)); setError(false); } catch { setError(true); }
  };
  const deactivate = async (ruleId: number) => {
    try { await deactivateEditorialRule(ruleId); window.dispatchEvent(new Event("industry-feedback-changed")); onRestore(); } catch { setError(true); }
  };
  return <details className="ib-feedback-manager"><summary>편집 기준 <span>{items.length}</span></summary>
    {error && <p className="ib-feedback-error">편집 기준을 처리하지 못했습니다.</p>}
    {items.length === 0 ? <p>핵심 요약에서 제외한 이슈가 없습니다.</p> : <div className="ib-feedback-list">{items.map((item) => <div key={item.issueId}><span>{item.category}</span><strong>{item.title}</strong><small>{Object.entries(item.reasonCounts).map(([reason,count]) => `${REASON_LABEL[reason] ?? reason} ${count}`).join(" · ")}</small><button type="button" onClick={() => void restore(item.issueId)}>복원</button></div>)}</div>}
    {suggestions.length > 0 && <section className="ib-rule-section"><h4>자동 규칙 후보</h4>{suggestions.map((item) => <div key={`${item.reason}-${item.pattern}`}><span>{REASON_LABEL[item.reason]}</span><strong>‘{item.pattern}’ 포함</strong><small>서로 다른 이슈 {item.issueCount}건</small><span className="ib-rule-actions"><button type="button" onClick={() => void showPreview(item)}>영향 보기</button><button type="button" onClick={() => void approve(item)}>승인</button></span></div>)}{preview && <div className={`ib-rule-preview ${preview.riskLevel === "CAUTION" ? "caution" : ""}`}><header><strong>‘{preview.pattern}’ 적용 예상</strong><button type="button" onClick={() => setPreview(null)}>닫기</button></header>{preview.warnings.length > 0 && <div className="ib-rule-warnings">{preview.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}<div className="ib-rule-preview-stats"><span>일치 이슈 <b>{preview.issueCount}</b></span><span>연결 기사 <b>{preview.articleCount}</b></span><span>핵심 후보 <b>{preview.coreCandidateCount}</b></span></div>{preview.issues.length === 0 ? <p>현재 기간에 영향을 받는 이슈가 없습니다.</p> : <ul>{preview.issues.map((issue) => <li key={issue.issueId}><em>{issue.category}</em><span>{issue.title}</span><small>{issue.coreCandidate ? "핵심 후보 제외" : `관찰 이슈 · 기사 ${issue.articleCount}건`}</small></li>)}</ul>}{preview.riskLevel === "CAUTION" && <button className="ib-confirm-caution" type="button" onClick={() => void confirmCaution()}>영향을 확인했으며 승인</button>}</div>}</section>}
    {activeRules.length > 0 && <section className="ib-rule-section active"><h4>적용 중인 규칙</h4>{activeRules.map((rule) => <div key={rule.id}><span>{REASON_LABEL[rule.reason]}</span><strong>‘{rule.pattern}’ 포함</strong><small>{rule.impact.riskLevel === "CAUTION" ? `주의 · 핵심 ${rule.impact.coreCandidateCount}개 영향` : "정상 범위"}</small><button type="button" onClick={() => void deactivate(rule.id)}>해제</button></div>)}</section>}
    {history.length > 0 && <section className="ib-rule-history"><h4>최근 변경 이력</h4>{history.map((entry) => <div key={entry.id}><span className={`action ${entry.action.toLowerCase()}`}>{ACTION_LABEL[entry.action]}</span><strong>‘{entry.pattern}’</strong><small>{entry.actorName} · {new Date(entry.createdAt).toLocaleString("ko-KR")}</small><em>당시 핵심 {entry.coreCandidateCount} · 이슈 {entry.issueCount} · 기사 {entry.articleCount}</em></div>)}</section>}
  </details>;
}
