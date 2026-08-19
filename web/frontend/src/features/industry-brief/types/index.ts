export type Direction = "up" | "flat" | "down";
export type Lifecycle = "EMERGING" | "GROWING" | "PEAK" | "STABLE" | "DECLINING";
export type ConfidenceLevel = "STRONG" | "MODERATE" | "WEAK";
export type IssueCategory = "GAME" | "AI";
export type Importance = "높음" | "보통" | "낮음";

export interface ChangeItem {
  direction: Direction;
  topic: string;
  description: string;
  sources?: SourceItem[];
}

export interface WatchItem {
  rank: number;
  topic: string;
  description: string;
  sources?: SourceItem[];
}

export interface IndustryPanel {
  headline: string;
  keySummaries?: string[];
  keySummaryDetails?: Array<{
    issueId?: number;
    text: string;
    articleCount: number;
    independentSources: number;
    officialCount: number;
    activeDays: number;
    selectionReason: string;
    confidence: string;
    scoreBreakdown?: {
      evidence: number;
      coverage: number;
      importance: number;
      persistence: number;
      momentum: number;
      editorialAdjustment: number;
      userFeedback: number;
      approvedRule: number;
      total: number;
    };
  }>;
  observations?: Array<{
    title: string;
    description: string;
    statusLabel: string;
    selectionReason: string;
    sources: SourceItem[];
  }>;
  promotions?: Array<{
    title: string;
    summary: string;
    promotedAt: string;
    evidenceCount: number;
    reason: string;
  }>;
  closedObservations?: Array<{
    title: string;
    closedAt: string;
    reason: string;
  }>;
  briefing: string[]; // paragraphs
  changes: ChangeItem[];
  watchList: WatchItem[];
}

export interface CrossInsight {
  hasSignal: boolean;
  summary: string[];
  opinion: string;
}

export interface SignalEvidence {
  outlet: string;
  title: string;
  url: string;
}

export interface Signal {
  topic: string;
  direction: Direction;
  weight: number;
  kind: "INDUSTRY" | "COMPANY" | "PRODUCT" | "PROJECT";
  kindLabel: string;
  eventType?: string;
  priorityReason?: string;
  domain?: "GAME" | "AI" | "GAME_AI";
  state: "NEW" | "EXPANDING" | "GROWING" | "CONTINUING" | "DECLINING";
  stateLabel: string;
  todayCount: number;
  baselineAverage: number;
  sourceCount: number;
  reason: string;
  evidence: SignalEvidence[];
}

export interface NewTodayItem {
  topic: string;
  description: string;
  articleCount: number;
  analysisStats?: AnalysisStats;
  independentSources: number;
  officialCount: number;
}

export interface SourceItem {
  outlet: string;
  title: string;
  publishedAgo: string;
  url: string;
}

export interface Confidence {
  level: ConfidenceLevel;
  articleCount: number;
  analysisStats?: AnalysisStats;
  independentSources: number;
  officialCount: number;
}

export interface EvidenceQuality {
  verificationStatus: "CORROBORATED" | "OFFICIAL_ONLY" | "DISCOVERY_ONLY" | "SINGLE_SOURCE";
  synthesisEligible: boolean;
  establishedMediaCount: number;
  discoveryMediaCount: number;
  reason: string;
}

export interface IssueCard {
  id: string;
  category: IssueCategory;
  importance: Importance;
  title: string;
  summary: string;
  whyItMatters: string;
  lifecycle: Lifecycle;
  relatedBriefing: string;
  confidence: Confidence;
  evidenceQuality?: EvidenceQuality;
  sources: SourceItem[];
}

export interface RecommendedArticle {
  category: IssueCategory;
  title: string;
  url: string;
  publishedDate: string;
}
export interface AnalysisStats {
  collected: number;
  analyzed: number;
  pending?: number;
  completionRate?: number;
  analysisStatus?: "COMPLETE" | "PARTIAL" | "INSUFFICIENT";
  relevant: number;
  issues: number;
  verifiedIssues?: number;
  singleSourceIssues?: number;
}

export interface LandscapeIssue {
  key: string;
  title: string;
  referenceCount: number;
  recentArticleCount: number;
  firstObservedAt: string | null;
  axes: string[];
  priorityScore: number;
  priorityReasons: string[];
}

export interface LandscapeDomain {
  key: "GAME" | "AI" | "GAME_AI";
  label: string;
  issues: LandscapeIssue[];
}

export interface IndustryLandscape {
  referenceArticleCount: number;
  domains: LandscapeDomain[];
}
export interface LandscapeEvidenceArticle {
  title: string;
  url: string | null;
  source: string | null;
  publishedAt: string | null;
}

export interface LandscapeTimelinePoint {
  month: string;
  count: number;
}

export interface LandscapeIssueDetail {
  key: string;
  title: string;
  historicalStart: string | null;
  historicalCount: number;
  recentCount: number;
  historicalEnd: string | null;
  changeSummary: string;
  timeline: LandscapeTimelinePoint[];
  historicalArticles: LandscapeEvidenceArticle[];
  recentArticles: LandscapeEvidenceArticle[];
}
export interface ComparisonTopic {
  topic: string;
  count?: number;
  koreaCount?: number;
  globalCount?: number;
}

export interface MarketComparisonPanel {
  category: "GAME" | "AI";
  label: string;
  koreaArticleCount: number;
  globalArticleCount: number;
  koreaFocus: ComparisonTopic[];
  globalFocus: ComparisonTopic[];
  sharedTopics: ComparisonTopic[];
}
export interface PolicyUpdate {
  id: string;
  type: "REGULATION" | "ENFORCEMENT" | "FUNDING" | "TALENT" | "GLOBAL" | "PARTNERSHIP" | "PROGRAM";
  typeLabel: string;
  title: string;
  source: string;
  url: string;
  publishedDate: string;
  effectiveDate: string | null;
  target: string;
  action: string;
  implication: string;
  responseChecklist: string[];
  priorityScore: number;
  priorityLabel: "긴급 확인" | "우선 확인" | "관찰";
  urgencyLabel: string;
  policyKey: string;
  changeType: "NEW" | "REVISION" | "STAGE_CHANGE" | "FOLLOW_UP";
  changeLabel: string;
  historyCount: number;
  history: Array<{ title: string; url: string; publishedDate: string; stageLabel: string }>;
  selectionReason: string;
  evidenceSentence: string;
}
export interface IndustryBrief {
  briefDate: string;
  generatedAt: string;
  periodLabel: string;
  articleCount: number;
  analysisStats?: AnalysisStats;
  analytics?: {
    interest: { labels: string[]; series: Array<{ name: string; originalTitle: string; category: "GAME" | "AI"; values: number[] }>; bucket: string };
    topicShare: Array<{ topic: string; game: number; ai: number }>;
  };
  game: IndustryPanel;
  ai: IndustryPanel;
  crossInsight: CrossInsight;
  recommendedArticles?: RecommendedArticle[];
  signals: Signal[];
  newToday: NewTodayItem[];
  issues: IssueCard[];
  landscape?: IndustryLandscape;
  marketComparison?: MarketComparisonPanel[];
  policyUpdates?: PolicyUpdate[];
  policyTimeline?: PolicyUpdate[];
}

