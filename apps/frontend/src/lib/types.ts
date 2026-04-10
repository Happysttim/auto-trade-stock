export type OrderProposal = {
  id: number;
  signal_ids: number[];
  symbol: string;
  company_name: string;
  proposal_type: "buy" | "sell";
  quantity: number;
  reference_price: number;
  target_amount: number;
  score: number;
  hold_days: number;
  rationale: string;
  status: string;
  reason: string | null;
  broker_order_id: string | null;
  last_error: string | null;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
};

export type TradeRecord = {
  id: number;
  symbol: string;
  company_name: string;
  trade_type: "buy" | "sell";
  quantity: number;
  price: number;
  total_amount: number;
  pnl: number | null;
  status: string;
  broker_order_id: string | null;
  signal_id: number | null;
  position_ids: number[];
  notes: string | null;
  executed_at: string;
};

export type HoldingRecord = {
  id: number;
  account_no: string | null;
  symbol: string;
  company_name: string;
  quantity: number;
  available_quantity: number;
  average_price: number;
  current_price: number;
  market_value: number;
  pnl: number | null;
  updated_at: string;
};

export type LogRecord = {
  id: number;
  event_type: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type SignalRecord = {
  id: number;
  symbol: string;
  company_name: string;
  keyword: string;
  score: number;
  signal_type: "buy" | "sell" | "hold";
  allocation_ratio: number;
  hold_days: number;
  recent_volume: number;
  volume_ratio: number;
  suspicious_volume: boolean;
  recorded_date: string;
  rationale: string;
  source_names: string[];
  source_urls: string[];
  source_article_ids: string[];
  created_at: string;
  processed: boolean;
  processed_at: string | null;
  execution_status: string;
};

export type ServiceStatus = {
  service_now: string;
  operating_window: boolean;
  market_open: boolean;
  last_news_cycle_at: string | null;
  last_ai_summary: string | null;
  latest_signal_count: number;
  pending_proposal_count: number;
  holding_count: number;
  last_holdings_sync_at: string | null;
  active_account_no: string | null;
  last_processed_signal_id: string | null;
};

export type DashboardData = {
  status: ServiceStatus;
  proposals: OrderProposal[];
  holdings: HoldingRecord[];
  trades: TradeRecord[];
  logs: LogRecord[];
  signals: SignalRecord[];
};

export type KeywordArticle = {
  article_id: string;
  title: string;
  source_name: string;
  url: string;
  published_at: string;
  summary: string;
  region: string;
  topic: string;
};

export type KeywordRecommendation = {
  symbol: string;
  company_name: string;
  keyword: string;
  score: number;
  signal_type: "buy" | "sell" | "hold";
  allocation_ratio: number;
  hold_days: number;
  recent_volume: number;
  volume_ratio: number;
  suspicious_volume: boolean;
  stable_volume: boolean;
  recorded_date: string;
  rationale: string;
  reference_price: number | null;
  suggested_quantity: number | null;
  suggested_amount: number | null;
  max_affordable_quantity: number;
  currently_held_quantity: number;
  executable: boolean;
  execution_block_reason: string | null;
  registered_proposal_id: number | null;
  source_names: string[];
  source_urls: string[];
};

export type KeywordAnalysisAccount = {
  account_no: string | null;
  cash_balance: number;
  holdings_value: number;
  total_equity: number;
  available_buying_power: number;
  holding_count: number;
};

export type KeywordAnalysisResult = {
  status: "ok";
  keyword: string;
  analyzed_at: string;
  summary: string;
  skip_reason: string | null;
  articles: KeywordArticle[];
  recommendations: KeywordRecommendation[];
  registered_proposals: number[];
  account: KeywordAnalysisAccount;
};
