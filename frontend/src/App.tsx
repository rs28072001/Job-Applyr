import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import SetupPage from "./pages/SetupPage";
import DashboardPage from "./pages/DashboardPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import HistoryPage from "./pages/HistoryPage";
import IgnoredJobsPage from "./pages/IgnoredJobsPage";
import JobPreferencesPage from "./pages/JobPreferencesPage";
import ResumePage from "./pages/ResumePage";
import ProfilePage from "./pages/ProfilePage";

class PageErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="p-8 text-center">
          <p className="text-red-600 font-semibold mb-2">Something went wrong on this page.</p>
          <p className="text-slate-500 text-sm mb-4">{(this.state.error as Error).message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Navigate to="/dashboard" replace />} />
        <Route path="/signup" element={<Navigate to="/dashboard" replace />} />
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<PageErrorBoundary><DashboardPage /></PageErrorBoundary>} />
          <Route path="setup" element={<PageErrorBoundary><SetupPage /></PageErrorBoundary>} />
          <Route path="preferences" element={<PageErrorBoundary><JobPreferencesPage /></PageErrorBoundary>} />
          <Route path="resume" element={<PageErrorBoundary><ResumePage /></PageErrorBoundary>} />
          <Route path="profile" element={<PageErrorBoundary><ProfilePage /></PageErrorBoundary>} />
          <Route path="review" element={<PageErrorBoundary><ReviewQueuePage /></PageErrorBoundary>} />
          <Route path="ignored" element={<PageErrorBoundary><IgnoredJobsPage /></PageErrorBoundary>} />
          <Route path="history" element={<PageErrorBoundary><HistoryPage /></PageErrorBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
