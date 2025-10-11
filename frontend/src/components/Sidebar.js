import React from 'react';
import { Shield, LayoutDashboard, FileText, BarChart2, Settings } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { icon: <LayoutDashboard size={20} />, name: 'Dashboard' },
    { icon: <Shield size={20} />, name: 'Threat Intel' },
    { icon: <FileText size={20} />, name: 'Log Analyzer' },
    { icon: <BarChart2 size={20} />, name: 'Reporting' },
    { icon: <Settings size={20} />, name: 'Settings' },
  ];

  return (
    <aside className="w-64 bg-panel border-r border-border p-4 flex-col hidden lg:flex">
      <div className="flex items-center gap-3 mb-10 px-2">
        <img src="/logo.png" alt="Logo" className="h-8 w-8" />
        <h1 className="text-xl font-bold text-white">Project Nova</h1>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map((item, index) => (
          <a
            key={index}
            href="#"
            className={`flex items-center gap-3 px-4 py-2.5 rounded-md transition-colors text-sm font-medium
                        ${index === 0 
                          ? 'bg-blue-500/20 text-white' 
                          : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'
                        }`}
          >
            {item.icon}
            <span>{item.name}</span>
          </a>
        ))}
      </nav>
      <div className="mt-auto text-center text-xs text-gray-500">
        <p>CTI Dashboard v1.0.0</p>
        <p>Time: 2025-10-04 17:32</p>
      </div>
    </aside>
  );
};

export default Sidebar;