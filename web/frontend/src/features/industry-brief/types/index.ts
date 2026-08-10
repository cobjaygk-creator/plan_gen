export type Direction = "up" | "flat" | "down";
export type Lifecycle = "EMERGING" | "GROWING" | "PEAK" | "STABLE" | "DECLINING";
export type ConfidenceLevel = "STRONG" | "MODERATE" | "WEAK";
export type IssueCategory = "GAME" | "AI";
export type Importance = "높음" | "보통" | "낮음";

export interface ChangeItem {
  direction: Direction;
  topic: string;
  description: string;
}

export interface WatchItem {
  rank: number;
  topic: string;
  description: string;
}

export interface IndustryPanel {
  headline: string;
  briefing: string[]; // paragraphs
  changes: ChangeItem[];
  watchList: WatchItem[];
}

export interface CrossInsight {
  hasSignal: boolean;
  summary: string[];
}

export interface Signal {
  topic: string;
  direction: Direction;
  weight: number; // 0-100, relative bar width
}

export interface NewTodayItem {
  topic: string;
  description: string;
  articleCount: number;
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
  independentSources: number;
  officialCount: number;
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
  sources: SourceItem[];
}

export interface IndustryBrief {
  briefDate: string;
  generatedAt: string;
  periodLabel: string;
  articleCount: number;
  game: IndustryPanel;
  ai: IndustryPanel;
  crossInsight: CrossInsight;
  signals: Signal[];
  newToday: NewTodayItem[];
  issues: IssueCard[];
}
