import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';

const PublicProposal = () => {
  const { token } = useParams();

  useEffect(() => {
    // Redirect to backend-rendered proposal page
    // The backend serves full HTML with styling + tracking JS at this endpoint
    window.location.replace(`/api/proposals/public/${token}`);
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#1570EF] mx-auto mb-4"></div>
        <p className="text-[#667085]">Loading proposal...</p>
      </div>
    </div>
  );
};

export default PublicProposal;
