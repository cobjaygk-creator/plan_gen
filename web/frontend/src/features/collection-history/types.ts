export interface CollectedEvent {
  title: string | null;
  url: string | null;
  endsOn: string | null;
  active: boolean;
  collectedAt: string;
}

export interface DailyCollection {
  date: string;
  count: number;
  events: CollectedEvent[];
}

export interface GameCollection {
  game: string;
  publisher: string | null;
  total: number;
  active: number;
  lastSuccessAt: string | null;
  firstCollectedAt: string | null;
  d1: number;
  d7: number;
  d30: number;
  ytd: number;
  daily: DailyCollection[];
}

export interface CollectionTotals {
  d1: number;
  d7: number;
  d30: number;
  ytd: number;
  total: number;
  active: number;
}

export interface CollectionHistory {
  generatedAt: string;
  today: string;
  yearStart: string;
  totals: CollectionTotals;
  games: GameCollection[];
}
