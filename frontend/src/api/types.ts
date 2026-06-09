// TypeScript mirrors of backend Pydantic schemas

export interface AppConfig {
  naukri_email: string;
  naukri_password: string;       // "***" when set
  linkedin_email: string;
  linkedin_password: string;     // "***" when set
  azure_openai_endpoint: string;
  azure_openai_api_key: string;  // "***" when set
  azure_deployment_name: string;
  confidence_threshold: number;
  port_num: number;
  max_jobs_per_hour: number;
  max_jobs_per_day: number;
  is_configured: boolean;
}

export interface CVProfile {
  id: number;
  name: string;
  email: string;
  phone: string;
  skills: string[];
  job_titles: string[];
  experience_years: number;
  education: string[];
  summary: string;
  pdf_path: string;
  created_at: string;
  is_active: boolean;
}

export interface SessionStartRequest {
  platform: "naukri" | "linkedin" | "both";
  mode: "search" | "search_and_apply";
  location: string;
  job_target: number;
  confidence_threshold: number;
  keywords: string[];
}

export interface SessionRecord {
  id: number;
  platform: string;
  mode: string;
  location: string;
  job_target: number;
  confidence_threshold: number;
  keywords: string[];
  started_at: string;
  ended_at: string | null;
  applied: number;
  skipped: number;
  errors: number;
  status: string;
}

export interface ApplicationRecord {
  id: number;
  session_id: number | null;
  platform: string;
  job_title: string;
  company: string;
  job_url: string;
  score: number;
  location: string;
  experience_required: string;
  salary: string;
  key_skills: string[];
  matched_skills: string[];
  missing_skills: string[];
  external_site_url: string;
  status: "applied" | "skipped" | "skipped_external" | "error";
  error_message: string | null;
  timestamp: string;
}

export interface PaginatedApplications {
  total: number;
  page: number;
  per_page: number;
  records: ApplicationRecord[];
}

// ── WebSocket event union ──────────────────────────────────────────────────────

export type WSEvent =
  | { type: "ping" }
  | { type: "session_config"; platform: string; target: number; location: string; threshold: number }
  | { type: "cv_parsed"; name: string; experience_years: number; titles: string[]; skills: string[] }
  | { type: "login"; platform: string; ok: boolean; error?: string }
  | { type: "search"; platform: string; keywords: string[]; count: number }
  | { type: "job_start"; idx: number; total: number; title: string; company: string; url: string }
  | { type: "job_skip"; reason: string; title: string }
  | { type: "job_details"; exp_required: string; salary: string; posted_date: string; applicants: string; logo_url: string }
  | { type: "llm_score"; score: number; threshold: number; rationale: string; recommendation: string; matched: string[]; missing: string[] }
  | { type: "apply_start"; title: string; company: string }
  | { type: "apply_result"; status: string; title: string; external_url: string; error: string }
  | { type: "session_end"; applied: number; target: number; skipped: number; errors: number }
  | { type: "rate_limit"; msg: string }
  | { type: "error"; msg: string; traceback?: string }
  | { type: "log"; level: string; msg: string };
