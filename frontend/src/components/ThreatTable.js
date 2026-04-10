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
    <div className="w-full animate-fade-in">
      <table className="w-full table-fixed text-xs lg:text-sm text-left text-gray-400">
        <colgroup>
          <col className="w-[22%]" />
          <col className="w-[22%]" />
          <col className="w-[40%]" />
          <col className="w-[16%]" />
        </colgroup>
        <thead className="text-xs text-gray-300 uppercase bg-background/50">
          <tr>
            <th scope="col" className="px-3 py-3">Timestamp</th>
            <th scope="col" className="px-3 py-3">Source IP</th>
            <th scope="col" className="px-3 py-3">IOC Found</th>
            <th scope="col" className="px-3 py-3">Severity</th>
          </tr>
        </thead>
        <tbody>
          {threats.map((threat, index) => (
            <tr key={index} className="border-b border-border hover:bg-border/50">
              <td className="px-3 py-2 align-top break-words">{threat.timestamp}</td>
              <td className="px-3 py-2 align-top font-mono break-words">{threat.sourceIp}</td>
              <td className="px-3 py-2 align-top font-mono break-all">{threat.ioc}</td>
              <td className="px-3 py-2 align-top">
                <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getSeverityClass(threat.severity)}`}>
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
