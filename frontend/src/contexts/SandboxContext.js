import React, { createContext, useContext, useState } from 'react';

const SandboxContext = createContext();

export const SandboxProvider = ({ children }) => {
  const [showDrafts, setShowDrafts] = useState(false);

  return (
    <SandboxContext.Provider value={{ showDrafts, setShowDrafts }}>
      {children}
    </SandboxContext.Provider>
  );
};

export const useSandbox = () => {
  const context = useContext(SandboxContext);
  if (!context) {
    throw new Error('useSandbox must be used within a SandboxProvider');
  }
  return context;
};
