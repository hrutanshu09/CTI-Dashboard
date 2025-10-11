import React from 'react';
import { Bell, UserCircle } from 'lucide-react';
import QueryInput from './QueryInput';

const Navbar = () => {
  return (
    <header className="bg-panel border-b border-border h-16 flex items-center justify-between px-6">
      <div className="flex-1">
        <QueryInput />
      </div>
      <div className="flex items-center gap-4">
        <button className="text-gray-400 hover:text-white transition-colors">
          <Bell size={20} />
        </button>
        <button className="text-gray-400 hover:text-white transition-colors">
          <UserCircle size={24} />
        </button>
      </div>
    </header>
  );
};

export default Navbar;