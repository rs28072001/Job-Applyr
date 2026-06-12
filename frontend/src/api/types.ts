// TypeScript mirrors of backend Pydantic schemas

export type OutreachMode = "off" | "draft_only" | "send_after_approval";
export type DatePostedFilter = "any" | "24h" | "3d" | "7d" | "14d";

export type AppStatus =
  | "queued" | "fetching" | "scoring" | "skipped" | "applying" | "applied"
  | "applied_pending_confirmation" | "saved"
  | "manual_review" | "email_drafted" | "email_sent" | "failed" | "stopped";

export type JobClassification =
  | "platform_easy_apply" | "platform_internal_apply" | "external_ats"
  | "email_outreach_candidate" | "manual_review" | "unsupported" | "";

export interface AppConfig {
  naukri_email: string;
  naukri_password: string;       // "***" when set
  linkedin_email: string;
  linkedin_password: string;     // "***" when set
  azure_openai_endpoint: string;
  azure_openai_api_key: string;  // "***" when set
  azure_deployment_name: string;
  ai_provider: "azure" | "openai" | "gemini" | "groq" | "openrouter";
  openai_api_key: string;        // "***" when set
  openai_model: string;
  gemini_api_key: string;        // "***" when set
  gemini_model: string;
  groq_api_key: string;          // "***" when set
  groq_model: string;
  openrouter_api_key: string;    // "***" when set
  openrouter_model: string;
  openrouter_base_url: string;
  confidence_threshold: number;
  port_num: number;
  max_jobs_per_hour: number;
  max_jobs_per_day: number;
  easy_apply_only: boolean;
  include_external_review: boolean;
  outreach_mode: OutreachMode;
  hide_previously_skipped: boolean;
  auto_ignore_skipped: boolean;
  date_posted_filter: DatePostedFilter;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;         // "***" when set
  smtp_from: string;
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
  easy_apply_only: boolean;
  include_external_review: boolean;
  outreach_mode: OutreachMode;
  hide_previously_skipped: boolean;
  auto_ignore_skipped: boolean;
  date_posted_filter: DatePostedFilter;
}

export interface SessionRecord {
  id: number;
  platform: string;
  mode: string;
  location: string;
  job_target: number;
  confidence_threshold: number;
  keywords: string[];
  easy_apply_only: boolean;
  include_external_review: boolean;
  outreach_mode: OutreachMode;
  hide_previously_skipped: boolean;
  auto_ignore_skipped: boolean;
  date_posted_filter: DatePostedFilter;
  started_at: string;
  ended_at: string | null;
  applied: number;
  skipped: number;
  errors: number;
  status: string;
}

export interface SessionStatusResponse {
  is_running: boolean;
  session_id: number | null;
  started_at: string | null;
  counts: Record<string, number>;
  session: SessionRecord | null;
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
  status: AppStatus;
  classification: JobClassification;
  failure_reason: string;
  recommendation: string;
  rationale: string;
  job_description: string;
  error_message: string | null;
  timestamp: string;
  updated_at: string | null;
}

export interface PaginatedApplications {
  total: number;
  page: number;
  per_page: number;
  records: ApplicationRecord[];
}

// ── Outreach & Review queue ────────────────────────────────────────────────

export interface OutreachDraft {
  id: number;
  application_id: number | null;
  session_id: number | null;
  recruiter_email: string;
  email_source: string;
  email_source_url: string;
  subject: string;
  body: string;
  status: "draft" | "approved" | "sent" | "discarded";
  created_at: string;
  updated_at: string | null;
  sent_at: string | null;
  job_title: string;
  company: string;
  job_url: string;
}

export interface ReviewQueueResponse {
  manual_review: ApplicationRecord[];   // "Needs Attention"
  drafts: OutreachDraft[];
  skipped: ApplicationRecord[];         // recent skips with reasons
  saved: ApplicationRecord[];           // auto-saved external jobs
}

export interface IgnoredJob {
  id: number;
  ignored_at: string;
  platform: string;
  company: string;
  job_title: string;
  job_url: string;
  job_fingerprint: string;
  ignore_type: string;
  ignore_reason: string;
  score: number;
  status: string;
  expires_at: string | null;
}

export interface IgnoredJobsResponse {
  total: number;
  records: IgnoredJob[];
}

// ── WebSocket event union ────────────────────────────────────────────────────

export type WSEvent =
  | { type: "ping" }
  | { type: "session_config"; platform: string; target: number; location: string; threshold: number }
  | { type: "cv_parsed"; name: string; experience_years: number; titles: string[]; skills: string[] }
  | { type: "login"; platform: string; ok: boolean; error?: string }
  | { type: "search"; platform: string; keywords: string[]; count: number }
  | { type: "job_start"; idx: number; total: number; title: string; company: string; url: string }
  | { type: "job_skip"; reason: string; title: string }
  | { type: "job_details"; exp_required: string; salary: string; posted_date: string; applicants: string; logo_url: string }
  | { type: "job_status"; application_id: number; status: AppStatus; failure_reason: string; classification: JobClassification; title: string; company: string }
  | { type: "job_classified"; application_id: number; classification: JobClassification; title: string }
  | { type: "outreach_drafted"; application_id: number; draft_id: number; email: string; source_url: string }
  | { type: "backoff"; reason: string; seconds: number }
  | { type: "llm_score"; score: number; threshold: number; rationale: string; recommendation: string; matched: string[]; missing: string[] }
  | { type: "apply_start"; title: string; company: string }
  | { type: "apply_result"; status: string; title: string; external_url: string; error: string }
  | { type: "session_end"; applied: number; target: number; skipped: number; errors: number }
  | { type: "session_stopped"; session_id: number }
  | { type: "rate_limit"; msg: string }
  | { type: "error"; msg: string; traceback?: string }
  | { type: "log"; level: string; msg: string };
