import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { platformLogin, setPlatformAuthToken } from '../api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { AlertCircle, Shield } from 'lucide-react';

const PlatformLogin = ({ onLogin }) => {
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
      const response = await platformLogin(email, password);
      const token = response.data.access_token;
      
      setPlatformAuthToken(token);
      onLogin(token);
      navigate('/platform');
    } catch (err) {
      console.error('Platform login error:', err);
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="max-w-md w-full mx-4">
        <div className="bg-slate-900 border border-slate-800 rounded-lg shadow-xl p-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-600 rounded-full mb-4">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-3xl font-semibold text-white mb-2" style={{ fontFamily: 'Space Grotesk' }}>
              DD Planner
            </h1>
            <p className="text-sm text-slate-400">Platform Admin Portal</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" data-testid="platform-login-form">
            <div>
              <Label htmlFor="email" className="text-slate-300">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@platform.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                data-testid="platform-email-input"
              />
            </div>

            <div>
              <Label htmlFor="password" className="text-slate-300">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                data-testid="platform-password-input"
              />
            </div>

            {error && (
              <Alert variant="destructive" data-testid="platform-error-alert" className="bg-red-900/20 border-red-900 text-red-400">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
              disabled={loading}
              data-testid="platform-login-button"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>

          <div className="mt-6 text-center text-xs text-slate-500">
            Platform administrators only
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlatformLogin;
