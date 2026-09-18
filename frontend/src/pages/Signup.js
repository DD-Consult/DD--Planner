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
      <div 
        className="min-h-screen flex items-center justify-center p-4 relative"
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

        <Card 
          className="w-full max-w-md relative z-10 bg-[#1F2937] border-[rgba(148,163,184,0.15)]" 
          data-testid="signup-success-card"
        >
          <CardContent className="p-8 text-center">
            {/* Logo */}
            <img 
              src="https://customer-assets.emergentagent.com/job_resourcy/artifacts/tongpt22_Options%205-transparent%20background%20landscape%20copy%20%282%29.png"
              alt="DD Consulting"
              className="h-12 w-auto mx-auto mb-6"
            />

            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/20 rounded-full mb-4">
              <CheckCircle2 className="w-10 h-10 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold text-[#F8FAFC] mb-2">
              Welcome to DD Planner!
            </h1>
            <p className="text-[#94A3B8] mb-6">
              Your workspace <strong className="text-[#CBD5E1]">{signupResult.tenant_name}</strong> is ready.
            </p>
            <div className="bg-[#141C2B] border border-[#334155] rounded-lg p-4 mb-6 text-left space-y-3 text-sm">
              <div>
                <span className="text-[#94A3B8]">Workspace:</span>{' '}
                <span className="font-mono text-[#F8FAFC]">{signupResult.tenant_slug}</span>
              </div>
              <div>
                <span className="text-[#94A3B8]">Admin email:</span>{' '}
                <span className="font-mono text-[#F8FAFC]">{signupResult.admin_email}</span>
              </div>
              <div className="pt-2 border-t border-[#334155]">
                <div className="text-xs text-[#94A3B8] mb-1">Workspace URL:</div>
                <div className="font-mono text-[#F8FAFC] break-all bg-[#1F2937] px-2 py-1 rounded border border-[#334155]">
                  {signupResult.login_url}
                </div>
              </div>
            </div>
            <a
              href={signupResult.login_url}
              className="inline-flex items-center justify-center gap-2 w-full bg-[#4A90E2] text-white px-4 py-3 rounded-lg hover:bg-[#3A7BC8] transition font-medium"
              data-testid="signup-success-go-to-login-btn"
            >
              Go to Workspace <ArrowRight className="w-4 h-4" />
            </a>
            <div className="text-xs text-[#64748B] mt-4">{signupResult.message}</div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ===== Signup form =====
  return (
    <div 
      className="min-h-screen flex items-center justify-center p-4 relative"
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

      <Card 
        className="w-full max-w-lg relative z-10 bg-[#1F2937] border-[rgba(148,163,184,0.15)]" 
        data-testid="signup-card"
      >
        <CardHeader className="text-center pb-6">
          {/* Logo */}
          <img 
            src="https://customer-assets.emergentagent.com/job_resourcy/artifacts/tongpt22_Options%205-transparent%20background%20landscape%20copy%20%282%29.png"
            alt="DD Consulting"
            className="h-12 w-auto mx-auto mb-6"
          />
          
          {/* Micro label */}
          <div className="text-[#4A90E2] text-xs uppercase tracking-widest font-mono mb-3 opacity-70">
            // New Workspace
          </div>

          <CardTitle 
            className="text-3xl text-[#F8FAFC] uppercase"
            style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
          >
            Start Your Workspace
          </CardTitle>
          <CardDescription className="text-[#94A3B8] mt-2">
            Create your DD Planner workspace in 30 seconds. Free for the first 30 days.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Company name */}
            <div>
              <Label htmlFor="company_name" className="text-[#CBD5E1]">Company name</Label>
              <Input
                id="company_name"
                data-testid="signup-company-name"
                value={form.company_name}
                onChange={(e) => updateField('company_name', e.target.value)}
                placeholder="Acme Consulting"
                autoComplete="organization"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
              {errors.company_name && <p className="text-sm text-red-400 mt-1">{errors.company_name}</p>}
            </div>

            {/* Workspace slug */}
            <div>
              <Label htmlFor="slug" className="text-[#CBD5E1]">
                Workspace URL{' '}
                <span className="text-[#64748B] text-xs">(you can&apos;t change this later)</span>
              </Label>
              <div className="flex items-center gap-2">
                <div className="flex-1 relative">
                  <Input
                    id="slug"
                    data-testid="signup-slug"
                    value={form.slug}
                    onChange={(e) => updateField('slug', e.target.value)}
                    placeholder="acme"
                    className="pr-10 bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {slugCheck.status === 'checking' && <Loader2 className="w-4 h-4 animate-spin text-[#64748B]" />}
                    {slugCheck.status === 'available' && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                    {slugCheck.status === 'taken' && <XCircle className="w-4 h-4 text-red-400" />}
                  </div>
                </div>
                <span className="text-[#94A3B8] text-sm whitespace-nowrap">.ddplanner.io</span>
              </div>
              {slugCheck.status === 'available' && (
                <p className="text-sm text-emerald-400 mt-1" data-testid="signup-slug-available">
                  ✓ Available
                </p>
              )}
              {slugCheck.status === 'taken' && (
                <p className="text-sm text-red-400 mt-1" data-testid="signup-slug-taken">
                  {slugCheck.reason}
                </p>
              )}
              {errors.slug && <p className="text-sm text-red-400 mt-1">{errors.slug}</p>}
            </div>

            {/* Admin name */}
            <div>
              <Label htmlFor="admin_name" className="text-[#CBD5E1]">Your name <span className="text-[#64748B] text-xs">(optional)</span></Label>
              <Input
                id="admin_name"
                data-testid="signup-admin-name"
                value={form.admin_name}
                onChange={(e) => updateField('admin_name', e.target.value)}
                placeholder="Jane Doe"
                autoComplete="name"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
            </div>

            {/* Admin email */}
            <div>
              <Label htmlFor="admin_email" className="text-[#CBD5E1]">Admin email</Label>
              <Input
                id="admin_email"
                data-testid="signup-admin-email"
                type="email"
                value={form.admin_email}
                onChange={(e) => updateField('admin_email', e.target.value)}
                placeholder="jane@acme.com"
                autoComplete="email"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
              {errors.admin_email && <p className="text-sm text-red-400 mt-1">{errors.admin_email}</p>}
            </div>

            {/* Password */}
            <div>
              <Label htmlFor="admin_password" className="text-[#CBD5E1]">Admin password</Label>
              <Input
                id="admin_password"
                data-testid="signup-admin-password"
                type="password"
                value={form.admin_password}
                onChange={(e) => updateField('admin_password', e.target.value)}
                placeholder="At least 8 chars, letters + numbers"
                autoComplete="new-password"
                className="bg-[#141C2B] border-[#334155] text-[#F8FAFC] placeholder:text-[#64748B] focus-visible:ring-[#4A90E2] focus-visible:border-[#4A90E2]"
              />
              {errors.admin_password && <p className="text-sm text-red-400 mt-1">{errors.admin_password}</p>}
            </div>

            <Button
              type="submit"
              className="w-full bg-[#4A90E2] hover:bg-[#3A7BC8] text-white font-medium transition-colors"
              disabled={step === 'submitting' || slugCheck.status === 'taken' || slugCheck.status === 'checking'}
              data-testid="signup-submit-btn"
            >
              {step === 'submitting' ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating your workspace...</>
              ) : (
                <>Create Workspace <ArrowRight className="w-4 h-4 ml-2" /></>
              )}
            </Button>

            <div className="text-center text-sm text-[#94A3B8] pt-2">
              Already have a workspace?{' '}
              <Link to="/login" className="text-[#4A90E2] font-medium hover:underline" data-testid="signup-login-link">
                Sign in
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
