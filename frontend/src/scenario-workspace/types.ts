export type ScenarioSummary = {
  id: number;
  title: string;
  description: string;
  employee_scope: string;
  created_at: string | null;
  updated_at: string | null;
  candidate_work_stage_trigger: string;
  role_scope_label: string;
  employee_scope_label: string;
  trigger_mode_label: string;
  steps_count: number;
  classic_url: string;
  workspace_url: string;
};

export type WorkspaceStep = {
  id: number;
  step_key: string;
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
  return_to_step_key: string;
  notify_on_send: boolean;
  notify_on_send_text: string;
  notify_on_send_recipient_ids: string;
  notify_on_send_recipient_scope: string;
  step_send_notifications: WorkspaceStepSendNotificationRule[];
  button_notifications: WorkspaceButtonNotification[];
  branch_items: WorkspaceBranchSlot[];
  chain_steps: WorkspaceStep[];
};

export type WorkspaceStepSendNotificationRule = {
  rule_index: number;
  message_text: string;
  recipient_ids: string;
  recipient_scope: string;
};

export type WorkspaceButtonNotificationRule = {
  rule_index: number;
  message_text: string;
  recipient_ids: string;
  recipient_scope: string;
};

export type WorkspaceButtonNotification = {
  option_index: number;
  option_label: string;
  message_text: string;
  recipient_ids: string;
  recipient_scope: string;
  rules: WorkspaceButtonNotificationRule[];
};

export type WorkspaceBranchSlot = {
  id: string;
  kind: "branch_slot";
  option_index: number;
  label: string;
  has_step: boolean;
  step: WorkspaceStep | null;
};

export type WorkspaceGraphNode = {
  id: string;
  step_id: number | null;
  step_key: string;
  kind: "step" | "branch_step" | "chain_step" | "branch_slot" | "launch_target";
  title: string;
  text_preview: string;
  response_type: string;
  response_label: string;
  has_attachment: boolean;
  has_notifications: boolean;
  waits_for_response: boolean;
  send_mode: string;
  launch_scenario_key: string;
  is_placeholder: boolean;
  is_terminal: boolean;
};

export type WorkspaceGraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: "next" | "chain" | "branch_option" | "return_to_root" | "launch_scenario";
  label: string;
};

export type WorkspaceGraph = {
  nodes: WorkspaceGraphNode[];
  edges: WorkspaceGraphEdge[];
  meta: {
    node_count: number;
    edge_count: number;
    has_branching: boolean;
    has_return_edges: boolean;
    has_launch_edges: boolean;
    has_placeholders: boolean;
  };
};

export type WorkspaceData = {
  scenario: {
    id: number;
    scenario_kind: "scenario" | "survey";
    title: string;
    description: string;
    role_scope: string;
    role_scope_label: string;
    employee_scope: string;
    employee_scope_label: string;
    recipient_mode: string;
    recipient_mode_label: string;
    trigger_mode: string;
    candidate_work_stage_trigger: string;
    trigger_mode_label: string;
    target_employee_id: number | null;
    classic_url: string;
  };
  root_steps: WorkspaceStep[];
  graph: WorkspaceGraph;
  stats: {
    steps_count: number;
  };
  response_type_labels: Record<string, string>;
  role_scope_labels: Record<string, string>;
  employee_scope_labels: Record<string, string>;
  recipient_mode_labels: Record<string, string>;
  trigger_mode_labels: Record<string, string>;
  candidate_work_stage_labels: Record<string, string>;
  target_field_labels: Record<string, string>;
  send_mode_labels: Record<string, string>;
  notification_recipient_scope_labels: Record<string, string>;
  document_tag_titles: string[];
  employee_options: Array<{ id: number; label: string; kind: string }>;
  notification_recipient_options: Array<{ token: string; label: string; description: string; kind: string }>;
  available_scenarios: Array<{ value: string; label: string }>;
};

export type WorkspaceRootStepOption = {
  value: string;
  label: string;
};

export type WorkspacePayload = {
  kind: "scenario" | "survey";
  item_label: string;
  scenarios: ScenarioSummary[];
  selected_scenario_id: number | null;
  workspace: WorkspaceData | null;
};

export type Container =
  | {
      type: "root";
      key: string;
      sourceKey: null;
      ownerStepId: null;
      title: string;
      subtitle: string;
      crumbLabel: string;
      items: WorkspaceStep[];
    }
  | {
      type: "branches" | "chain";
      key: string;
      sourceKey: string;
      ownerStepId: number;
      title: string;
      subtitle: string;
      crumbLabel: string;
      items: Array<WorkspaceStep | WorkspaceBranchSlot>;
    };

export type WorkspaceItem = WorkspaceStep | WorkspaceBranchSlot;

export type SingleOption = {
  value: string;
  label: string;
};

export type ScenarioSettingsForm = {
  title: string;
  description: string;
  role_scope: string;
  employee_scope: string;
  recipient_mode: string;
  trigger_mode: string;
  candidate_work_stage_trigger: string;
  target_employee_id: string;
};
