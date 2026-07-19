import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import './index.css';
import './App.css';
import { Toaster } from './components/ui/sonner';
import { SandboxProvider } from './contexts/SandboxContext';

import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';
import Dashboard from './pages/Dashboard';
import Resources from './pages/Resources';
import Projects from './pages/Projects';
import Portfolio from './pages/Portfolio';
import Allocations from './pages/Allocations';
import MyAllocations from './pages/MyAllocations';
import ClientPortal from './pages/ClientPortal';
import ClientPortalMagicLink from './pages/ClientPortalMagicLink';
import ProjectDetail from './pages/ProjectDetail';
import ProjectReport from './pages/ProjectReport';
import Settings from './pages/Settings';
import Holidays from './pages/Holidays';
import Leaves from './pages/Leaves';
import Users from './pages/Users';
import ManageTimesheets from './pages/ManageTimesheets';
import Reports from './pages/Reports';
import TimesheetReports from './pages/TimesheetReports';
import PrintReport from './pages/PrintReport';
import Layout from './components/Layout';
import { getMe, setAuthToken } from './api';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,        // Data fresh for 30 seconds
      refetchOnMount: true,         // Refetch stale data when component mounts (page navigation)
      refetchOnWindowFocus: true,   // Refetch when user tabs back to the app
      retry: 1,
    },
  },
});

// Role-based route wrapper
function ProtectedRoute({ children, allowedRoles }) {
  const [userRole, setUserRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await getMe();
        setUserRole(response.data.role);
      } catch (error) {
        console.error('Error fetching user:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  }

  if (allowedRoles && !allowedRoles.includes(userRole)) {
    // Redirect based on role
    return <Navigate to={userRole === 'client' ? '/portal' : '/'} replace />;
  }

  return children;
}

function App() {
  const [token, setToken] = useState(() => {
    const savedToken = localStorage.getItem('token');
    // Initialize auth header if token exists
    if (savedToken) {
      setAuthToken(savedToken);
    }
    return savedToken;
  });

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      setAuthToken(token);
    } else {
      localStorage.removeItem('token');
      setAuthToken(null);
    }
  }, [token]);

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    setToken(null);
  };

  return (
    <QueryClientProvider client={queryClient}>
      <SandboxProvider>
        <Router>
          <Routes>
            {/* Print/Export routes — UNPROTECTED. Token is passed via ?_t=JWT and
                bootstrapped by PrintReport into localStorage before rendering.
                Used by backend Playwright to render PDF/PPT exports. */}
            <Route path="/print/projects/:id/report" element={<PrintReport />} />
            
            {/* Client Portal Magic Link - PUBLIC route for secure report sharing */}
            <Route path="/portal/:token" element={<ClientPortalMagicLink />} />

            <Route
              path="/login"
              element={
                token ? <Navigate to="/" replace /> : <Login onLogin={handleLogin} />
              }
            />
            <Route
              path="/change-password"
              element={
                token ? <ChangePassword /> : <Navigate to="/login" replace />
              }
            />
            <Route
              path="/*"
              element={
                !token ? (
                  <Navigate to="/login" replace />
                ) : (
                  <Layout token={token} onLogout={handleLogout}>
                  <Routes>
                    <Route 
                      path="/" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource', 'contractor']}>
                          <Dashboard token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/portal" 
                      element={
                        <ProtectedRoute allowedRoles={['client']}>
                          <ClientPortal token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/resources" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                          <Resources token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/projects" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource']}>
                          <Projects token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/portfolio" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                          <Portfolio />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/projects/:id" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource', 'contractor', 'client']}>
                          <ProjectDetail token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/projects/:id/report" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource', 'client']}>
                          <ProjectReport token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/my-allocations" 
                      element={
                        <ProtectedRoute allowedRoles={['resource', 'contractor', 'admin', 'super_admin']}>
                          <MyAllocations token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/allocations" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource', 'contractor']}>
                          <Allocations token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/settings" 
                      element={
                        <ProtectedRoute allowedRoles={['super_admin']}>
                          <Settings token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/users" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                          <Users token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    
                    <Route 
                      path="/manage-timesheets" 
                      element={
                        <ProtectedRoute allowedRoles={['super_admin']}>
                          <ManageTimesheets token={token} />
                        </ProtectedRoute>
                      } 
                    />

                    <Route 
                      path="/reports" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                          <Reports token={token} />
                        </ProtectedRoute>
                      } 
                    />

                    <Route 
                      path="/timesheets/reports" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin']}>
                          <TimesheetReports token={token} />
                        </ProtectedRoute>
                      } 
                    />

                    <Route 
                      path="/holidays" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource']}>
                          <Holidays token={token} />
                        </ProtectedRoute>
                      } 
                    />
                    <Route 
                      path="/leaves" 
                      element={
                        <ProtectedRoute allowedRoles={['admin', 'super_admin', 'resource']}>
                          <Leaves token={token} />
                        </ProtectedRoute>
                      } 
                    />
                  </Routes>
                </Layout>
              )
            }
          />
        </Routes>
      </Router>
      <Toaster />
      {/* <ReactQueryDevtools initialIsOpen={false} /> */}
    </SandboxProvider>
    </QueryClientProvider>
  );
}

export default App;
