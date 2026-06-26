import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, loginUser, logoutUser, signupUser } from '../services/auth';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const hydrate = async () => {
      try {
        const data = await getCurrentUser();
        if (mounted) {
          setUser(data.user || null);
        }
      } catch {
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setAuthLoading(false);
        }
      }
    };

    hydrate();
    return () => {
      mounted = false;
    };
  }, []);

  const login = async (credentials) => {
    const data = await loginUser(credentials);
    setUser(data.user || null);
    return data.user || null;
  };

  const signup = async (credentials) => {
    const data = await signupUser(credentials);
    setUser(data.user || null);
    return data.user || null;
  };

  const logout = async () => {
    try {
      await logoutUser();
    } finally {
      setUser(null);
    }
  };

  const value = useMemo(
    () => ({
      user,
      authenticated: Boolean(user),
      authLoading,
      login,
      signup,
      logout,
    }),
    [user, authLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
};
