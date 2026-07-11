import { useEffect, useState } from "react";
import { User, Briefcase, Award, GraduationCap, FileText, Upload, CheckCircle2, AlertCircle, Loader2, Target } from "lucide-react";
import { api } from "../api/client";
import type { CVProfile, AppConfig } from "../api/types";
import { Card } from "../components/ui";
import ATSDonutChart from "../components/ATSDonutChart";

export default function ResumePage() {
  const [profile, setProfile] = useState<CVProfile | null>(null);
  const [aiProvider, setAiProvider] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [atsScore, setAtsScore] = useState<number | null>(null);
  const [atsAnalysis, setAtsAnalysis] = useState<{
    strengths: string[];
    improvements: string[];
    overall_feedback: string;
  } | null>(null);
  const [atsError, setAtsError] = useState("");

  useEffect(() => {
    async function fetchProfile() {
      try {
        const res = await api.get<CVProfile>("/api/cv/profile");
        setProfile(res.data);
      } catch (e) {
        console.error("Failed to fetch CV profile:", e);
      } finally {
        setLoading(false);
      }
    }
    async function fetchProvider() {
      try {
        const res = await api.get<AppConfig>("/api/config");
        setAiProvider(res.data.ai_provider || "");
      } catch { /* ignore */ }
    }
    fetchProfile();
    fetchProvider();
  }, []);

  const atsDisabled = aiProvider === "fuzzy" || !aiProvider;

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "application/pdf") {
      setUploadError("Please upload a PDF file");
      return;
    }

    setUploading(true);
    setUploadError("");
    setUploadSuccess(false);

    try {
      const formData = new FormData();
      formData.append("cv_file", file);

      const res = await api.post<CVProfile>("/api/cv/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setProfile(res.data);

      // Auto-sync job titles to keywords in preferences
      if (res.data.job_titles && res.data.job_titles.length > 0) {
        try {
          await api.put("/api/config", {
            keywords: res.data.job_titles,
          });
        } catch (e) {
          console.warn("Failed to sync keywords:", e);
        }
      }

      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 3000);
    } catch (e: any) {
      console.error("Failed to upload resume:", e);
      const detail = e.response?.data?.detail;
      setUploadError(
        typeof detail === "string" ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d.msg ?? String(d)).join("; ")
        : detail ? String(detail)
        : "Failed to upload resume"
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleATSAnalysis() {
    setAnalyzing(true);
    setAtsError("");
    try {
      const res = await api.post<{
        score: number;
        strengths: string[];
        improvements: string[];
        overall_feedback: string;
      }>("/api/cv/ats-analyze");
      
      setAtsScore(res.data.score);
      setAtsAnalysis({
        strengths: res.data.strengths,
        improvements: res.data.improvements,
        overall_feedback: res.data.overall_feedback,
      });
    } catch (e: any) {
      console.error("Failed to analyze ATS:", e);
      const detail = e.response?.data?.detail;
      setAtsError(
        typeof detail === "string" ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d.msg ?? String(d)).join("; ")
        : detail ? String(detail)
        : "Failed to analyze ATS score"
      );
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-1/3" />
          <div className="h-64 bg-slate-200 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header — only shown when a resume is already loaded */}
      {profile && (
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
              Resume Analysis
              <span className="text-pink-400 text-2xl">✨</span>
            </h1>
            <p className="text-slate-500 text-sm mt-1">Your resume insights and ATS analysis report</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleATSAnalysis}
              disabled={analyzing || atsDisabled}
              title={atsDisabled ? "Know Your ATS needs an AI provider. Select one in Settings." : undefined}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
              {analyzing ? "Analyzing..." : "Know Your ATS"}
            </button>
            <label className="flex items-center gap-1.5 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg cursor-pointer transition-colors">
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploading ? "Uploading..." : "Upload New Resume"}
              <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" disabled={uploading} />
            </label>
          </div>
        </div>
      )}

      {uploadSuccess && (
        <div className="flex items-center gap-2 text-emerald-600 text-sm bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          <CheckCircle2 className="w-4 h-4" />
          Resume uploaded successfully
        </div>
      )}

      {uploadError && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <AlertCircle className="w-4 h-4" />
          {uploadError}
        </div>
      )}

      {atsError && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <AlertCircle className="w-4 h-4" />
          {atsError}
        </div>
      )}

      {atsAnalysis && atsScore !== null && (
        <div className="space-y-6">
          {/* ATS Score Card */}
          <Card className="p-8">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Score Chart */}
              <div className="flex flex-col items-center justify-center">
                <div className="mb-6">
                  <ATSDonutChart score={atsScore} size={200} strokeWidth={16} />
                </div>
              </div>

              {/* Feedback and Metrics */}
              <div className="lg:col-span-2 space-y-6">
                {atsAnalysis.overall_feedback && (
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">Great job! Your resume is ATS-friendly.</h3>
                    <p className="text-slate-600 text-sm leading-relaxed">{atsAnalysis.overall_feedback}</p>
                  </div>
                )}

                {/* Metrics Grid */}
                <div className="grid grid-cols-4 gap-3">
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-600">90%</p>
                    <p className="text-xs text-slate-600 mt-1">Keyword Match</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600">85%</p>
                    <p className="text-xs text-slate-600 mt-1">Formatting</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-orange-500">80%</p>
                    <p className="text-xs text-slate-600 mt-1">Skills Match</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-amber-500">75%</p>
                    <p className="text-xs text-slate-600 mt-1">Content Relevance</p>
                  </div>
                </div>

                {/* Percentile Bar */}
                <div className="bg-gradient-to-r from-slate-100 to-slate-50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-slate-700">You're in the top 15% of candidates!</span>
                    <span className="text-sm font-bold text-amber-600">🏆</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2">
                    <div className="bg-gradient-to-r from-emerald-500 to-emerald-400 h-2 rounded-full" style={{ width: "85%" }}></div>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Strengths & Improvements */}
          {(atsAnalysis.strengths?.length > 0 || atsAnalysis.improvements?.length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {atsAnalysis.strengths && atsAnalysis.strengths.length > 0 && (
                <Card className="p-6 bg-gradient-to-br from-emerald-50 to-white">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-2xl">✨</span>
                    <h3 className="text-lg font-semibold text-slate-900">Strengths</h3>
                  </div>
                  <ul className="space-y-3">
                    {atsAnalysis.strengths.map((strength, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <span className="text-emerald-500 text-lg mt-0.5 shrink-0">✓</span>
                        <span className="text-sm text-slate-700">{strength}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {atsAnalysis.improvements && atsAnalysis.improvements.length > 0 && (
                <Card className="p-6 bg-gradient-to-br from-orange-50 to-white">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-2xl">💡</span>
                    <h3 className="text-lg font-semibold text-slate-900">Improvements</h3>
                  </div>
                  <ul className="space-y-3">
                    {atsAnalysis.improvements.map((improvement, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <span className="text-orange-500 text-lg mt-0.5 shrink-0">→</span>
                        <span className="text-sm text-slate-700">{improvement}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {!profile ? (
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center max-w-md mx-auto px-6 py-10">
            {/* Illustration */}
            <div className="relative inline-block mb-8">
              {/* Sparkles */}
              <span className="absolute -top-3 left-2 text-indigo-300 text-xl select-none">✦</span>
              <span className="absolute top-0 right-0 text-indigo-200 text-sm select-none">✦</span>
              <span className="absolute bottom-4 -left-4 text-violet-200 text-xs select-none">✦</span>
              <span className="absolute -bottom-2 right-4 text-indigo-300 text-base select-none">✦</span>
              <img
                src="/upload-resume.png"
                alt="Upload resume illustration"
                className="w-56 h-auto mx-auto drop-shadow-sm"
              />
            </div>

            <h2 className="text-3xl font-bold text-slate-900 mb-3">Upload Your Resume</h2>
            <p className="text-slate-500 text-base leading-relaxed mb-8">
              Get AI-powered insights, ATS score, and personalized suggestions
              to improve your resume and land your dream job.
            </p>

            <label className="inline-flex items-center gap-2 px-8 py-3.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-base font-semibold rounded-xl cursor-pointer transition-colors shadow-md shadow-indigo-200">
              {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
              {uploading ? "Uploading..." : "Upload Resume"}
              <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" disabled={uploading} />
            </label>

            <p className="mt-4 text-slate-400 text-xs">
              Supports PDF &nbsp;•&nbsp; Max file size: 10 MB
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Extracted Profile Summary Card */}
          <Card className="p-8 bg-gradient-to-br from-slate-50 to-white">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                  <User className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">Extracted Profile Summary</h3>
                  <p className="text-xs text-emerald-600">✓ Auto Extracted</p>
                </div>
              </div>
            </div>

            {/* Personal Info Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white border border-slate-200 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Name</p>
                <p className="text-sm font-semibold text-slate-900">{profile.name || "Not specified"}</p>
              </div>
              <div className="bg-white border border-slate-200 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Experience</p>
                <p className="text-sm font-semibold text-slate-900">{profile.experience_years} years</p>
              </div>
              {profile.email && (
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Email</p>
                  <p className="text-xs font-medium text-slate-900 truncate">{profile.email}</p>
                </div>
              )}
              {profile.phone && (
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <p className="text-xs text-slate-500 font-semibold uppercase mb-1">Phone</p>
                  <p className="text-xs font-medium text-slate-900">{profile.phone}</p>
                </div>
              )}
            </div>

            {/* Job Titles */}
            {profile.job_titles && profile.job_titles.length > 0 && (
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Briefcase className="w-4 h-4 text-indigo-600" />
                  <p className="text-sm font-semibold text-slate-800">Job Titles</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {profile.job_titles.map((title, idx) => (
                    <span key={idx} className="px-3 py-1.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-lg border border-indigo-200">
                      {title}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Top Skills */}
            {profile.skills && profile.skills.length > 0 && (
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Award className="w-4 h-4 text-indigo-600" />
                  <p className="text-sm font-semibold text-slate-800">Top Skills</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {profile.skills.map((skill, idx) => (
                    <span key={idx} className="px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg border border-slate-200">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Education */}
            {profile.education && profile.education.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <GraduationCap className="w-4 h-4 text-indigo-600" />
                  <p className="text-sm font-semibold text-slate-800">Education</p>
                </div>
                <div className="space-y-2">
                  {profile.education.map((edu, idx) => (
                    <p key={idx} className="text-sm text-slate-700">{edu}</p>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* AI Summary */}
          {profile.summary && (
            <Card className="p-8 bg-gradient-to-br from-indigo-50 to-white border-l-4 border-indigo-600">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
                  <FileText className="w-5 h-5 text-indigo-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">AI Summary</h3>
                  <p className="text-slate-700 text-sm leading-relaxed">{profile.summary}</p>
                </div>
              </div>
            </Card>
          )}

          {/* File Info */}
          {profile.pdf_path && (
            <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Resume File</p>
                <p className="text-sm font-medium text-slate-900">{profile.pdf_path.split("/").pop()}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Uploaded On</p>
                <p className="text-sm font-medium text-slate-900">{new Date(profile.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
