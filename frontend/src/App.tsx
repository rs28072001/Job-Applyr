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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Navigate to="/dashboard" replace />} />
        <Route path="/signup" element={<Navigate to="/dashboard" replace />} />
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="setup" element={<SetupPage />} />
          <Route path="preferences" element={<JobPreferencesPage />} />
          <Route path="resume" element={<ResumePage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="review" element={<ReviewQueuePage />} />
          <Route path="ignored" element={<IgnoredJobsPage />} />
          <Route path="history" element={<HistoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
