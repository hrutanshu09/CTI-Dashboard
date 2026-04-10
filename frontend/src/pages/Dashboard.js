import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import StatsCard from '../components/StatsCard';
import ThreatTable from '../components/ThreatTable';
import { clearDashboardMetrics, getDashboardStats, getRecentAlerts, getSeverityData } from '../services/api';
import { ShieldAlert, ShieldCheck, Siren } from 'lucide-react';
import Loader from '../components/Loader';

// Component for the Donut Chart
const SeverityDonut = ({ refreshKey = 0 }) => {
    const [data, setData] = useState([]);

    useEffect(() => {
        getSeverityData().then(setData);
    }, [refreshKey]);

    if (data.length === 0) {
        return (
            <div className="bg-panel p-6 rounded-lg border border-border flex items-center justify-center h-full">
                <Loader size={24} text=""/>
            </div>
        );
    }

    return (
        <div className="bg-panel p-6 rounded-lg border border-border h-full">
            <h2 className="text-lg font-semibold text-white mb-4">Severity Breakdown</h2>
            <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                    <Pie 
                        data={data} 
                        cx="50%" 
                        cy="50%" 
                        innerRadius={70} 
                        outerRadius={90} 
                        fill="#8884d8" 
                        paddingAngle={5} 
                        dataKey="value"
                    >
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.fill} className="focus:outline-none" />
                        ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#161B22', border: '1px solid #30363d', borderRadius: '0.5rem' }} />
                    <Legend iconType="circle" />
                </PieChart>
            </ResponsiveContainer>
        </div>
    );
};


const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadDashboardData = () => {
    getDashboardStats().then(setStats);
    getRecentAlerts().then(setAlerts);
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleClearDashboard = async () => {
    try {
      await clearDashboardMetrics('all');
      loadDashboardData();
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error(error);
    }
  };

  if (!stats) {
    return <div className="flex-1 p-6 flex items-center justify-center"><Loader /></div>
  }

  return (
    <div className="flex-1 p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <button
          type="button"
          onClick={handleClearDashboard}
          className="text-xs px-3 py-1 rounded-md border border-border text-gray-300 hover:text-white hover:border-neon-blue transition-colors"
        >
          Clear
        </button>
      </div>
      
      {/* Threat Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        <StatsCard title="Total CVEs (Week)" value={stats.totalCVEs} icon={<ShieldCheck size={24} />} />
        <StatsCard title="IOC Detections (24h)" value={stats.iocDetections} icon={<Siren size={24} />} />
        <StatsCard title="Critical Alerts" value={stats.criticalAlerts} icon={<ShieldAlert size={24} />} isCritical={true} />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Alerts Section */}
        <div className="lg:col-span-2 bg-panel p-6 rounded-lg border border-border">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Alerts</h2>
          {alerts.length > 0 ? (
            <ThreatTable threats={alerts} />
          ) : (
            <Loader text="Loading Alerts..." />
          )}
        </div>

        {/* Severity Breakdown Chart */}
        <div className="lg:col-span-1">
          <SeverityDonut refreshKey={refreshKey} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
