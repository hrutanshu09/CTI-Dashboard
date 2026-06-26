import React, { useEffect, useMemo, useState } from 'react';
import { Activity, CheckCircle2, Database, LogOut, RefreshCw, Server, UserCircle2, XCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const MODULE_STATE_KEY = 'cti_dashboard_module_state_v1';
const SIDEBAR_STATE_KEY = 'cti_sidebar_collapsed_v1';

const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';
const ragApiBaseUrl =
  process.env.REACT_APP_AUTH_API_BASE_URL ||
  process.env.REACT_APP_LOG_API_BASE_URL ||
  'http://127.0.0.1:8001';

const StatusBadge = ({ status }) => {
  const online = status === 'online';
  const checking = status === 'checking';

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs font-medium ${
        online
          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
          : checking
            ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
            : 'border-red-500/30 bg-red-500/10 text-red-300'
      }`}
    >
      {online ? <CheckCircle2 size={14} /> : checking ? <RefreshCw size={14} className="animate-spin" /> : <XCircle size={14} />}
      {checking ? 'Checking' : online ? 'Online' : 'Offline'}
    </span>
  );
};

const SettingsPage = () => {
  const { user, logout } = useAuth();
  const [status, setStatus] = useState({
    backend: 'checking',
    ragBackend: 'checking',
  });
  const [cleared, setCleared] = useState(false);

  const displayName = user?.name || 'Authenticated User';
  const initials = useMemo(() => {
    const parts = String(displayName).trim().split(/\s+/).filter(Boolean);
    return (parts[0]?.[0] || user?.email?.[0] || 'U').toUpperCase();
  }, [displayName, user?.email]);

  const checkServices = async () => {
    setStatus({ backend: 'checking', ragBackend: 'checking' });

    const check = async (url) => {
      try {
        const response = await fetch(`${url.replace(/\/$/, '')}/openapi.json`, {
          method: 'GET',
          credentials: 'include',
        });
        return response.ok ? 'online' : 'offline';
      } catch {
        return 'offline';
      }
    };

    const [backend, ragBackend] = await Promise.all([
      check(apiBaseUrl),
      check(ragApiBaseUrl),
    ]);

    setStatus({ backend, ragBackend });
  };

  useEffect(() => {
    checkServices();
  }, []);

  const clearWorkspace = () => {
    window.localStorage.removeItem(MODULE_STATE_KEY);
    window.localStorage.removeItem(SIDEBAR_STATE_KEY);
    setCleared(true);
    window.setTimeout(() => window.location.reload(), 700);
  };

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm text-gray-400 mt-1">Workspace essentials for your local CTI platform.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <section className="xl:col-span-1 border border-border rounded-lg bg-panel p-5">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-lg bg-blue-500/15 border border-blue-500/20 flex items-center justify-center text-blue-200 font-semibold">
              {user?.picture_url ? (
                <img src={user.picture_url} alt="Profile" className="h-full w-full rounded-lg object-cover" />
              ) : (
                initials
              )}
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-white truncate">{displayName}</h2>
              <p className="text-xs text-gray-400 truncate">{user?.email || 'No email available'}</p>
            </div>
          </div>

          <div className="mt-5 space-y-3 text-sm">
            <div className="flex items-center justify-between border border-border rounded-md bg-background/40 px-3 py-2">
              <span className="text-gray-400 flex items-center gap-2">
                <UserCircle2 size={16} />
                Account
              </span>
              <span className="text-gray-200">Local user</span>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full h-10 rounded-md border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </section>

        <section className="xl:col-span-2 border border-border rounded-lg bg-panel p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Activity size={18} className="text-blue-300" />
                System Status
              </h2>
              <p className="text-xs text-gray-400 mt-1">Checks the local APIs used by the dashboard.</p>
            </div>
            <button
              type="button"
              onClick={checkServices}
              className="h-9 rounded-md border border-border px-3 text-sm text-gray-300 hover:text-white hover:border-blue-400 transition-colors flex items-center gap-2"
            >
              <RefreshCw size={15} />
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="border border-border rounded-lg bg-background/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-white flex items-center gap-2">
                    <Server size={16} className="text-gray-400" />
                    Backend API
                  </p>
                  <p className="text-xs text-gray-400 mt-1 break-all">{apiBaseUrl}</p>
                </div>
                <StatusBadge status={status.backend} />
              </div>
              <p className="text-xs text-gray-500 mt-3">CVE lookup and AI assistant service.</p>
            </div>

            <div className="border border-border rounded-lg bg-background/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-white flex items-center gap-2">
                    <Database size={16} className="text-gray-400" />
                    RAG Backend
                  </p>
                  <p className="text-xs text-gray-400 mt-1 break-all">{ragApiBaseUrl}</p>
                </div>
                <StatusBadge status={status.ragBackend} />
              </div>
              <p className="text-xs text-gray-500 mt-3">Authentication, log analyzer, reports, and dashboard metrics.</p>
            </div>
          </div>
        </section>

        <section className="xl:col-span-3 border border-border rounded-lg bg-panel p-5">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-white">Workspace</h2>
              <p className="text-sm text-gray-400 mt-1">Clear saved UI state for reports, logs, CVE lookup, AI chat, and sidebar layout.</p>
            </div>
            <button
              type="button"
              onClick={clearWorkspace}
              className="h-10 rounded-md border border-blue-500/30 bg-blue-500/10 px-4 text-sm font-medium text-blue-200 hover:bg-blue-500/20 transition-colors"
            >
              {cleared ? 'Cleared. Reloading...' : 'Clear local workspace'}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};

export default SettingsPage;
