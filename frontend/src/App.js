import React, { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import AIAssistantPage from './pages/AIAssistantPage';
import ThreatIntelPage from './pages/ThreatIntelPage';
import LogAnalyzerPage from './pages/LogAnalyzerPage';
import ReportingPage from './pages/ReportingPage';
import LoginPage from './pages/LoginPage';
import SettingsPage from './pages/SettingsPage';
import { useAuth } from './context/AuthContext';

const SIDEBAR_STORAGE_KEY = 'cti_sidebar_collapsed_v1';

const AppShell = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  return (
    <div className="flex h-screen bg-background text-white font-sans">
      <Sidebar collapsed={sidebarCollapsed} />
      <div className="flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out">
        <Navbar
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
        />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ai-assistant" element={<AIAssistantPage />} />
            <Route path="/threat-intel" element={<ThreatIntelPage />} />
            <Route path="/log-analyzer" element={<LogAnalyzerPage />} />
            <Route path="/reporting" element={<ReportingPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

function App() {
  const { authenticated, authLoading } = useAuth();

  if (authLoading) {
    return (
      <div className="min-h-screen bg-background text-gray-300 flex items-center justify-center">
        Checking session...
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={authenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="*"
        element={authenticated ? <AppShell /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default App;
