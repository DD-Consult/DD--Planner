import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { setAuthToken } from '../api';
import ProjectReport from './ProjectReport';

/**
 * Print wrapper component for rendering reports without the main Layout.
 * This component:
 * 1. Extracts the JWT token from URL query param (_t)
 * 2. Sets it in localStorage and API auth header
 * 3. Renders ProjectReport in print mode
 */
const PrintReport = () => {
  const { id: projectId } = useParams();
  const [searchParams] = useSearchParams();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Extract token from URL
    const token = searchParams.get('_t');
    
    if (token) {
      // Set token in localStorage and API
      localStorage.setItem('token', token);
      setAuthToken(token);
    }
    
    // Small delay to ensure token is set before rendering
    setTimeout(() => {
      setReady(true);
    }, 100);
  }, [searchParams]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  // Check if WBS-only view
  const view = searchParams.get('view');
  const isPrint = searchParams.get('print') === '1';
  const isWbsOnly = view === 'wbs';

  return (
    <ProjectReport 
      printMode={isPrint} 
      wbsOnly={isWbsOnly}
    />
  );
};

export default PrintReport;
