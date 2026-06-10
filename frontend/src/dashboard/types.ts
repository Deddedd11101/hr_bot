export type DashboardStats = {
  candidates_without_channel: number;
  recent_telegram_links: number;
  recent_inbound_files: number;
  scheduled_next_7_days: number;
};

export type DashboardEvent = {
  id: string;
  kind: string;
  kind_label: string;
  title: string;
  subtitle: string;
  scheduled_at: string;
  scheduled_at_label: string;
  date_label: string;
  recipient_count: number;
  href: string;
};

export type TelegramLink = {
  employee_id: number;
  full_name: string;
  channel: string;
  handle_or_id: string;
  linked_at: string;
  linked_at_label: string;
  href: string;
};

export type InboundFile = {
  id: number;
  employee_id: number;
  full_name: string;
  filename: string;
  created_at: string;
  created_at_label: string;
  href: string;
};

export type AttentionItem = {
  id: string;
  kind: string;
  severity: "warning" | "danger" | "info";
  title: string;
  subtitle: string;
  href: string;
};

export type ModuleLink = {
  key: string;
  title: string;
  description: string;
  href: string;
};

export type DashboardPayload = {
  meta: {
    recent_days: number;
    upcoming_days: number;
    stat_upcoming_days: number;
    generated_at: string;
  };
  stats: DashboardStats;
  upcoming_events: DashboardEvent[];
  telegram_links: TelegramLink[];
  inbound_files: InboundFile[];
  attention_items: AttentionItem[];
  module_links: ModuleLink[];
};
