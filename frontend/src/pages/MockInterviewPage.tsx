import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle, AlertTriangle, Award, BarChart3, Bot, Briefcase, CheckCircle2,
  ChevronDown, Clock, Flame, Gauge, Globe, History, Keyboard, Lightbulb,
  Loader2, Mic, MicOff, Play, Send, Sparkles, Target, TrendingUp, Volume2,
} from "lucide-react";
import { api } from "../api/client";
import { Card } from "../components/ui";

/* ── Types ─────────────────────────────────────────────────────────────────── */

interface InterviewDefaults {
  role: string;
  role_options: string[];
  experience_years: number;
  skills: string[];
}

interface QAResult {
  question: string;
  answer: string;
  score: number;
  feedback: string;
  improvement: string;
}

interface FinishResponse {
  overall_score: number;
  answered: number;
  total_questions: number;
  status: string;
  verdict: string;
  results: QAResult[];
}

interface HistoryData {
  interviews_taken: number;
  avg_score: number;
  success_rate: number;
  best_streak: number;
  recent: {
    id: number;
    role: string;
    interview_type: string;
    difficulty: string;
    overall_score: number | null;
    status: string;
    created_at: string;
  }[];
}

type Phase = "setup" | "starting" | "running" | "results";

const INTERVIEW_TYPES = [
  { value: "technical", label: "Technical Interview", hint: "Coding, concepts & problem solving" },
  { value: "hr", label: "HR Interview", hint: "Behavioral & situational questions" },
  { value: "behavioral", label: "Behavioral", hint: "Past experience & soft skills" },
  { value: "system_design", label: "System Design", hint: "Architecture & design discussions" },
];

const EXPERIENCE_LEVELS = ["0-1 years", "1-3 years", "3-5 years", "5-8 years", "8+ years"];
const DIFFICULTIES = ["easy", "medium", "hard"] as const;
const LANGUAGES = [
  { value: "en-US", label: "English" },
  { value: "en-IN", label: "English (India)" },
  { value: "hi-IN", label: "Hindi" },
];
const DURATIONS = [15, 30, 45];

const HOW_IT_WORKS = [
  { icon: Target, title: "1. Choose setup", hint: "Select role, experience, type and skills." },
  { icon: Bot, title: "2. Interview session", hint: "AI asks questions aloud in real time." },
  { icon: BarChart3, title: "3. Get feedback", hint: "Each answer is scored with improvement tips." },
  { icon: TrendingUp, title: "4. Improve", hint: "Track progress and get better every time." },
];

const TIPS = [
  "Find a quiet place with stable internet",
  "Use a headset for better speech recognition",
  "Speak clearly and at a normal pace",
  "Stay on the interview screen — leaving it ends the interview",
];

const VIOLATION_SECONDS = 8;

function experienceLevelFromYears(years: number): string {
  if (years < 1) return "0-1 years";
  if (years < 3) return "1-3 years";
  if (years < 5) return "3-5 years";
  if (years < 8) return "5-8 years";
  return "8+ years";
}

function scoreColor(score: number): string {
  if (score >= 7) return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (score >= 5) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-red-600 bg-red-50 border-red-200";
}

const selectCls = `w-full pl-10 pr-9 py-2.5 border border-slate-200 rounded-lg text-sm
  focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
  hover:border-slate-300 bg-white text-slate-900`;

// Tailwind's `appearance-none` alone doesn't fully suppress native select
// chrome/arrow in Safari — force it with vendor-prefixed inline styles too,
// otherwise the browser's own icon/arrow renders underneath our custom ones.
const nativeSelectReset: React.CSSProperties = {
  WebkitAppearance: "none",
  MozAppearance: "none",
  appearance: "none",
  backgroundImage: "none",
};

function SetupField({ label, icon: Icon, iconColor = "text-slate-400", children }: {
  label: string; icon: React.ElementType; iconColor?: string; children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-600 mb-1.5">{label}</label>
      <div className="relative">
        <Icon className={`absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none z-10 ${iconColor}`} />
        {children}
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────────────────── */

export default function MockInterviewPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [error, setError] = useState("");

  // Setup
  const [role, setRole] = useState("");
  const [roleOptions, setRoleOptions] = useState<string[]>([]);
  const [experienceLevel, setExperienceLevel] = useState("1-3 years");
  const [interviewType, setInterviewType] = useState("technical");
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTIES)[number]>("medium");
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState("");
  const [language, setLanguage] = useState("en-US");
  const [duration, setDuration] = useState(30);
  const [answerMode, setAnswerMode] = useState<"voice" | "text">("voice");
  const [history, setHistory] = useState<HistoryData | null>(null);

  // Interview
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [qIndex, setQIndex] = useState(0);
  const [answerText, setAnswerText] = useState("");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [violationCountdown, setViolationCountdown] = useState<number | null>(null);
  const [results, setResults] = useState<FinishResponse | null>(null);

  const shellRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const listeningRef = useRef(false);
  const answerRef = useRef("");
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const violationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseRef = useRef<Phase>("setup");
  const finishingRef = useRef(false);
  phaseRef.current = phase;

  const sttSupported =
    typeof window !== "undefined" &&
    Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  /* ── Data loading ── */

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.get<HistoryData>("/api/interview/history");
      setHistory(res.data);
    } catch {
      /* stats are non-critical */
    }
  }, []);

  useEffect(() => {
    async function load() {
      loadHistory();
      try {
        const res = await api.get<InterviewDefaults>("/api/interview/defaults");
        const d = res.data;
        setRole(d.role);
        setRoleOptions(d.role_options);
        setSkills(d.skills.slice(0, 6));
        setExperienceLevel(experienceLevelFromYears(d.experience_years));
      } catch {
        /* no CV yet — user fills the form manually */
      }
    }
    load();
  }, [loadHistory]);

  /* ── Text-to-speech ── */

  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = language;
    utt.rate = 0.95;
    utt.onstart = () => setSpeaking(true);
    utt.onend = () => setSpeaking(false);
    utt.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utt);
  }, [language]);

  /* ── Speech-to-text ── */

  const stopListening = useCallback(() => {
    listeningRef.current = false;
    setListening(false);
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    try { recognitionRef.current?.stop(); } catch { /* already stopped */ }
  }, []);

  const submitAnswerRef = useRef<() => void>(() => {});

  const startListening = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    stopListening();

    const rec = new SR();
    rec.lang = language;
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (event: any) => {
      let finalChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) finalChunk += event.results[i][0].transcript + " ";
      }
      if (finalChunk) {
        answerRef.current = (answerRef.current + " " + finalChunk).trim();
        setAnswerText(answerRef.current);
      }
      // Voice mode auto-submit: no speech for a while after saying something → process the answer
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = setTimeout(() => {
        if (listeningRef.current && answerRef.current.trim()) {
          submitAnswerRef.current();
        }
      }, 9000);
    };
    rec.onend = () => {
      // Browsers stop recognition after brief silence — restart while we're still meant to listen
      if (listeningRef.current && phaseRef.current === "running") {
        try { rec.start(); } catch { /* restart raced with stop */ }
      }
    };
    rec.onerror = (e: any) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        listeningRef.current = false;
        setListening(false);
        setError("Microphone access denied — switch to text mode or allow the mic.");
      }
    };

    recognitionRef.current = rec;
    listeningRef.current = true;
    setListening(true);
    try { rec.start(); } catch { /* already started */ }
  }, [language, stopListening]);

  /* ── Interview flow ── */

  const askQuestion = useCallback((index: number, qs: string[]) => {
    answerRef.current = "";
    setAnswerText("");
    setQIndex(index);
    speak(qs[index]);
  }, [speak]);

  const finishInterview = useCallback(async (terminated: boolean, reason = "") => {
    if (finishingRef.current || sessionId === null) return;
    finishingRef.current = true;
    stopListening();
    window.speechSynthesis?.cancel();
    if (violationTimerRef.current) clearInterval(violationTimerRef.current);
    setViolationCountdown(null);
    try {
      const res = await api.post<FinishResponse>("/api/interview/finish", {
        session_id: sessionId, terminated, reason,
      });
      setResults(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to finish the interview");
    }
    setPhase("results");
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    loadHistory();
  }, [sessionId, stopListening, loadHistory]);

  const finishRef = useRef(finishInterview);
  finishRef.current = finishInterview;

  const submitAnswer = useCallback(async () => {
    if (evaluating || sessionId === null || phaseRef.current !== "running") return;
    const answer = answerRef.current.trim();
    stopListening();
    window.speechSynthesis?.cancel();
    setEvaluating(true);
    try {
      await api.post("/api/interview/answer", {
        session_id: sessionId, question_index: qIndex, answer,
      });
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to evaluate the answer");
    }
    setEvaluating(false);
    if (qIndex + 1 < questions.length) {
      askQuestion(qIndex + 1, questions);
      if (answerMode === "voice") setTimeout(() => startListening(), 400);
    } else {
      finishRef.current(false);
    }
  }, [evaluating, sessionId, qIndex, questions, answerMode, askQuestion, startListening, stopListening]);

  submitAnswerRef.current = submitAnswer;

  const startInterview = useCallback(async () => {
    setError("");
    setPhase("starting");
    // Enter fullscreen right away — the browser only honors the request close to
    // the click, and question generation can take longer than that window.
    setTimeout(() => shellRef.current?.requestFullscreen().catch(() => {}), 0);
    try {
      const res = await api.post<{ session_id: number; questions: string[] }>("/api/interview/start", {
        role,
        experience_level: experienceLevel,
        interview_type: interviewType,
        difficulty,
        skills,
        language,
        duration_minutes: duration,
        answer_mode: answerMode,
      });
      const { session_id, questions: qs } = res.data;
      setSessionId(session_id);
      setQuestions(qs);
      setResults(null);
      finishingRef.current = false;
      setSecondsLeft(duration * 60);

      if (!document.fullscreenElement) {
        await shellRef.current?.requestFullscreen().catch(() => {});
      }
      setPhase("running");
      askQuestion(0, qs);
      if (answerMode === "voice") setTimeout(() => startListening(), 800);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Failed to start the interview");
      setPhase("setup");
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    }
  }, [role, experienceLevel, interviewType, difficulty, skills, language, duration, answerMode, askQuestion, startListening]);

  /* ── Session timer ── */

  useEffect(() => {
    if (phase !== "running") return;
    const t = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          finishRef.current(false);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [phase]);

  /* ── Anti-cheat: fullscreen + tab watching ── */

  useEffect(() => {
    if (phase !== "running") return;

    function violated() {
      return !document.fullscreenElement || document.hidden;
    }

    function check() {
      if (phaseRef.current !== "running") return;
      if (violated()) {
        if (violationTimerRef.current) return; // countdown already running
        let remaining = VIOLATION_SECONDS;
        setViolationCountdown(remaining);
        violationTimerRef.current = setInterval(() => {
          if (!violated()) {
            clearInterval(violationTimerRef.current!);
            violationTimerRef.current = null;
            setViolationCountdown(null);
            return;
          }
          remaining -= 1;
          setViolationCountdown(remaining);
          if (remaining <= 0) {
            clearInterval(violationTimerRef.current!);
            violationTimerRef.current = null;
            finishRef.current(true, "Left fullscreen / switched screens during the interview");
          }
        }, 1000);
      }
    }

    document.addEventListener("fullscreenchange", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      document.removeEventListener("fullscreenchange", check);
      document.removeEventListener("visibilitychange", check);
      if (violationTimerRef.current) {
        clearInterval(violationTimerRef.current);
        violationTimerRef.current = null;
      }
    };
  }, [phase]);

  // Cleanup on unmount
  useEffect(() => () => {
    stopListening();
    window.speechSynthesis?.cancel();
    if (violationTimerRef.current) clearInterval(violationTimerRef.current);
  }, [stopListening]);

  /* ── Render ── */

  const timerLabel = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;

  if (phase === "running" || phase === "starting") {
    return (
      <div ref={shellRef} className="min-h-screen h-full bg-slate-900 text-white flex flex-col select-none">
        {phase === "starting" ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
            <p className="text-sm text-slate-300">Preparing your interview questions…</p>
          </div>
        ) : (
          <>
            {/* Top bar */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/60">
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Bot className="w-4 h-4 text-indigo-400" />
                {role} · {INTERVIEW_TYPES.find((t) => t.value === interviewType)?.label} · {difficulty}
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-slate-400">
                  Question {qIndex + 1} of {questions.length}
                </span>
                <span className={`flex items-center gap-1.5 text-sm font-semibold tabular-nums
                  ${secondsLeft <= 60 ? "text-red-400" : "text-slate-200"}`}>
                  <Clock className="w-4 h-4" />
                  {timerLabel}
                </span>
              </div>
            </div>

            {/* Question */}
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-8 gap-8 max-w-3xl mx-auto w-full">
              <div className="w-full">
                <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold uppercase tracking-wide mb-3">
                  {speaking ? <Volume2 className="w-4 h-4 animate-pulse" /> : <Bot className="w-4 h-4" />}
                  {speaking ? "Interviewer is speaking…" : "Interviewer"}
                  <button
                    type="button"
                    onClick={() => speak(questions[qIndex])}
                    className="ml-1 text-[11px] text-slate-400 hover:text-slate-200 underline underline-offset-2"
                  >
                    repeat
                  </button>
                </div>
                <p className="text-xl leading-relaxed font-medium">{questions[qIndex]}</p>
              </div>

              {/* Answer area */}
              <div className="w-full space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Your answer</span>
                  {answerMode === "voice" && sttSupported && (
                    <button
                      type="button"
                      onClick={() => (listening ? stopListening() : startListening())}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-colors
                        ${listening ? "bg-red-500/20 text-red-300 border border-red-500/40" : "bg-slate-700 text-slate-200 border border-slate-600 hover:bg-slate-600"}`}
                    >
                      {listening ? <Mic className="w-3.5 h-3.5 animate-pulse" /> : <MicOff className="w-3.5 h-3.5" />}
                      {listening ? "Listening… tap to pause" : "Mic paused — tap to resume"}
                    </button>
                  )}
                </div>
                <textarea
                  value={answerText}
                  onChange={(e) => { answerRef.current = e.target.value; setAnswerText(e.target.value); }}
                  placeholder={answerMode === "voice"
                    ? "Speak your answer — the transcript appears here (you can edit it too)…"
                    : "Type your answer here…"}
                  rows={6}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-4 text-sm leading-relaxed
                    text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
                <div className="flex items-center justify-between">
                  <p className="text-[11px] text-slate-500">
                    {answerMode === "voice"
                      ? "Answers auto-submit after a long pause, or press Submit."
                      : "Press Submit when you are done."}
                  </p>
                  <button
                    type="button"
                    onClick={submitAnswer}
                    disabled={evaluating}
                    className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60
                      text-white text-sm font-semibold rounded-lg transition-colors"
                  >
                    {evaluating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    {evaluating
                      ? "Evaluating…"
                      : qIndex + 1 === questions.length ? "Submit & Finish" : "Submit Answer"}
                  </button>
                </div>
                {error && (
                  <p className="text-xs text-red-400 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" /> {error}
                  </p>
                )}
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-700/60 text-center text-[11px] text-slate-500">
              Stay in fullscreen on this screen — leaving it will end and flag the interview.
            </div>
          </>
        )}

        {/* Anti-cheat overlay */}
        {violationCountdown !== null && (
          <div className="fixed inset-0 z-50 bg-slate-950/90 flex flex-col items-center justify-center gap-4 px-6 text-center">
            <AlertTriangle className="w-12 h-12 text-amber-400" />
            <h2 className="text-2xl font-bold">Return to the interview!</h2>
            <p className="text-slate-300 text-sm max-w-md">
              You left fullscreen or switched screens. That is not allowed during the interview —
              return within the countdown or the interview ends and is flagged.
            </p>
            <div className="text-6xl font-bold tabular-nums text-red-400">{violationCountdown}</div>
            <button
              type="button"
              onClick={() => shellRef.current?.requestFullscreen().catch(() => {})}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-semibold"
            >
              Return to fullscreen
            </button>
          </div>
        )}
      </div>
    );
  }

  if (phase === "results" && results) {
    return (
      <div className="p-6 max-w-4xl mx-auto space-y-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Interview Results</h1>
          <p className="text-slate-500 text-sm mt-0.5">{role} · {INTERVIEW_TYPES.find((t) => t.value === interviewType)?.label}</p>
        </div>

        {results.status === "terminated" && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            Interview terminated — you left the interview screen. This attempt is flagged as incomplete.
          </div>
        )}

        <Card className="p-5 flex items-center gap-6">
          <div className={`w-20 h-20 rounded-2xl border-2 flex flex-col items-center justify-center shrink-0 ${scoreColor(results.overall_score)}`}>
            <span className="text-2xl font-bold">{results.overall_score}</span>
            <span className="text-[10px] font-medium opacity-70">/ 10</span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-800">{results.verdict}</p>
            <p className="text-xs text-slate-500 mt-1">
              Answered {results.answered} of {results.total_questions} questions
              {results.answered < results.total_questions && " — unanswered questions score 0"}
            </p>
          </div>
        </Card>

        <div className="space-y-3">
          {results.results.map((r, i) => (
            <Card key={i} className="p-4 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-slate-800">Q{i + 1}. {r.question}</p>
                <span className={`shrink-0 px-2 py-0.5 rounded border text-xs font-bold ${scoreColor(r.score)}`}>
                  {r.score}/10
                </span>
              </div>
              {r.answer
                ? <p className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded-lg p-2.5 whitespace-pre-wrap">{r.answer}</p>
                : <p className="text-xs text-slate-400 italic">No answer given</p>}
              <p className="text-xs text-slate-600"><span className="font-semibold">Feedback:</span> {r.feedback}</p>
              {r.improvement && (
                <p className="text-xs text-indigo-700 flex items-start gap-1.5">
                  <Lightbulb className="w-3.5 h-3.5 shrink-0 mt-px" />
                  {r.improvement}
                </p>
              )}
            </Card>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => { setPhase("setup"); setResults(null); setError(""); }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Practice again
          </button>
        </div>
      </div>
    );
  }

  /* ── Setup screen ── */

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          AI Mock Interview <Sparkles className="w-4 h-4 text-indigo-500" />
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">Practice real interviews with AI and improve your confidence.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <div className="lg:col-span-2 space-y-4">
          {/* Setup card */}
          <Card className="p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-800">1. Choose Your Interview Setup</h2>
            <p className="text-xs text-slate-500 -mt-2">Auto-filled from your resume and job preferences — adjust anything.</p>

            <div className="grid grid-cols-2 gap-4">
              <SetupField label="Job Role" icon={Briefcase} iconColor="text-indigo-500">
                <select value={role} onChange={(e) => setRole(e.target.value)} className={selectCls} style={nativeSelectReset}>
                  {role && !roleOptions.includes(role) && <option value={role}>{role}</option>}
                  {roleOptions.map((r) => <option key={r} value={r}>{r}</option>)}
                  {roleOptions.length === 0 && !role && <option value="">Upload a resume to auto-fill</option>}
                </select>
              </SetupField>
              <SetupField label="Experience Level" icon={TrendingUp} iconColor="text-emerald-500">
                <select value={experienceLevel} onChange={(e) => setExperienceLevel(e.target.value)} className={selectCls} style={nativeSelectReset}>
                  {EXPERIENCE_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </SetupField>
              <SetupField label="Interview Type" icon={Mic} iconColor="text-violet-500">
                <select value={interviewType} onChange={(e) => setInterviewType(e.target.value)} className={selectCls} style={nativeSelectReset}>
                  {INTERVIEW_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </SetupField>
              <SetupField label="Difficulty Level" icon={Gauge} iconColor="text-amber-500">
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as any)} className={selectCls} style={nativeSelectReset}>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d[0].toUpperCase() + d.slice(1)}</option>)}
                </select>
              </SetupField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <SetupField label="Interview Language" icon={Globe} iconColor="text-sky-500">
                <select value={language} onChange={(e) => setLanguage(e.target.value)} className={selectCls} style={nativeSelectReset}>
                  {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </SetupField>
              <SetupField label="Duration" icon={Clock} iconColor="text-rose-500">
                <select value={duration} onChange={(e) => setDuration(+e.target.value)} className={selectCls} style={nativeSelectReset}>
                  {DURATIONS.map((d) => <option key={d} value={d}>{d} Minutes</option>)}
                </select>
              </SetupField>
            </div>

            {/* Skills */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Skills Focus (Optional)</label>
              <div className="flex flex-wrap items-center gap-1.5 p-2 border border-slate-200 rounded-lg bg-white">
                {skills.map((s) => (
                  <span key={s} className="flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded-md">
                    {s}
                    <button type="button" onClick={() => setSkills(skills.filter((x) => x !== s))}
                      className="text-slate-400 hover:text-slate-700">×</button>
                  </span>
                ))}
                <input
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === ",") && skillInput.trim()) {
                      e.preventDefault();
                      if (!skills.includes(skillInput.trim())) setSkills([...skills, skillInput.trim()]);
                      setSkillInput("");
                    }
                  }}
                  placeholder={skills.length ? "Add skill…" : "e.g. Manual Testing, Selenium, API Testing"}
                  className="flex-1 min-w-[120px] px-1 py-1 text-xs focus:outline-none bg-transparent text-slate-900 placeholder-slate-400"
                />
              </div>
            </div>

            {/* Answer mode */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Answer Mode</label>
              <div className="grid grid-cols-2 gap-2">
                {([
                  { v: "voice", l: "Voice", hint: "Speak answers — auto transcribed & submitted", icon: Mic },
                  { v: "text", l: "Text", hint: "Type your answers manually", icon: Keyboard },
                ] as const).map(({ v, l, hint, icon: Icon }) => (
                  <button key={v} type="button" onClick={() => setAnswerMode(v)}
                    disabled={v === "voice" && !sttSupported}
                    className={`flex items-start gap-2.5 p-3 rounded-lg border text-left transition-colors
                      ${answerMode === v ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300"}
                      ${v === "voice" && !sttSupported ? "opacity-50 cursor-not-allowed" : ""}`}>
                    <Icon className={`w-4 h-4 mt-0.5 ${answerMode === v ? "text-indigo-600" : "text-slate-400"}`} />
                    <span>
                      <span className={`block text-xs font-semibold ${answerMode === v ? "text-indigo-700" : "text-slate-700"}`}>{l}</span>
                      <span className="block text-[11px] text-slate-400 mt-0.5">
                        {v === "voice" && !sttSupported ? "Not supported in this browser — use Chrome" : hint}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={startInterview}
              disabled={!role.trim()}
              className="w-full flex flex-col items-center gap-0.5 py-3 bg-indigo-600 hover:bg-indigo-700
                disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                <Play className="w-4 h-4" /> Start Mock Interview
              </span>
              <span className="text-[11px] text-indigo-200">
                Goes fullscreen — the AI interviewer asks questions aloud based on your setup.
              </span>
            </button>
            {error && (
              <p className="text-xs text-red-600 flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5" /> {error}
              </p>
            )}
          </Card>

          {/* How it works */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-4">How It Works</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {HOW_IT_WORKS.map(({ icon: Icon, title, hint }) => (
                <div key={title} className="flex flex-col items-center text-center gap-2">
                  <div className="w-11 h-11 rounded-full bg-indigo-50 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-indigo-600" />
                  </div>
                  <p className="text-xs font-semibold text-slate-800">{title}</p>
                  <p className="text-[11px] text-slate-500">{hint}</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Popular types */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-800 mb-3">Popular Interview Types</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {INTERVIEW_TYPES.map((t) => (
                <button key={t.value} type="button" onClick={() => setInterviewType(t.value)}
                  className={`p-3 rounded-lg border text-left transition-colors
                    ${interviewType === t.value ? "border-indigo-400 bg-indigo-50" : "border-slate-200 hover:border-slate-300"}`}>
                  <span className={`block text-xs font-semibold ${interviewType === t.value ? "text-indigo-700" : "text-slate-700"}`}>{t.label}</span>
                  <span className="block text-[11px] text-slate-400 mt-1">{t.hint}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-500" /> Your Interview Stats
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { icon: Mic, label: "Interviews Taken", value: String(history?.interviews_taken ?? 0) },
                { icon: Award, label: "Avg. Score", value: `${history?.avg_score ?? 0}/10` },
                { icon: Target, label: "Success Rate", value: `${history?.success_rate ?? 0}%` },
                { icon: Flame, label: "Best Streak", value: String(history?.best_streak ?? 0) },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 text-center">
                  <p className="text-lg font-bold text-indigo-600">{value}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-500" /> Recent Interviews
            </h2>
            {history?.recent.length ? (
              <div className="space-y-2">
                {history.recent.map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-700 truncate">
                        {r.role} — {INTERVIEW_TYPES.find((t) => t.value === r.interview_type)?.label ?? r.interview_type}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {new Date(r.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                        {r.status === "terminated" && " · flagged"}
                      </p>
                    </div>
                    <span className={`shrink-0 px-1.5 py-0.5 rounded border text-[11px] font-semibold ${scoreColor(r.overall_score ?? 0)}`}>
                      {r.overall_score ?? 0}/10
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No interviews yet — take your first one!</p>
            )}
          </Card>

          <Card className="p-4 space-y-3 bg-indigo-50/50">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-indigo-500" /> Tips for Best Experience
            </h2>
            <ul className="space-y-2">
              {TIPS.map((tip) => (
                <li key={tip} className="flex items-start gap-2 text-xs text-slate-600">
                  <CheckCircle2 className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-px" />
                  {tip}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
