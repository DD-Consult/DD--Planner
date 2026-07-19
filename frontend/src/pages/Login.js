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
    <div className="min-h-screen flex items-center justify-center bg-[#FCFCFD]">
      <div className="max-w-md w-full mx-4">
        <div className="bg-white border border-[#E6E8EC] rounded-lg shadow-sm p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>
              DD Planner
            </h1>
            <p className="text-sm text-[#667085]">Resource Planning & Capacity Management</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@test.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="email-input"
              />
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="password-input"
              />
            </div>

            {error && (
              <Alert variant="destructive" data-testid="error-alert">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              data-testid="login-button"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>

          <div className="mt-6 p-4 bg-[#F7F7F8] rounded-lg text-xs text-[#475467]">
            <p className="font-medium mb-2">Demo Credentials:</p>
            <p>Admin: admin@test.com / admin123</p>
            <p>Client: client@test.com / client123</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
