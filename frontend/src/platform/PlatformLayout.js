import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { platformLogout, setPlatformAuthToken } from './api';
import { Button } from '../components/ui/button';
import { LayoutDashboard, Building2, FileText, User, LogOut, Shield } from 'lucide-react';
import { toast } from 'sonner';

const PlatformLayout = ({ children }) => {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await platformLogout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setPlatformAuthToken(null);
      navigate('/platform/login');
    }
  };

  const navItems = [
    { path: '/platform', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/platform/tenants', label: 'Tenants', icon: Building2 },
    { path: '/platform/audit-log', label: 'Audit Log', icon: FileText },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
        {/* Logo/Header */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-indigo-600 rounded-lg">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white" style={{ fontFamily: 'Space Grotesk' }}>
                DD Planner
              </h1>
              <p className="text-xs text-slate-400">Platform Admin</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/platform'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`
              }
              data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-medium">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Logout button */}
        <div className="p-4 border-t border-slate-800">
          <Button
            variant="ghost"
            className="w-full justify-start text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            onClick={handleLogout}
            data-testid="platform-logout-button"
          >
            <LogOut className="h-5 w-5 mr-3" />
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 min-h-screen">
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  );
};

export default PlatformLayout;
