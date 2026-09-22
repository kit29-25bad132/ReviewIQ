import React from 'react';
import { Sparkles, Cpu } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Analyzing review...",
}) => {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-[#111827]/90 p-10 text-center backdrop-blur-xl shadow-glass">
      {/* Animated glow backgrounds */}
      <div className="absolute -top-20 -left-20 h-40 w-40 rounded-full bg-purple-600/20 blur-3xl animate-pulse" />
      <div className="absolute -bottom-20 -right-20 h-40 w-40 rounded-full bg-cyan-600/20 blur-3xl animate-pulse delay-700" />

      <div className="relative z-10 flex flex-col items-center justify-center space-y-4">
        {/* Animated icon orb */}
        <div className="relative flex h-16 w-16 items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-500 to-cyan-500 opacity-75 blur-md animate-spin" style={{ animationDuration: '3s' }} />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#0B0F17] border border-purple-500/40">
            <Cpu className="h-7 w-7 text-purple-400 animate-pulse" />
          </div>
        </div>

        <div className="space-y-1">
          <h3 className="text-lg font-bold text-white flex items-center justify-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-400 animate-spin" style={{ animationDuration: '4s' }} />
            {message}
          </h3>
          <p className="text-xs text-slate-400 max-w-sm">
            Extracting sentiment, rating, pros, cons, and summary using Gemini AI structured output.
          </p>
        </div>

        {/* Progress skeleton animation */}
        <div className="w-full max-w-xs space-y-2 pt-2">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div className="h-full w-2/5 rounded-full bg-gradient-to-r from-purple-500 via-cyan-400 to-purple-500 animate-[shimmer_1.5s_infinite]" />
          </div>
          <div className="flex justify-between text-[11px] font-mono text-slate-400">
            <span>Anti-hallucination check</span>
            <span className="text-purple-400">Processing...</span>
          </div>
        </div>
      </div>
    </div>
  );
};
