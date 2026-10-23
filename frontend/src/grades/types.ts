export type CatalogItem = { id: number; name: string; sort_order: number; active: boolean };
export type Grade = CatalogItem & { slug: string; rank: number };
export type Specialization = CatalogItem & { slug: string; description: string; position_slug: string | null; skill_ids_json?: string | null };
export type Skill = CatalogItem & { category_id: number; complexity: number; revision: number };
export type Catalog = {
  grades: Grade[];
  specializations: Specialization[];
  categories: CatalogItem[];
  skills: Skill[];
  importances: { id: number; skill_id: number; specialization_id: number; importance: number }[];
  expectations: { id: number; skill_id: number; specialization_id: number; grade_id: number; level: number }[];
};
export type Workspace = Catalog & { positions: { slug: string; name?: string; title?: string; label?: string; active?: boolean }[] };
export type EntityKind = "grades" | "specializations" | "categories" | "skills";
export type Profile = { specialization_id: number | null; current_grade_id: number | null; target_grade_id: number | null; target_specialization_id: number | null };
export type Score = { skillId: number; skillName: string; categoryId: number; categoryName: string; importance: number; currentLevel: number; targetLevel: number; assessed?: boolean };
export type Assessment = Profile & {
  id: number; employee_id: number; status: "draft" | "final"; created_at: string; finalized_at: string | null;
  catalog: Catalog;
  scores: Score[];
  categories: { categoryId: number; categoryName: string; current: number; target: number }[];
  progress: number | null;
  gaps: (Score & { gap: number; weightedGap: number })[];
  goal_options: { value: string; label: string }[];
  review_mode?: string; matrix_version?: string;
  import_source?: {filename: string; sheet: string; review_date?: string | null} | null;
};
export type EmployeeGrade = {
  employee_id: number; profile: Profile | null; suggested_specialization_id: number | null;
  grades: Grade[]; specializations: Specialization[];
  assessments: { id: number; status: "draft" | "final"; created_at: string; finalized_at: string | null }[];
  latest_final: Assessment | null;
  decisions: { id: number; labels_json: string; comment: string | null; created_at: string }[];
};
export type MatrixRow = { skill_id: number; importance: number; levels: Record<string, number> };
