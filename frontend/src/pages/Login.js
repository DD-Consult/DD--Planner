import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, setAuthToken } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle } from 'lucide-react';

const Login = ({ onLogin }) => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await login(email, password);
      console.log('Login response:', response.data);
      const token = response.data.access_token;
      const user = response.data.user;
      
      setAuthToken(token);
      
      // Check if user must change password
      if (user && user.must_change_password) {
        // Call onLogin to set token in parent, which will allow access to /change-password
        console.log('User must change password, setting token and navigating...');
        onLogin(token);
        // Navigate after a short delay to ensure token is set
        setTimeout(() => {
          navigate('/change-password');
        }, 100);
      } else {
        console.log('Calling onLogin...');
        onLogin(token);
      }
    } catch (err) {
      console.error('Login error:', err);
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center relative"
      style={{
        background: 'linear-gradient(to bottom, #1B2436, #141C2B)',
      }}
    >
      {/* Grid texture overlay */}
      <div 
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px'
        }}
      />

      <div className="max-w-md w-full mx-4 relative z-10">
        <div 
          className="bg-[#1F2937] rounded-lg shadow-2xl p-8"
          style={{
            border: '1px solid rgba(148, 163, 184, 0.15)'
          }}
        >
          {/* Logo */}
          <div className="text-center mb-6">
            <img 
              src="https://customer-assets.emergentagent.com/job_resourcy/artifacts/tongpt22_Options%205-transparent%20background%20landscape%20copy%20%282%29.png"
              alt="DD Consulting"
              className="h-12 w-auto mx-auto mb-6"
            />
            
            {/* Micro label */}
            <div className="text-[#4A90E2] text-xs uppercase tracking-widest font-mono mb-3 opacity-70">
              // Secure Access
            </div>
            
            {/* Headline */}
            <h1 
              className="text-4xl mb-2 text-[#F8FAFC] uppercase"
              style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
            >
              DD Planner
            </h1>
            <p className="text-sm text-[#94A3B8]">Resource Planning & Capacity Management</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5" data-testid="login-form">
            <div>
              <Label htmlFor="email" className="text-[#CBD5E1]">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="email-input"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
            </div>

            <div>
              <Label htmlFor="password" className="text-[#CBD5E1]">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="password-input"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
            </div>

            {error && (
              <Alert variant="destructive" data-testid="error-alert" className="bg-red-950/50 border-red-900/50 text-red-200">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              className="w-full bg-[#4A90E2] hover:bg-[#3A7BC8] text-white font-medium transition-colors"
              disabled={loading}
              data-testid="login-button"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-[#94A3B8]">
            New to DD Planner?{' '}
            <a
              href="/signup"
              className="text-[#4A90E2] font-medium hover:underline"
              data-testid="login-signup-link"
            >
              Create a workspace
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
