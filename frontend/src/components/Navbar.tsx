import React, { useEffect, useState } from 'react';
import { Sparkles, Activity, History, MessageSquareQuote, Search, Home } from 'lucide-react';
import { checkBackendHealth } from '../services/api';

export type NavTab = 'home' | 'search' | 'dashboard' | 'analyzer' | 'history';

interface NavbarProps {
  currentTab: NavTab;
  onNavigate: (tab: NavTab) => void;
  hasActiveProduct?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onNavigate,
  hasActiveProduct = false,
}) => {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    let mounted = true;
    checkBackendHealth()
      .then((health) => {
        if (mounted) {
          setBackendStatus(health.status === 'ok' || health.status === 'online' ? 'online' : 'offline');
        }
      })
      .catch(() => {
        if (mounted) setBackendStatus('offline');
      });

    const interval = setInterval(() => {
      checkBackendHealth()
        .then((health) => {
          if (mounted) {
            setBackendStatus(health.status === 'ok' || health.status === 'online' ? 'online' : 'offline');
          }
        })
        .catch(() => {
          if (mounted) setBackendStatus('offline');
        });
    }, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-[#292A2B] bg-[#0E0F10]/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <button
          onClick={() => onNavigate('home')}
          className="flex items-center gap-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#D4AF5A]/60 rounded-md"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#D4AF5A]/40 bg-[#1A1815] shadow-sm">
            <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold tracking-[0.16em] text-[#F5F2EA]">
                REVIEW<span className="text-[#D4AF5A]">IQ</span>
              </span>
              <span className="hidden rounded border border-[#D4AF5A]/30 bg-[#1B1915] px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-[#F0D58A] sm:inline-block">
                Enterprise
              </span>
            </div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#74736E]">
              Product Intelligence
            </p>
          </div>
        </button>

        {/* Navigation tabs */}
        <nav className="hidden md:flex items-center gap-1">
          <button
            onClick={() => onNavigate('home')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition ${
              currentTab === 'home'
                ? 'border border-[#D4AF5A]/30 bg-[#1C1A16] text-[#F0D58A]'
                : 'text-[#AAA79F] hover:bg-[#161719] hover:text-[#F5F2EA]'
            }`}
          >
            <Home className="h-3.5 w-3.5" />
            Home
          </button>

          <button
            onClick={() => onNavigate('search')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition ${
              currentTab === 'search'
                ? 'border border-[#D4AF5A]/30 bg-[#1C1A16] text-[#F0D58A]'
                : 'text-[#AAA79F] hover:bg-[#161719] hover:text-[#F5F2EA]'
            }`}
          >
            <Search className="h-3.5 w-3.5" />
            Product Search
          </button>

          {hasActiveProduct && (
            <button
              onClick={() => onNavigate('dashboard')}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition ${
                currentTab === 'dashboard'
                  ? 'border border-[#D4AF5A]/30 bg-[#1C1A16] text-[#F0D58A]'
                  : 'text-[#AAA79F] hover:bg-[#161719] hover:text-[#F5F2EA]'
              }`}
            >
              <Activity className="h-3.5 w-3.5" />
              Active Dashboard
            </button>
          )}

          <button
            onClick={() => onNavigate('analyzer')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition ${
              currentTab === 'analyzer'
                ? 'border border-[#D4AF5A]/30 bg-[#1C1A16] text-[#F0D58A]'
                : 'text-[#AAA79F] hover:bg-[#161719] hover:text-[#F5F2EA]'
            }`}
          >
            <MessageSquareQuote className="h-3.5 w-3.5" />
            Single Review Analyzer
          </button>

          <button
            onClick={() => onNavigate('history')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition ${
              currentTab === 'history'
                ? 'border border-[#D4AF5A]/30 bg-[#1C1A16] text-[#F0D58A]'
                : 'text-[#AAA79F] hover:bg-[#161719] hover:text-[#F5F2EA]'
            }`}
          >
            <History className="h-3.5 w-3.5" />
            Recent History
          </button>
        </nav>

        {/* Right status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border border-[#292A2B] bg-[#151617] px-3 py-1.5 text-[11px]">
            <span
              className={`h-2 w-2 rounded-full ${
                backendStatus === 'online'
                  ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
                  : backendStatus === 'checking'
                  ? 'bg-[#D4AF5A] animate-pulse'
                  : 'bg-rose-500'
              }`}
            />
            <span className="hidden sm:inline text-[#AAA79F]">
              {backendStatus === 'online'
                ? 'FastAPI AI Engine Connected'
                : backendStatus === 'checking'
                ? 'Connecting to Engine...'
                : 'Engine Offline'}
            </span>
            <span className="sm:hidden text-[#AAA79F]">
              {backendStatus === 'online' ? 'Online' : 'Offline'}
            </span>
          </div>

          <button
            onClick={() => onNavigate('search')}
            className="gold-button hidden sm:flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold"
          >
            <Search className="h-3.5 w-3.5" />
            Analyze Product
          </button>
        </div>
      </div>

      {/* Mobile navigation bar */}
      <div className="flex md:hidden border-t border-[#242526] px-3 py-2 gap-1 overflow-x-auto bg-[#121314]">
        <button
          onClick={() => onNavigate('home')}
          className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
            currentTab === 'home'
              ? 'bg-[#1C1A16] text-[#F0D58A] border border-[#D4AF5A]/30'
              : 'text-[#AAA79F]'
          }`}
        >
          <Home className="h-3.5 w-3.5" /> Home
        </button>
        <button
          onClick={() => onNavigate('search')}
          className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
            currentTab === 'search'
              ? 'bg-[#1C1A16] text-[#F0D58A] border border-[#D4AF5A]/30'
              : 'text-[#AAA79F]'
          }`}
        >
          <Search className="h-3.5 w-3.5" /> Search
        </button>
        {hasActiveProduct && (
          <button
            onClick={() => onNavigate('dashboard')}
            className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
              currentTab === 'dashboard'
                ? 'bg-[#1C1A16] text-[#F0D58A] border border-[#D4AF5A]/30'
                : 'text-[#AAA79F]'
            }`}
          >
            <Activity className="h-3.5 w-3.5" /> Dashboard
          </button>
        )}
        <button
          onClick={() => onNavigate('analyzer')}
          className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
            currentTab === 'analyzer'
              ? 'bg-[#1C1A16] text-[#F0D58A] border border-[#D4AF5A]/30'
              : 'text-[#AAA79F]'
          }`}
        >
          <MessageSquareQuote className="h-3.5 w-3.5" /> Review Text
        </button>
        <button
          onClick={() => onNavigate('history')}
          className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
            currentTab === 'history'
              ? 'bg-[#1C1A16] text-[#F0D58A] border border-[#D4AF5A]/30'
              : 'text-[#AAA79F]'
          }`}
        >
          <History className="h-3.5 w-3.5" /> History
        </button>
      </div>
    </header>
  );
};
