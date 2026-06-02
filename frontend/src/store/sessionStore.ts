import { create } from "zustand";
import type { WSEvent } from "../api/types";

export interface JobEntry {
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
  status?: string;
  external_url?: string;
  exp_required?: string;
  salary?: string;
}

export interface LogEntry {
  ts: string;
  level: string;
  msg: string;
}

interface SessionState {
  isRunning: boolean;
  sessionId: number | null;
  loginStatus: Record<string, boolean>;
  searchCounts: Record<string, number>;
  jobs: JobEntry[];
  appliedCount: number;
  target: number;
  logs: LogEntry[];

  handleEvent: (event: WSEvent) => void;
  setRunning: (running: boolean, sessionId?: number | null) => void;
  reset: () => void;
}

const MAX_LOGS = 500;

export const useSessionStore = create<SessionState>((set) => ({
  isRunning: false,
  sessionId: null,
  loginStatus: {},
  searchCounts: {},
  jobs: [],
  appliedCount: 0,
  target: 0,
  logs: [],

  setRunning: (running, sessionId = null) =>
    set({ isRunning: running, sessionId: sessionId ?? null }),

  reset: () =>
    set({
      isRunning: false,
      sessionId: null,
      loginStatus: {},
      searchCounts: {},
      jobs: [],
      appliedCount: 0,
      target: 0,
      logs: [],
    }),

  handleEvent: (event) => {
    const ts = new Date().toLocaleTimeString();

    set((state) => {
      switch (event.type) {
        case "ping":
          return state;

        case "session_config":
          return { target: event.target, logs: addLog(state.logs, ts, "info",
            `Session started: ${event.platform} | target=${event.target} | loc=${event.location}`) };

        case "login":
          return {
            loginStatus: { ...state.loginStatus, [event.platform]: event.ok },
            logs: addLog(state.logs, ts, event.ok ? "info" : "error",
              `${event.platform}: ${event.ok ? "✓ logged in" : `login failed — ${event.error}`}`),
          };

        case "search":
          return {
            searchCounts: { ...state.searchCounts, [event.platform]: event.count },
            logs: addLog(state.logs, ts, "info",
              `Found ${event.count} listings on ${event.platform}`),
          };

        case "job_start": {
          const newJob: JobEntry = {
            idx: event.idx, total: event.total,
            title: event.title, company: event.company, url: event.url,
          };
          return { jobs: [...state.jobs, newJob] };
        }

        case "job_details": {
          return updateLastJob(state, { exp_required: event.exp_required, salary: event.salary });
        }

        case "llm_score": {
          return {
            ...updateLastJob(state, {
              score: event.score, rationale: event.rationale,
              matched: event.matched, missing: event.missing,
              recommendation: event.recommendation,
            }),
            logs: addLog(state.logs, ts, "info",
              `LLM: score=${event.score} | ${event.recommendation}`),
          };
        }

        case "apply_result": {
          const updates = { status: event.status, external_url: event.external_url };
          const newApplied = event.status === "applied"
            ? state.appliedCount + 1 : state.appliedCount;
          const lvl = event.status === "applied" ? "success"
            : event.status === "error" ? "error" : "info";
          return {
            ...updateLastJob(state, updates),
            appliedCount: newApplied,
            logs: addLog(state.logs, ts, lvl, `Apply: ${event.status} — ${event.title}`),
          };
        }

        case "session_end":
          return {
            isRunning: false,
            appliedCount: event.applied,
            target: event.target,
            logs: addLog(state.logs, ts, "info",
              `Session ended: applied=${event.applied}/${event.target} skipped=${event.skipped} errors=${event.errors}`),
          };

        case "error":
          return {
            logs: addLog(state.logs, ts, "error", `ERROR: ${event.msg}`),
          };

        case "log":
          return { logs: addLog(state.logs, ts, event.level, event.msg) };

        default:
          return state;
      }
    });
  },
}));

function addLog(logs: LogEntry[], ts: string, level: string, msg: string): LogEntry[] {
  const next = [...logs, { ts, level, msg }];
  return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
}

function updateLastJob(state: SessionState, updates: Partial<JobEntry>): Partial<SessionState> {
  if (!state.jobs.length) return {};
  const jobs = [...state.jobs];
  jobs[jobs.length - 1] = { ...jobs[jobs.length - 1], ...updates };
  return { jobs };
}
