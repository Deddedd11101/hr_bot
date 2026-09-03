export type EmployeeItem = {
  id: number;
  full_name: string;
  chat_id: string;
  chat_handle: string;
  chat_link?: string | null;
  position: string;
  status_label: string;
  candidate_work_stage_label: string;
  planned_scenario_title: string;
  first_workday: string | null;
  first_workday_label: string;
  test_task_due_at: string | null;
  test_task_due_at_label: string;
  workdays: number;
  edit_url: string;
  react_edit_url: string;
  list_kind: "employees" | "candidates";
};

export type EmployeesMeta = {
  active_tab: "employees" | "candidates";
  list_title: string;
  empty_message: string;
  create_button_label: string;
  create_modal_title: string;
  create_intro: string;
  first_workday_label: string;
  default_employee_stage: string;
  list_kind: "employees" | "candidates";
  classic_page_url: string;
};

export type EmployeesPayload = {
  meta: EmployeesMeta;
  items: EmployeeItem[];
};

export type CreatePayload = {
  meta: EmployeesMeta;
  item: EmployeeItem | null;
};

export type Option = {
  value: string;
  label: string;
};

export type ListKind = "employees" | "candidates";
export type ViewMode = "cards" | "table";

export type { ColumnKey, SortDirection, SortField } from "./data";
