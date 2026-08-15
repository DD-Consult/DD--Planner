/**
 * Public sign-up page — creates a new tenant workspace.
 *
 * Flow:
 *   1. User fills in slug, company name, admin email, password
 *   2. Slug availability is checked live (debounced) via GET /api/signup/check-slug
 *   3. Submit → POST /api/signup → success screen with login link
 *
 * This page is INTENTIONALLY unauthenticated. It bypasses the ProtectedRoute
 * guards in App.js because it needs to be reachable by anyone visiting the
 * marketing site.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { CheckCircle2, XCircle, Loader2, Building2, ArrowRight } from 'lucide-react';

// Signup uses relative /api base — Kubernetes ingress + nginx routes to backend
const signupApi = axios.create({ baseURL: '/api/signup' });

export default function Signup() {
  const navigate = useNavigate();
  const [step, setStep] = useState('form'); // 'form' | 'submitting' | 'success'
  const [form, setForm] = useState({
    slug: '',
    company_name: '',
    admin_email: '',
    admin_password: '',
    admin_name: '',
  });
  const [slugCheck, setSlugCheck] = useState({ status: 'idle', reason: null });
  const [errors, setErrors] = useState({});
  const [signupResult, setSignupResult] = useState(null);

  // Debounced slug availability check
  useEffect(() => {
    if (!form.slug || form.slug.length < 3) {
      setSlugCheck({ status: 'idle', reason: null });
      return;
    }
    setSlugCheck({ status: 'checking', reason: null });
    const timer = setTimeout(async () => {
      try {
        const r = await signupApi.get(`/check-slug?slug=${encodeURIComponent(form.slug)}`);
        setSlugCheck({
          status: r.data.available ? 'available' : 'taken',
          reason: r.data.reason,
        });
      } catch (e) {
        setSlugCheck({ status: 'error', reason: 'Check failed' });
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [form.slug]);

  const updateField = (field, value) => {
    // Slug: force lowercase and strip disallowed chars as user types
    if (field === 'slug') {
      value = value.toLowerCase().replace(/[^a-z0-9_-]/g, '');
    }
    setForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: null }));
  };

  const validateBeforeSubmit = () => {
    const e = {};
    if (form.slug.length < 3) e.slug = 'Must be at least 3 characters';
    if (slugCheck.status === 'taken') e.slug = slugCheck.reason || 'Not available';
    if (form.company_name.trim().length < 2) e.company_name = 'Please enter your company name';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.admin_email)) e.admin_email = 'Enter a valid email address';
    if (form.admin_password.length < 8) e.admin_password = 'At least 8 characters';
    else if (!/[a-zA-Z]/.test(form.admin_password)) e.admin_password = 'Must contain a letter';
    else if (!/\d/.test(form.admin_password)) e.admin_password = 'Must contain a number';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateBeforeSubmit()) return;
    setStep('submitting');
    try {
      const r = await signupApi.post('', form);
      setSignupResult(r.data);
      setStep('success');
      toast.success(`Workspace "${r.data.tenant_name}" created!`);
    } catch (err) {
      setStep('form');
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        toast.error(detail);
        if (detail.toLowerCase().includes('slug')) {
          setErrors({ slug: detail });
        }
      } else if (Array.isArray(detail)) {
        // Pydantic validation error array
        const msgs = detail.map(d => d.msg).join('; ');
        toast.error(msgs);
      } else {
        toast.error('Sign-up failed. Please try again.');
      }
    }
  };

  // ===== Success screen =====
  if (step === 'success' && signupResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md" data-testid="signup-success-card">
          <CardContent className="p-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-full mb-4">
              <CheckCircle2 className="w-10 h-10 text-emerald-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              Welcome to DD Planner!
            </h1>
            <p className="text-slate-600 mb-6">
              Your workspace <strong>{signupResult.tenant_name}</strong> is ready.
            </p>
            <div className="bg-slate-50 rounded-lg p-4 mb-6 text-left space-y-2 text-sm">
              <div>
                <span className="text-slate-500">Workspace:</span>{' '}
                <span className="font-mono text-slate-900">{signupResult.tenant_slug}</span>
              </div>
              <div>
                <span className="text-slate-500">Admin email:</span>{' '}
                <span className="font-mono text-slate-900">{signupResult.admin_email}</span>
              </div>
            </div>
            <a
              href={signupResult.login_url}
              className="inline-flex items-center justify-center gap-2 w-full bg-slate-900 text-white px-4 py-3 rounded-lg hover:bg-slate-800 transition font-medium"
              data-testid="signup-success-go-to-login-btn"
            >
              Go to Workspace <ArrowRight className="w-4 h-4" />
            </a>
            <div className="text-xs text-slate-400 mt-4">{signupResult.message}</div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ===== Signup form =====
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg" data-testid="signup-card">
        <CardHeader className="text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-slate-900 rounded-full mb-3 mx-auto">
            <Building2 className="w-7 h-7 text-white" />
          </div>
          <CardTitle className="text-2xl">Start your workspace</CardTitle>
          <CardDescription>
            Create your DD Planner workspace in 30 seconds. Free for the first 30 days.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Company name */}
            <div>
              <Label htmlFor="company_name">Company name</Label>
              <Input
                id="company_name"
                data-testid="signup-company-name"
                value={form.company_name}
                onChange={(e) => updateField('company_name', e.target.value)}
                placeholder="Acme Consulting"
                autoComplete="organization"
              />
              {errors.company_name && <p className="text-sm text-red-600 mt-1">{errors.company_name}</p>}
            </div>

            {/* Workspace slug */}
            <div>
              <Label htmlFor="slug">
                Workspace URL{' '}
                <span className="text-slate-400 text-xs">(you can't change this later)</span>
              </Label>
              <div className="flex items-center gap-2">
                <div className="flex-1 relative">
                  <Input
                    id="slug"
                    data-testid="signup-slug"
                    value={form.slug}
                    onChange={(e) => updateField('slug', e.target.value)}
                    placeholder="acme"
                    className="pr-10"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {slugCheck.status === 'checking' && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                    {slugCheck.status === 'available' && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                    {slugCheck.status === 'taken' && <XCircle className="w-4 h-4 text-red-500" />}
                  </div>
                </div>
                <span className="text-slate-500 text-sm whitespace-nowrap">.ddplanner.io</span>
              </div>
              {slugCheck.status === 'available' && (
                <p className="text-sm text-emerald-600 mt-1" data-testid="signup-slug-available">
                  ✓ Available
                </p>
              )}
              {slugCheck.status === 'taken' && (
                <p className="text-sm text-red-600 mt-1" data-testid="signup-slug-taken">
                  {slugCheck.reason}
                </p>
              )}
              {errors.slug && <p className="text-sm text-red-600 mt-1">{errors.slug}</p>}
            </div>

            {/* Admin name */}
            <div>
              <Label htmlFor="admin_name">Your name <span className="text-slate-400 text-xs">(optional)</span></Label>
              <Input
                id="admin_name"
                data-testid="signup-admin-name"
                value={form.admin_name}
                onChange={(e) => updateField('admin_name', e.target.value)}
                placeholder="Jane Doe"
                autoComplete="name"
              />
            </div>

            {/* Admin email */}
            <div>
              <Label htmlFor="admin_email">Admin email</Label>
              <Input
                id="admin_email"
                data-testid="signup-admin-email"
                type="email"
                value={form.admin_email}
                onChange={(e) => updateField('admin_email', e.target.value)}
                placeholder="jane@acme.com"
                autoComplete="email"
              />
              {errors.admin_email && <p className="text-sm text-red-600 mt-1">{errors.admin_email}</p>}
            </div>

            {/* Password */}
            <div>
              <Label htmlFor="admin_password">Admin password</Label>
              <Input
                id="admin_password"
                data-testid="signup-admin-password"
                type="password"
                value={form.admin_password}
                onChange={(e) => updateField('admin_password', e.target.value)}
                placeholder="At least 8 chars, letters + numbers"
                autoComplete="new-password"
              />
              {errors.admin_password && <p className="text-sm text-red-600 mt-1">{errors.admin_password}</p>}
            </div>

            <Button
              type="submit"
              className="w-full bg-slate-900 hover:bg-slate-800"
              disabled={step === 'submitting' || slugCheck.status === 'taken' || slugCheck.status === 'checking'}
              data-testid="signup-submit-btn"
            >
              {step === 'submitting' ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating your workspace...</>
              ) : (
                <>Create Workspace <ArrowRight className="w-4 h-4 ml-2" /></>
              )}
            </Button>

            <div className="text-center text-sm text-slate-500 pt-2">
              Already have a workspace?{' '}
              <Link to="/login" className="text-slate-900 font-medium hover:underline" data-testid="signup-login-link">
                Sign in
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
