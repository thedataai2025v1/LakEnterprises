'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { UserProfile, UserRole } from '@/types/api';
import { api } from '@/lib/api-client';

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  loginAsDemo: (role: UserRole) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  loginAsDemo: async () => {},
  logout: async () => {},
  hasRole: () => false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      try {
        const token = api.getToken();
        if (token) {
          const profile = await api.getMe();
          setUser(profile);
        }
      } catch (err) {
        console.warn('Session verification failed, resetting token', err);
        api.setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  const loginAsDemo = async (role: UserRole) => {
    setLoading(true);
    try {
      await api.loginDemo(role);
      const profile = await api.getMe();
      setUser(profile);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await api.logout();
    } finally {
      setUser(null);
      setLoading(false);
    }
  };

  const hasRole = (roles: UserRole[]): boolean => {
    if (!user) return false;
    const userRole = user.role || (user.roles && user.roles[0] as UserRole);
    return userRole ? roles.includes(userRole) : false;
  };

  return (
    <AuthContext.Provider value={{ user, loading, loginAsDemo, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
