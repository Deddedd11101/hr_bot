export type ScenarioSummary = {
  id: number;
  title: string;
  description: string;
  role_scope_label: string;
  trigger_mode_label: string;
  steps_count: number;
  classic_url: string;
  workspace_url: string;
};

export type WorkspaceStep = {
  id: number;
  kind: "step" | "branch_step" | "chain_step";
  title: string;
  text: string;
  text_preview: string;
  response_type: string;
  response_label: string;
  button_options: string[];
  has_attachment: boolean;
  attachment_filename: string;
  send_employee_card: boolean;
  send_mode: string;
  send_mode_label: string;
  send_time: string;
  day_offset_workdays: number;
  target_field: string;
  target_field_label: string;
  launch_scenario_key: string;
  notify_on_send: boolean;
  notify_on_send_text: string;
  notify_on_send_recipient_ids: string;
  notify_on_send_recipient_scope: string;
  branch_items: WorkspaceBranchSlot[];
  chain_steps: WorkspaceStep[];
};

export type WorkspaceBranchSlot = {
  id: string;
  kind: "branch_slot";
  option_index: number;
  label: string;
  has_step: boolean;
  step: WorkspaceStep | null;
};

export type WorkspaceData = {
  scenario: {
    id: number;
    title: string;
    description: string;
    role_scope_label: string;
    trigger_mode_label: string;
    classic_url: string;
  };
  root_steps: WorkspaceStep[];
  stats: {
    steps_count: number;
  };
  response_type_labels: Record<string, string>;
  target_field_labels: Record<string, string>;
  send_mode_labels: Record<string, string>;
  notification_recipient_scope_labels: Record<string, string>;
  document_tag_titles: string[];
  employee_options: Array<{ id: number; label: string; kind: string }>;
  available_scenarios: Array<{ value: string; label: string }>;
};

export type WorkspacePayload = {
  scenarios: ScenarioSummary[];
  selected_scenario_id: number | null;
  workspace: WorkspaceData | null;
};
