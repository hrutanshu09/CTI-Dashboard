import React from 'react';
import { NavLink } from 'react-router-dom';
import { Shield, LayoutDashboard, FileText, BarChart2, Settings, Bot } from 'lucide-react';

const navItems = [
  { icon: <LayoutDashboard size={20} />, name: 'Dashboard', path: '/' },
  { icon: <Bot size={20} />, name: 'AI Assistant', path: '/ai-assistant' },
  { icon: <Shield size={20} />, name: 'CVE Lookup', path: '/threat-intel' },
  { icon: <FileText size={20} />, name: 'Log Analyzer', path: '/log-analyzer' },
  { icon: <BarChart2 size={20} />, name: 'Report Analyzer', path: '/reporting' },
  { icon: <Settings size={20} />, name: 'Settings', path: '/settings' },
];

const Sidebar = ({ collapsed }) => {
  return (
    <aside
      className={`bg-panel border-r border-border py-4 hidden lg:flex flex-col transition-all duration-300 ease-in-out overflow-hidden ${
        collapsed ? 'w-20 px-3' : 'w-64 px-4'
      }`}
    >
      <div className={`flex items-center mb-10 ${collapsed ? 'justify-center' : 'justify-start gap-0 pr-3 -ml-1'}`}>
        <img src="/logo.png" alt="Logo" className={`w-auto object-contain ${collapsed ? 'h-12' : 'h-16'}`} />
        <h1
          className={`brand-font -ml-1 text-xl font-extrabold text-white whitespace-nowrap transition-all duration-200 ${
            collapsed ? 'opacity-0 w-0 translate-x-1' : 'opacity-100 w-auto translate-x-0'
          }`}
        >
          FlashCTI
        </h1>
      </div>

      <nav className="flex flex-col gap-2">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `flex items-center rounded-md transition-all duration-200 text-sm font-medium ${
                collapsed ? 'justify-center px-2 py-2.5' : 'gap-3 px-4 py-2.5'
              } ${isActive ? 'bg-blue-500/20 text-white' : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'}`
            }
            title={collapsed ? item.name : ''}
          >
            {item.icon}
            <span
              className={`whitespace-nowrap transition-all duration-200 ${
                collapsed ? 'opacity-0 w-0 overflow-hidden' : 'opacity-100 w-auto'
              }`}
            >
              {item.name}
            </span>
          </NavLink>
        ))}
      </nav>

      <div className={`mt-auto text-center text-xs text-gray-500 transition-opacity duration-200 ${collapsed ? 'opacity-0' : 'opacity-100'}`}>
        <p>CTI Dashboard v1.0.0</p>
      </div>
    </aside>
  );
};

export default Sidebar;
