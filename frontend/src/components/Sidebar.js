import React from 'react';
import { NavLink } from 'react-router-dom';
import { Shield, LayoutDashboard, FileText, BarChart2, Settings, Bot } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { icon: <LayoutDashboard size={20} />, name: 'Dashboard', path: '/' },
    { icon: <Bot size={20} />, name: 'AI Assistant', path: '/ai-assistant' },
    { icon: <Shield size={20} />, name: 'Threat Intel', path: '/threat-intel' },
    { icon: <FileText size={20} />, name: 'Log Analyzer', path: '/log-analyzer' },
    { icon: <BarChart2 size={20} />, name: 'Reporting', path: '/reporting' },
    { icon: <Settings size={20} />, name: 'Settings', path: '/settings' },
  ];

  return (
    <aside className="w-64 bg-panel border-r border-border p-4 flex-col hidden lg:flex">
      <div className="flex w-full items-center justify-start gap-0 mb-10 pr-3 -ml-1">
        <img src="/logo.png" alt="Logo" className="h-16 w-auto object-contain" />
        <h1 className="brand-font -ml-1 text-xl font-extrabold text-white">FlashCTI</h1>
      </div>
      
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-md transition-colors text-sm font-medium
               ${isActive 
                 ? 'bg-blue-500/20 text-white' 
                 : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'
               }`
            }
          >
            {item.icon}
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto text-center text-xs text-gray-500">
        <p>CTI Dashboard v1.0.0</p>
        <p>Time: 2025-10-12 20:55</p>
      </div>
    </aside>
  );
};

export default Sidebar;

