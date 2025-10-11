import React from 'react';

const StatsCard = ({ title, value, icon, isCritical = false }) => {
  return (
    <div className={`bg-panel p-6 rounded-lg border border-border
                    transition-all duration-300 hover:scale-[1.03] hover:shadow-lg
                    ${isCritical ? 'hover:shadow-red-500/30' : 'hover:shadow-blue-500/30'}`}>
      <div className="flex justify-between items-start">
        <div className="flex flex-col">
          <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider">{title}</h3>
          <p className="text-3xl font-semibold text-white mt-2">{value}</p>
        </div>
        <div className={`p-2 rounded-md ${isCritical ? 'bg-red-500/20 text-neon-red' : 'bg-blue-500/20 text-neon-blue'}`}>
          {icon}
        </div>
      </div>
    </div>
  );
};

export default StatsCard;