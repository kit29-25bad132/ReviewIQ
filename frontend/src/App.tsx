import React from 'react';
import { Dashboard } from './pages/Dashboard';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#080B11] text-slate-100 selection:bg-purple-500 selection:text-white">
      <Dashboard />
    </div>
  );
};

export default App;
