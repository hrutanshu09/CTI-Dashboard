import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'cti_dashboard_module_state_v1';

const defaultState = {
  aiAssistant: {
    messages: [
      { sender: 'ai', text: 'Hello! How can I help you with your threat intelligence tasks today?' }
    ],
    input: ''
  },
  threatIntel: {
    cveId: '',
    cveData: null,
    error: ''
  },
  logAnalyzer: {
    results: [],
    iocDetails: [],
    query: '',
    queryResponse: '',
    queryError: '',
    error: ''
  },
  reporting: {
    reportId: '',
    analysisPayload: null,
    mode: 'hybrid',
    query: '',
    queryResponse: '',
    querySources: [],
    error: '',
    queryError: ''
  }
};

const ModuleStateContext = createContext(null);

const loadInitialState = () => {
  if (typeof window === 'undefined') {
    return defaultState;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState;
    const parsed = JSON.parse(raw);

    return {
      ...defaultState,
      ...parsed,
      aiAssistant: { ...defaultState.aiAssistant, ...(parsed.aiAssistant || {}) },
      threatIntel: { ...defaultState.threatIntel, ...(parsed.threatIntel || {}) },
      logAnalyzer: { ...defaultState.logAnalyzer, ...(parsed.logAnalyzer || {}) },
      reporting: { ...defaultState.reporting, ...(parsed.reporting || {}) }
    };
  } catch {
    return defaultState;
  }
};

export const ModuleStateProvider = ({ children }) => {
  const [state, setState] = useState(loadInitialState);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const setModuleState = (moduleKey, patch) => {
    setState((prev) => ({
      ...prev,
      [moduleKey]: {
        ...prev[moduleKey],
        ...(typeof patch === 'function' ? patch(prev[moduleKey]) : patch)
      }
    }));
  };

  const resetModuleState = (moduleKey) => {
    setState((prev) => ({
      ...prev,
      [moduleKey]: defaultState[moduleKey]
    }));
  };

  const value = useMemo(
    () => ({ state, setModuleState, resetModuleState }),
    [state]
  );

  return <ModuleStateContext.Provider value={value}>{children}</ModuleStateContext.Provider>;
};

export const useModuleState = (moduleKey) => {
  const context = useContext(ModuleStateContext);
  if (!context) {
    throw new Error('useModuleState must be used within a ModuleStateProvider');
  }

  return {
    moduleState: context.state[moduleKey],
    setModuleState: (patch) => context.setModuleState(moduleKey, patch),
    resetModuleState: () => context.resetModuleState(moduleKey)
  };
};
