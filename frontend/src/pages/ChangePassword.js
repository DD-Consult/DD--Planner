import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePassword } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Lock, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

const ChangePassword = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (formData.newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (formData.newPassword !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await changePassword(formData.oldPassword, formData.newPassword);
      toast.success('Password changed successfully!');
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FCFCFD] flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="w-12 h-12 rounded-full bg-[#FFF8E5] flex items-center justify-center mx-auto mb-4">
            <Lock className="text-[#F4B740]" size={24} />
          </div>
          <CardTitle style={{ fontFamily: 'Space Grotesk' }}>Change Your Password</CardTitle>
          <p className="text-sm text-[#667085] mt-2">
            For security reasons, please change your password on first login
          </p>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert className="mb-4 border-[#EF4444] bg-[#FEEBEC]">
              <AlertCircle className="h-4 w-4 text-[#EF4444]" />
              <AlertDescription className="text-[#7A1D1D]">{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="oldPassword">Current Password</Label>
              <Input
                id="oldPassword"
                type="password"
                value={formData.oldPassword}
                onChange={(e) => setFormData({ ...formData, oldPassword: e.target.value })}
                required
                className="mt-1"
                data-testid="old-password-input"
              />
            </div>

            <div>
              <Label htmlFor="newPassword">New Password</Label>
              <Input
                id="newPassword"
                type="password"
                value={formData.newPassword}
                onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })}
                required
                minLength={8}
                className="mt-1"
                data-testid="new-password-input"
              />
              <p className="text-xs text-[#667085] mt-1">At least 8 characters</p>
            </div>

            <div>
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                required
                className="mt-1"
                data-testid="confirm-password-input"
              />
            </div>

            <Button 
              type="submit" 
              className="w-full bg-[#1570EF] hover:bg-[#0E5FD9]"
              disabled={loading}
              data-testid="change-password-btn"
            >
              <CheckCircle2 size={16} className="mr-2" />
              {loading ? 'Changing Password...' : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChangePassword;
