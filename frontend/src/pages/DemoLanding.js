import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { demoLogin } from '../api';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
  Calendar,
  Users,
  BarChart3,
  Clock,
  FileText,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Briefcase,
  Activity,
  MessageSquare,
} from 'lucide-react';

const DemoLanding = ({ onLaunch }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleLaunchDemo = async () => {
    setLoading(true);
    try {
      const response = await demoLogin();
      const token = response.data.access_token;
      
      // Call the same onLaunch (handleLogin) that the parent passes
      // This stores the token exactly like a normal login
      onLaunch(token);
      
      // Navigate to the main app
      navigate('/');
      
      toast.success('Welcome to the DD Planner demo!');
    } catch (error) {
      console.error('Demo login error:', error);
      toast.error(error.response?.data?.detail || 'Demo is not available right now. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: Briefcase,
      title: 'Portfolio & Meeting Mode',
      description: 'Unified view of all projects with timeline and resource allocation.',
    },
    {
      icon: Users,
      title: 'Resource Allocations & Capacity',
      description: 'Interactive grid showing team capacity across projects and time.',
    },
    {
      icon: Activity,
      title: 'WBS with Gantt & Critical Path',
      description: 'Work breakdown structure with dependencies, baseline tracking, and critical path analysis.',
    },
    {
      icon: Clock,
      title: 'Timesheets & Approvals',
      description: 'Time tracking with autofill from allocations and approval workflows.',
    },
    {
      icon: FileText,
      title: 'Client Report Sharing',
      description: 'Export project reports as PDF/PPT and share via magic links.',
    },
    {
      icon: Sparkles,
      title: 'AI PM Assistant',
      description: 'Natural language commands for project planning, risk analysis, and insights.',
    },
  ];

  return (
    <div
      className="min-h-screen flex flex-col relative"
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
          backgroundSize: '40px 40px',
        }}
      />

      {/* Top Navigation Bar */}
      <nav className="relative z-10 px-6 py-4 flex items-center justify-between border-b border-[#334155]">
        <div className="flex items-center gap-3">
          <img
            src="https://customer-assets.emergentagent.com/job_resourcy/artifacts/tongpt22_Options%205-transparent%20background%20landscape%20copy%20%282%29.png"
            alt="DD Consulting"
            className="h-10 w-auto"
          />
          <span
            className="text-white text-xl font-bold uppercase"
            style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
          >
            DD Planner
          </span>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate('/login')}
          className="bg-transparent border-[#4A90E2] text-[#4A90E2] hover:bg-[#4A90E2] hover:text-white"
          data-testid="demo-to-login"
        >
          Sign in
        </Button>
      </nav>

      {/* Hero Section */}
      <div className="relative z-10 flex-1 flex items-center justify-center px-6 py-16">
        <div className="max-w-5xl w-full text-center">
          {/* Tagline Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-[#1570EF]/10 border border-[#1570EF]/30 rounded-full mb-6">
            <Sparkles size={16} className="text-[#4A90E2]" />
            <span className="text-sm text-[#4A90E2] font-medium">Project Portfolio Management</span>
          </div>

          {/* Main Headline */}
          <h1
            className="text-5xl sm:text-6xl lg:text-7xl mb-6 text-[#F8FAFC] uppercase leading-tight"
            style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
          >
            Resource Planning, WBS,
            <br />
            and Client Reporting
            <br />
            <span className="text-[#4A90E2]">— in One Place.</span>
          </h1>

          <p className="text-lg sm:text-xl text-[#94A3B8] mb-8 max-w-2xl mx-auto">
            DD Planner unifies portfolio management, resource capacity, work breakdown structures, and AI-powered insights for investment professionals.
          </p>

          {/* Primary CTA */}
          <Button
            onClick={handleLaunchDemo}
            disabled={loading}
            className="bg-[#4A90E2] hover:bg-[#3A7BC8] text-white text-lg px-8 py-6 rounded-lg shadow-lg shadow-[#4A90E2]/30 transition-all"
            data-testid="launch-demo-btn"
          >
            {loading ? (
              'Launching Demo...'
            ) : (
              <>
                Launch Live Demo
                <ArrowRight size={20} className="ml-2" />
              </>
            )}
          </Button>

          {/* Note */}
          <p className="text-sm text-[#64748B] mt-4 flex items-center justify-center gap-2">
            <CheckCircle2 size={16} className="text-[#10B981]" />
            The live demo is read-only — explore freely; changes are disabled.
          </p>
        </div>
      </div>

      {/* Features Grid */}
      <div className="relative z-10 px-6 py-16 border-t border-[#334155]">
        <div className="max-w-6xl mx-auto">
          <h2
            className="text-3xl sm:text-4xl text-center mb-12 text-[#F8FAFC] uppercase"
            style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
          >
            Core Capabilities
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, idx) => {
              const Icon = feature.icon;
              return (
                <div
                  key={idx}
                  className="bg-[#1F2937] border border-[#334155] rounded-lg p-6 hover:border-[#4A90E2] transition-colors"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-[#4A90E2]/10 flex items-center justify-center">
                      <Icon size={20} className="text-[#4A90E2]" />
                    </div>
                    <h3 className="text-lg font-semibold text-[#F8FAFC]">{feature.title}</h3>
                  </div>
                  <p className="text-sm text-[#94A3B8] leading-relaxed">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer CTA */}
      <div className="relative z-10 px-6 py-12 border-t border-[#334155] text-center">
        <h3
          className="text-2xl sm:text-3xl mb-4 text-[#F8FAFC] uppercase"
          style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: '0.05em' }}
        >
          Ready to explore?
        </h3>
        <p className="text-[#94A3B8] mb-6">
          Jump into the demo or sign in to create your own workspace.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button
            onClick={handleLaunchDemo}
            disabled={loading}
            className="bg-[#4A90E2] hover:bg-[#3A7BC8] text-white px-6 py-3"
            data-testid="launch-demo-btn-footer"
          >
            {loading ? 'Launching...' : 'Launch Demo'}
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate('/login')}
            className="bg-transparent border-[#4A90E2] text-[#4A90E2] hover:bg-[#4A90E2] hover:text-white px-6 py-3"
          >
            Sign in
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DemoLanding;
