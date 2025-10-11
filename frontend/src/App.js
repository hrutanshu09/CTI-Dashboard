import React from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';

function App() {
  return (
    <div className="flex h-screen bg-background text-white font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        {/* In a multi-page app, you'd have a router here. For now, we directly render Dashboard. */}
        <Dashboard />
      </div>
    </div>
  );
}

export default App;
