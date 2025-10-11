import React from 'react';
import { Search } from 'lucide-react';

const QueryInput = () => {
  return (
    <div className="relative w-full max-w-md">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
      <input
        type="text"
        placeholder="Ask AI Assistant... (e.g., 'show recent phishing IOCs')"
        className="w-full bg-background border border-border rounded-md pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-neon-blue"
      />
    </div>
  );
};

export default QueryInput;