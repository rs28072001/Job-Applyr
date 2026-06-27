import { useEffect, useState } from "react";
import { User, Mail, Phone, Briefcase, Award, GraduationCap, FileText, Upload, CheckCircle2, AlertCircle, Loader2, Target, Lightbulb, TrendingUp } from "lucide-react";
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
      formData.append("file", file);

      const res = await api.post<{ profile: CVProfile }>("/api/cv/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setProfile(res.data.profile);
      setUploadSuccess(true);
      setTimeout(() => setUploadSuccess(false), 3000);
    } catch (e: any) {
      console.error("Failed to upload resume:", e);
      setUploadError(e.response?.data?.detail || "Failed to upload resume");
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
      setAtsError(e.response?.data?.detail || "Failed to analyze ATS score");
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
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Resume Profile</h1>
          <p className="text-slate-500 text-sm mt-0.5">Your parsed resume information</p>
        </div>
        <div className="flex items-center gap-2">
          {profile && (
            <button
              onClick={handleATSAnalysis}
              disabled={analyzing || atsDisabled}
              title={atsDisabled ? "Know Your ATS needs an AI provider. Select one in Settings." : undefined}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
              {analyzing ? "Analyzing..." : "Know Your ATS"}
            </button>
          )}
          <label className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg cursor-pointer transition-colors">
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? "Uploading..." : "Upload New"}
            <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" disabled={uploading} />
          </label>
        </div>
      </div>

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
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">ATS Analysis Results</h2>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Target className="w-4 h-4" />
              AI-Powered Analysis
            </div>
          </div>

          <div className="flex items-center justify-center py-4">
            <ATSDonutChart score={atsScore} size={180} strokeWidth={14} />
          </div>

          {atsAnalysis.overall_feedback && (
            <div className="bg-slate-50 rounded-lg p-4">
              <p className="text-slate-700 text-sm leading-relaxed">{atsAnalysis.overall_feedback}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {atsAnalysis.strengths && atsAnalysis.strengths.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-emerald-600" />
                  <h3 className="text-sm font-semibold text-slate-800">Strengths</h3>
                </div>
                <ul className="space-y-2">
                  {atsAnalysis.strengths.map((strength, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                      {strength}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {atsAnalysis.improvements && atsAnalysis.improvements.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Lightbulb className="w-5 h-5 text-amber-600" />
                  <h3 className="text-sm font-semibold text-slate-800">Improvements</h3>
                </div>
                <ul className="space-y-2">
                  {atsAnalysis.improvements.map((improvement, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-slate-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                      {improvement}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

      {!profile ? (
        <Card className="p-8 text-center">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-slate-800 mb-2">No resume uploaded</h2>
          <p className="text-slate-500 text-sm mb-4">Upload your resume to get started with job matching</p>
          <label className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg cursor-pointer transition-colors">
            <Upload className="w-4 h-4" />
            Upload Resume
            <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" disabled={uploading} />
          </label>
        </Card>
      ) : (
        <Card className="p-6 space-y-6">
          {/* Personal Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
                <User className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Name</p>
                <p className="text-slate-800 text-sm font-medium truncate">{profile.name || "Not specified"}</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
                <Briefcase className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="min-w-0">
                <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Experience</p>
                <p className="text-slate-800 text-sm font-medium">{profile.experience_years} years</p>
              </div>
            </div>
            {profile.email && (
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
                  <Mail className="w-5 h-5 text-indigo-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Email</p>
                  <p className="text-slate-800 text-sm font-medium truncate">{profile.email}</p>
                </div>
              </div>
            )}
            {profile.phone && (
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
                  <Phone className="w-5 h-5 text-indigo-600" />
                </div>
                <div className="min-w-0">
                  <p className="text-slate-500 text-xs uppercase tracking-wide mb-1">Phone</p>
                  <p className="text-slate-800 text-sm font-medium">{profile.phone}</p>
                </div>
              </div>
            )}
          </div>

          {/* Job Titles */}
          {profile.job_titles && profile.job_titles.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Briefcase className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-semibold text-slate-800">Job Titles</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {profile.job_titles.map((title, idx) => (
                  <span key={idx} className="px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg">
                    {title}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Skills */}
          {profile.skills && profile.skills.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Award className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-semibold text-slate-800">Skills</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {profile.skills.map((skill, idx) => (
                  <span key={idx} className="px-3 py-1.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-lg">
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
                <GraduationCap className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-semibold text-slate-800">Education</h3>
              </div>
              <div className="space-y-2">
                {profile.education.map((edu, idx) => (
                  <div key={idx} className="px-3 py-2 bg-slate-50 text-slate-700 text-sm rounded-lg">
                    {edu}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {profile.summary && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-semibold text-slate-800">Summary</h3>
              </div>
              <p className="text-slate-600 text-sm leading-relaxed">{profile.summary}</p>
            </div>
          )}

          {/* File Info */}
          {profile.pdf_path && (
            <div className="pt-4 border-t border-slate-100">
              <p className="text-slate-400 text-xs">
                Resume file: <span className="text-slate-500">{profile.pdf_path}</span>
              </p>
              <p className="text-slate-400 text-xs mt-1">
                Uploaded: {new Date(profile.created_at).toLocaleDateString()}
              </p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
