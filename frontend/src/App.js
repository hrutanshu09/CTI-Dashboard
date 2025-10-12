import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import AIAssistantPage from './pages/AIAssistantPage';
import ThreatIntelPage from './pages/ThreatIntelPage';
import LogAnalyzerPage from './pages/LogAnalyzerPage'; // <-- CORRECTED PATH
import ReportingPage from './pages/ReportingPage';

function App() {
  return (
    <div className="flex h-screen bg-background text-white font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ai-assistant" element={<AIAssistantPage />} />
            <Route path="/threat-intel" element={<ThreatIntelPage />} />
            <Route path="/log-analyzer" element={<LogAnalyzerPage />} />
            <Route path="/reporting" element={<ReportingPage />} />
            <Route path="/settings" element={<div className="p-6"><h1 className="text-2xl font-bold">Settings Page</h1></div>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;