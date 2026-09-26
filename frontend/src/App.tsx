import React from 'react';
import { Dashboard } from './pages/Dashboard';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#0E0F10] text-[#F5F2EA] selection:bg-[#D4AF5A] selection:text-[#111111]">
      <Dashboard />
    </div>
  );
};

export default App;
