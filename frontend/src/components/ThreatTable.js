import React from 'react';

const ThreatTable = ({ threats }) => {
  const getSeverityClass = (severity) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-900/50 text-neon-red';
      case 'high':
        return 'bg-orange-900/50 text-orange-400';
      case 'medium':
        return 'bg-yellow-900/50 text-yellow-400';
      default:
        return 'bg-blue-900/50 text-blue-400';
    }
  };

  return (
    <div className="overflow-x-auto animate-fade-in">
      <table className="w-full text-sm text-left text-gray-400">
        <thead className="text-xs text-gray-300 uppercase bg-background/50">
          <tr>
            <th scope="col" className="px-4 py-3">Timestamp</th>
            <th scope="col" className="px-4 py-3">Source IP</th>
            <th scope="col" className="px-4 py-3">IOC Found</th>
            <th scope="col" className="px-4 py-3">Type</th>
            <th scope="col" className="px-4 py-3">Severity</th>
          </tr>
        </thead>
        <tbody>
          {threats.map((threat, index) => (
            <tr key={index} className="border-b border-border hover:bg-border/50">
              <td className="px-4 py-2 whitespace-nowrap">{threat.timestamp}</td>
              <td className="px-4 py-2 font-mono">{threat.sourceIp}</td>
              <td className="px-4 py-2 font-mono">{threat.ioc}</td>
              <td className="px-4 py-2">{threat.type}</td>
              <td className="px-4 py-2">
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${getSeverityClass(threat.severity)}`}>
                  {threat.severity}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ThreatTable;     