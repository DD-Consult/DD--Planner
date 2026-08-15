import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import PlatformLayout from './PlatformLayout';
import PlatformLogin from './pages/PlatformLogin';
import PlatformDashboard from './pages/PlatformDashboard';
import PlatformTenants from './pages/PlatformTenants';
import PlatformTenantDetail from './pages/PlatformTenantDetail';
import PlatformAuditLog from './pages/PlatformAuditLog';
import { setPlatformAuthToken } from './api';

const PlatformApp = () => {
  const [platformToken, setPlatformToken] = useState(() => {
    const saved = localStorage.getItem('platform_token');
    if (saved) {
      setPlatformAuthToken(saved);
    }
    return saved;
  });
  
  const navigate = useNavigate();

  useEffect(() => {
    if (platformToken) {
      localStorage.setItem('platform_token', platformToken);
      setPlatformAuthToken(platformToken);
    } else {
      localStorage.removeItem('platform_token');
      setPlatformAuthToken(null);
    }
  }, [platformToken]);

  const handleLogin = (token) => {
    setPlatformToken(token);
  };

  const handleLogout = () => {
    setPlatformToken(null);
    navigate('/platform/login');
  };

  return (
    <Routes>
      <Route
        path="/login"
        element={
          platformToken ? (
            <Navigate to="/platform" replace />
          ) : (
            <PlatformLogin onLogin={handleLogin} />
          )
        }
      />
      <Route
        path="/*"
        element={
          !platformToken ? (
            <Navigate to="/platform/login" replace />
          ) : (
            <PlatformLayout onLogout={handleLogout}>
              <Routes>
                <Route path="/" element={<PlatformDashboard />} />
                <Route path="/tenants" element={<PlatformTenants />} />
                <Route path="/tenants/:slug" element={<PlatformTenantDetail />} />
                <Route path="/audit-log" element={<PlatformAuditLog />} />
              </Routes>
            </PlatformLayout>
          )
        }
      />
    </Routes>
  );
};

export default PlatformApp;
