import React, { createContext, useState, useEffect, useContext } from 'react';
import apiClient from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('reviewflow_token');
    const savedUser = localStorage.getItem('reviewflow_user');
    if (token && savedUser) {
      setUser(JSON.parse(savedUser));
      fetchMe();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchMe = async () => {
    try {
      const res = await apiClient.get('/auth/me');
      setUser(res.data);
      localStorage.setItem('reviewflow_user', JSON.stringify(res.data));
    } catch (err) {
      console.error('Failed to fetch profile', err);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const res = await apiClient.post('/auth/login-json', { email, password });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('reviewflow_token', access_token);
    localStorage.setItem('reviewflow_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const register = async (fullName, email, password, companyName) => {
    const res = await apiClient.post('/auth/register', {
      full_name: fullName,
      email,
      password,
      company_name: companyName
    });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('reviewflow_token', access_token);
    localStorage.setItem('reviewflow_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('reviewflow_token');
    localStorage.removeItem('reviewflow_user');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, refreshProfile: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
