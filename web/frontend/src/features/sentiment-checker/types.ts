export type Sentiment = "POSITIVE" | "NEUTRAL" | "NEGATIVE";

export interface RepresentativePost {
  title: string;
  url: string;
  source: string;
  created_at: string | null;
}

export interface Issue {
  key: string;
  title: string;
  category: string;
  mentions: number;
  growth: number;
  positive: number;
  neutral: number;
  negative: number;
  representative: RepresentativePost[];
}

export interface Observation {
  name: string;
  count: number;
  reason: string;
}

export interface SourceStat {
  source: string;
  count: number;
  score: number;
}

export interface CategoryStat {
  name: string;
  count: number;
}

export interface TimelinePoint {
  observed_at: string;
  score: number;
  count: number;
}

export interface ReferenceLink {
  title: string;
  url: string;
  published_at: string | null;
  relation: string;
}

export interface RecentPost {
  title: string;
  url: string;
  source: string;
  created_at: string | null;
  sentiment: Sentiment;
  category: string;
}

export interface Metrics {
  stored_total: number;
  collected: number;
  eligible: number;
  issue_count: number;
  ai_analyzed: number;
  ai_pending: number;
  analysis_coverage: number;
  score: number;
  change: number;
  positive: number;
  neutral: number;
  negative: number;
}

export interface CommentMetrics {
  count: number;
  positive: number;
  neutral: number;
  negative: number;
  agree: number;
  disagree: number;
  stance_neutral: number;
}

export interface DashboardData {
  generated_at: string;
  period_hours: number;
  analysis_basis: "SELECTED_PERIOD" | "RECENT_7_DAYS" | "ALL_STORED";
  analysis_count: number;
  metrics: Metrics;
  brief: string;
  comment_metrics: CommentMetrics;
  issues: Issue[];
  spikes: Issue[];
  sources: SourceStat[];
  categories: CategoryStat[];
  observations: Observation[];
  timeline: TimelinePoint[];
  references: ReferenceLink[];
  recent: RecentPost[];
}

export interface DetailTimelinePoint {
  date: string;
  count: number;
}

export interface DetailComment {
  content: string;
  created_at: string | null;
  sentiment: Sentiment;
  stance: "AGREE" | "DISAGREE" | "NEUTRAL";
  upvotes: number;
}

export interface DetailPost {
  title: string;
  url: string;
  source: string;
  created_at: string | null;
  views: number;
  comments: number;
  upvotes: number;
  sentiment: Sentiment;
  excerpt: string;
}

export interface CommentReaction {
  count: number;
  agree: number;
  disagree: number;
  neutral: number;
  positive: number;
  negative: number;
}

export interface IssueDetail {
  key: string;
  title: string;
  category: string;
  mentions: number;
  sentiment: { positive: number; neutral: number; negative: number };
  timeline: DetailTimelinePoint[];
  interpretation: string;
  ai_rationales: string[];
  comment_reaction: CommentReaction;
  comments: DetailComment[];
  references: ReferenceLink[];
  posts: DetailPost[];
}
