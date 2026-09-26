import React from 'react';
import { Sparkles, Cpu } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Analyzing review...",
}) => {
  return (
    <div className="premium-panel p-10 text-center relative overflow-hidden">
      <div className="relative z-10 flex flex-col items-center justify-center space-y-4">
        {/* Animated icon orb */}
        <div className="relative flex h-14 w-14 items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-[#D4AF5A] to-[#B98B28] opacity-60 blur-md animate-spin" style={{ animationDuration: '3s' }} />
          <div className="relative flex h-12 w-12 items-center justify-center rounded-full bg-[#151617] border border-[#D4AF5A]/40">
            <Cpu className="h-6 w-6 text-[#D4AF5A] animate-pulse" />
          </div>
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-medium text-[#F5F2EA] flex items-center justify-center gap-2">
            <Sparkles className="h-4 w-4 text-[#D4AF5A]" />
            {message}
          </h3>
          <p className="text-xs text-[#AAA79F] max-w-sm">
            Extracting sentiment, rating, pros, cons, and summary using Gemini AI structured output.
          </p>
        </div>

        {/* Progress skeleton animation */}
        <div className="w-full max-w-xs space-y-2 pt-2">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#292A2B]">
            <div className="h-full w-2/5 rounded-full bg-gradient-to-r from-[#D4AF5A] via-[#F0D58A] to-[#D4AF5A] animate-[pulse_1.5s_infinite]" />
          </div>
          <div className="flex justify-between text-[10px] font-mono text-[#74736E]">
            <span>Anti-hallucination validation</span>
            <span className="text-[#D4AF5A]">Processing...</span>
          </div>
        </div>
      </div>
    </div>
  );
};
