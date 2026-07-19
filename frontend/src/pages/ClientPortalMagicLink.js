import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Loader2, Shield, CheckCircle2, AlertTriangle, Clock, Eye } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import axios from 'axios';

// DD Consulting Brand Colors
const DD_NAVY = '#1B2A47';
const DD_BLUE = '#4A9CC7';
const DD_GOLD = '#C9A84C';

// DD Consulting Logo Component
const DDConsultingLogo = () => (
  <div className="flex items-center gap-3 mb-8">
    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#1B2A47] to-[#4A9CC7] flex items-center justify-center">
      <span className="text-white font-bold text-xl">DD</span>
    </div>
    <div>
      <div className="text-xl font-bold" style={{ color: DD_NAVY }}>DD Consulting</div>
      <div className="text-xs text-gray-500 uppercase tracking-wider">Client Portal</div>
    </div>
  </div>
);

const ClientPortalMagicLink = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  
  // State
  const [step, setStep] = useState('loading'); // loading, verify, report, error
  const [verificationCode, setVerificationCode] = useState('');
  const [linkData, setLinkData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [attempts, setAttempts] = useState(0);

  // Initialize - verify token on mount
  useEffect(() => {
    verifyToken();
  }, [token]);

  const verifyToken = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/portal/verify/${token}`);
      setLinkData(response.data);
      setStep('verify');
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired link');
      setStep('error');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e) => {
    e.preventDefault();
    
    if (verificationCode.length !== 6) {
      setError('Please enter a 6-digit code');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      await axios.post(`/api/portal/verify/${token}/confirm`, {
        verification_code: verificationCode
      });
      
      // Verification successful, fetch report
      await fetchReport();
      
    } catch (err) {
      setAttempts(prev => prev + 1);
      setError(err.response?.data?.detail || 'Invalid verification code');
      
      if (attempts >= 2) {
        setError('Too many failed attempts. Please request a new link.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchReport = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/portal/report/${token}`);
      setReportData(response.data);
      setStep('report');
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load report');
      setStep('error');
    } finally {
      setLoading(false);
    }
  };

  // Loading Screen
  if (step === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <DDConsultingLogo />
            <div className="text-center py-8">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" style={{ color: DD_BLUE }} />
              <p className="text-gray-600">Verifying link...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Error Screen
  if (step === 'error') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <DDConsultingLogo />
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-8 h-8 text-red-600" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Denied</h2>
              <p className="text-gray-600 mb-6">{error}</p>
              <Button onClick={() => navigate('/')} variant="outline">
                Return to Home
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Verification Screen
  if (step === 'verify') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <DDConsultingLogo />
            <CardTitle className="flex items-center gap-2" style={{ color: DD_NAVY }}>
              <Shield className="w-5 h-5" />
              Email Verification Required
            </CardTitle>
            <CardDescription>
              Project: <strong>{linkData?.project_name}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert className="mb-6 border-blue-200 bg-blue-50">
              <AlertDescription className="text-sm">
                A 6-digit verification code has been sent to <strong>{linkData?.recipient_email}</strong>
              </AlertDescription>
            </Alert>

            <form onSubmit={handleVerifyCode} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Verification Code
                </label>
                <Input
                  type="text"
                  maxLength={6}
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="text-center text-2xl tracking-widest font-mono"
                  autoFocus
                />
                <p className="text-xs text-gray-500 mt-2">
                  {3 - attempts} attempt{3 - attempts !== 1 ? 's' : ''} remaining
                </p>
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <Button 
                type="submit" 
                className="w-full"
                disabled={loading || verificationCode.length !== 6}
                style={{ backgroundColor: DD_BLUE }}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Verify & Access Report
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 p-4 bg-gray-50 rounded-lg text-xs text-gray-600">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4" />
                <span>Link expires: {linkData?.expires_at && format(parseISO(linkData.expires_at), 'MMM d, yyyy')}</span>
              </div>
              <p>Didn't receive the code? Check your spam folder or contact your project manager.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Report Display Screen
  if (step === 'report' && reportData) {
    const project = reportData.project;
    
    return (
      <div className="min-h-screen bg-white">
        {/* Header */}
        <div className="border-b border-gray-200 bg-white sticky top-0 z-10 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <DDConsultingLogo />
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <Eye className="w-4 h-4" />
                  <span>Views: {reportData.view_count}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  <span>Expires: {format(parseISO(reportData.expires_at), 'MMM d')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Report Content */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2" style={{ color: DD_NAVY }}>
              {project.name}
            </h1>
            <p className="text-gray-600">
              Project Status Report • Generated {format(parseISO(reportData.created_at), 'MMM d, yyyy')}
            </p>
          </div>

          {/* Project Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">Status</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold" style={{ color: DD_NAVY }}>
                  {project.status || 'Active'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-semibold" style={{ color: DD_NAVY }}>
                  {project.start_date && format(parseISO(project.start_date), 'MMM d')} - {project.end_date && format(parseISO(project.end_date), 'MMM d, yyyy')}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">Budget</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold" style={{ color: DD_NAVY }}>
                  {project.budgeted_hours || 0}h
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Description */}
          {project.description && (
            <Card className="mb-8">
              <CardHeader>
                <CardTitle style={{ color: DD_NAVY }}>Project Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700 whitespace-pre-wrap">{project.description}</p>
              </CardContent>
            </Card>
          )}

          {/* Status Summary */}
          {project.status_summary && (
            <Card className="mb-8">
              <CardHeader>
                <CardTitle style={{ color: DD_NAVY }}>Status Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700 whitespace-pre-wrap">{project.status_summary}</p>
              </CardContent>
            </Card>
          )}

          {/* Footer */}
          <div className="mt-12 pt-8 border-t border-gray-200 text-center text-sm text-gray-500">
            <p className="mb-2">Generated by DD Consulting Project Management Platform</p>
            <p>This report link expires on {format(parseISO(reportData.expires_at), 'MMMM d, yyyy')}</p>
            <p className="mt-4">For questions or updates, please contact your project manager.</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default ClientPortalMagicLink;
