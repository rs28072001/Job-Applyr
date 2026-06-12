import { create } from "zustand";
import type { AppStatus, JobClassification, WSEvent } from "../api/types";

export interface JobEntry {
  appId?: number;            // backend application row id
  idx: number;
  total: number;
  title: string;
  company: string;
  url: string;
  score?: number;
  rationale?: string;
  matched?: string[];
  missing?: string[];
  recommendation?: string;
  status?: AppStatus | string;
  classification?: JobClassification;
  failure_reason?: string;
  external_url?: string;
  exp_required?: string;
  salary?: string;
  logo_url?: string;
}

export interface TimelineEntry {
  ts: string;
  level: string;  // info | success | warning | error
  msg: string;
}

export type SessionUIState = "idle" | "running" | "completed" | "stopped" | "failed";

interface SessionState {
  isRunning: boolean;
  uiState: SessionUIState;
  sessionId: number | null;
  loginStatus: Record<string, boolean>;
  searchCounts: Record<string, number>;
  jobs: JobEntry[];
  appliedCount: number;
  target: number;
  logs: TimelineEntry[];
  counts: Record<string, number>;   // persisted-row counts from the API

  handleEvent: (event: WSEvent) => void;
  setRunning: (running: boolean, sessionId?: number | null) => void;
  setStopped: () => void;
  setCounts: (counts: Record<string, number>) => void;
  reset: () => void;
}

const MAX_LOGS = 500;

export const useSessionStore = create<SessionState>((set) => ({
  isRunning: false,
  uiState: "idle",
  sessionId: null,
  loginStatus: {},
  searchCounts: {},
  jobs: [],
  appliedCount: 0,
  target: 0,
  logs: [],
  counts: {},

  setRunning: (running, sessionId = null) =>
    set((s) => ({
      isRunning: running,
      sessionId: sessionId ?? null,
      uiState: running ? "running" : s.uiState === "running" ? "completed" : s.uiState,
    })),

  setStopped: () =>
    set((state) => ({
      isRunning: false,
      uiState: "stopped",
      // Stop is immediate: any in-flight row flips to stopped in the UI too.
      jobs: state.jobs.map((j) =>
        j.status && ["queued", "fetching", "scoring", "applying"].includes(j.status)
          ? { ...j, status: "stopped", failure_reason: "session_stopped" }
          : j
      ),
      logs: addLog(state.logs, ts(), "warning", "Session stopped by user"),
    })),

  setCounts: (counts) => set({ counts }),

  reset: () =>
    set({
      isRunning: false,
      uiState: "idle",
      sessionId: null,
      loginStatus: {},
      searchCounts: {},
      jobs: [],
      appliedCount: 0,
      target: 0,
      logs: [],
      counts: {},
    }),

  handleEvent: (event) => {
    const now = ts();

    set((state) => {
      switch (event.type) {
        case "ping":
          return state;

        case "session_config":
          return { target: event.target, uiState: "running" as const, isRunning: true,
            logs: addLog(state.logs, now, "info",
              `Session started: ${event.platform} · target ${event.target} · ${event.location}`) };

        case "login":
          return {
            loginStatus: { ...state.loginStatus, [event.platform]: event.ok },
            logs: addLog(state.logs, now, event.ok ? "success" : "error",
              `${event.platform}: ${event.ok ? "logged in" : `login failed — ${event.error}`}`),
          };

        case "search":
          return {
            searchCounts: { ...state.searchCounts, [event.platform]: event.count },
            logs: addLog(state.logs, now, "info",
              `Found ${event.count} listings on ${event.platform}`),
          };

        case "job_start": {
          const newJob: JobEntry = {
            idx: event.idx, total: event.total,
            title: event.title, company: event.company, url: event.url,
            status: "queued",
          };
          return { jobs: [...state.jobs, newJob] };
        }

        case "job_details":
          return updateLastJob(state, { exp_required: event.exp_required, salary: event.salary, logo_url: event.logo_url });

        case "job_status": {
          const updates: Partial<JobEntry> = {
            appId: event.application_id,
            status: event.status,
            failure_reason: event.failure_reason || undefined,
            classification: event.classification || undefined,
          };
          const next = updateJobByIdOrLast(state, event.application_id, updates);
          const lvl = event.status === "applied" ? "success"
            : event.status === "failed" ? "error"
            : ["stopped", "manual_review"].includes(event.status) ? "warning" : "info";
          const terminal = ["applied", "skipped", "failed", "stopped", "manual_review", "email_drafted", "email_sent"];
          const logs = terminal.includes(event.status)
            ? addLog(state.logs, now, lvl,
                `${event.title || "Job"} → ${event.status.replace(/_/g, " ")}${event.failure_reason ? ` (${event.failure_reason.replace(/_/g, " ")})` : ""}`)
            : state.logs;
          return { ...next, logs };
        }

        case "job_classified":
          return updateJobByIdOrLast(state, event.application_id, {
            appId: event.application_id, classification: event.classification,
          });

        case "outreach_drafted":
          return {
            ...updateJobByIdOrLast(state, event.application_id, { status: "email_drafted" }),
            logs: addLog(state.logs, now, "info",
              `Email draft created for review → ${event.email} (not sent)`),
          };

        case "backoff":
          return { logs: addLog(state.logs, now, "warning",
            `Backing off ${Math.round(event.seconds)}s — ${event.reason}`) };

        case "llm_score":
          return {
            ...updateLastJob(state, {
              score: event.score, rationale: event.rationale,
              matched: event.matched, missing: event.missing,
              recommendation: event.recommendation,
            }),
            logs: addLog(state.logs, now, "info",
              `AI score ${event.score} · ${event.recommendation}`),
          };

        case "apply_result": {
          const newApplied = event.status === "applied" ? state.appliedCount + 1 : state.appliedCount;
          return { appliedCount: newApplied };
        }

        case "session_end":
          return {
            isRunning: false,
            uiState: state.uiState === "stopped" ? ("stopped" as const) : ("completed" as const),
            appliedCount: event.applied,
            target: event.target,
            logs: addLog(state.logs, now, "info",
              `Session ended — applied ${event.applied}/${event.target}, skipped ${event.skipped}, failed ${event.errors}`),
          };

        case "session_stopped":
          return {
            isRunning: false,
            uiState: "stopped" as const,
            jobs: state.jobs.map((j) =>
              j.status && ["queued", "fetching", "scoring", "applying"].includes(j.status)
                ? { ...j, status: "stopped", failure_reason: "session_stopped" }
                : j),
            logs: addLog(state.logs, now, "warning", "Session stopped"),
          };

        case "rate_limit":
          return { logs: addLog(state.logs, now, "warning", event.msg) };

        case "error":
          return { logs: addLog(state.logs, now, "error", `ERROR: ${event.msg}`) };

        case "log":
          return { logs: addLog(state.logs, now, event.level, event.msg) };

        default:
          return state;
      }
    });
  },
}));

function ts(): string {
  return new Date().toLocaleTimeString();
}

function addLog(logs: TimelineEntry[], ts: string, level: string, msg: string): TimelineEntry[] {
  const next = [...logs, { ts, level, msg }];
  return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
}

function updateLastJob(state: SessionState, updates: Partial<JobEntry>): Partial<SessionState> {
  if (!state.jobs.length) return {};
  const jobs = [...state.jobs];
  jobs[jobs.length - 1] = { ...jobs[jobs.length - 1], ...updates };
  return { jobs };
}

function updateJobByIdOrLast(state: SessionState, appId: number, updates: Partial<JobEntry>): Partial<SessionState> {
  if (!state.jobs.length) return {};
  const jobs = [...state.jobs];
  let idx = jobs.findIndex((j) => j.appId === appId);
  if (idx < 0) idx = jobs.length - 1;
  jobs[idx] = { ...jobs[idx], ...updates };
  return { jobs };
}
