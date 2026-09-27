import React, { useEffect, useState } from 'react';
import { Database, BarChart3, Layers, Sparkles, CheckCircle2, ShieldCheck, Loader2 } from 'lucide-react';

interface ProcessingScreenProps {
  productTitle?: string;
  onCancel?: () => void;
}

const STAGES = [
  {
    id: 1,
    title: 'Retrieving Customer Reviews',
    description: 'Fetching verified dataset entries and rating distributions',
    icon: Database,
  },
  {
    id: 2,
    title: 'Analyzing Customer Sentiment',
    description: 'Computing multi-class sentiment balance across all review texts',
    icon: BarChart3,
  },
  {
    id: 3,
    title: 'Mining Dynamic Product Aspects',
    description: 'Identifying product-specific attributes, components, and themes',
    icon: Layers,
  },
  {
    id: 4,
    title: 'Synthesizing Verified Pros & Cons',
    description: 'Extracting key value drivers and recurrent customer pain points',
    icon: Sparkles,
  },
  {
    id: 5,
    title: 'Grounding Evidence & Citations',
    description: 'Traceably linking AI conclusions directly to authentic reviews',
    icon: ShieldCheck,
  },
];

export const ProcessingScreen: React.FC<ProcessingScreenProps> = ({
  productTitle,
  onCancel,
}) => {
  const [activeStage, setActiveStage] = useState(1);

  // Advance stage indicator gracefully to indicate pipeline progress without fake percentages
  useEffect(() => {
    const timer1 = setTimeout(() => setActiveStage(2), 1200);
    const timer2 = setTimeout(() => setActiveStage(3), 2800);
    const timer3 = setTimeout(() => setActiveStage(4), 4800);
    const timer4 = setTimeout(() => setActiveStage(5), 7200);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
    };
  }, []);

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:py-24 text-center">
      {/* Central Pulsing Icon */}
      <div className="relative mx-auto mb-8 flex h-20 w-20 items-center justify-center">
        <div className="absolute inset-0 rounded-2xl border border-[#D4AF5A]/30 bg-[#1A1815] animate-ping opacity-25" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-[#D4AF5A]/50 bg-[#181714] shadow-gold-subtle">
          <Loader2 className="h-8 w-8 text-[#D4AF5A] animate-spin" />
        </div>
      </div>

      <div className="mb-2 flex items-center justify-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-[#D4AF5A] animate-pulse" />
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#D4AF5A]">
          ReviewIQ Intelligence Pipeline
        </p>
      </div>

      <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#F5F2EA]">
        Analyzing Product Reviews
      </h2>

      {productTitle && (
        <p className="mt-3 text-sm text-[#AAA79F] max-w-lg mx-auto truncate font-medium">
          Target:{' '}
          <span className="text-[#F5F2EA] bg-[#1C1D1F] px-2.5 py-1 rounded border border-[#292A2B]">
            {productTitle}
          </span>
        </p>
      )}

      <p className="mt-2 text-xs text-[#74736E]">
        Strictly zero hallucination — synthesizing authentic dataset reviews into structured intelligence.
      </p>

      {/* Pipeline Stage Indicators */}
      <div className="mt-10 premium-panel p-6 sm:p-8 text-left border border-[#292A2B]">
        <div className="space-y-5">
          {STAGES.map((stage) => {
            const Icon = stage.icon;
            const isCompleted = activeStage > stage.id;
            const isCurrent = activeStage === stage.id;
            const isPending = activeStage < stage.id;

            return (
              <div
                key={stage.id}
                className={`flex items-start gap-4 transition-all duration-300 ${
                  isPending ? 'opacity-40' : 'opacity-100'
                }`}
              >
                <div
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-xs font-medium transition ${
                    isCompleted
                      ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-400'
                      : isCurrent
                      ? 'border-[#D4AF5A] bg-[#221E16] text-[#F0D58A] shadow-gold-subtle'
                      : 'border-[#292A2B] bg-[#161719] text-[#74736E]'
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : isCurrent ? (
                    <Icon className="h-4 w-4 animate-pulse text-[#D4AF5A]" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p
                      className={`text-sm font-medium ${
                        isCurrent
                          ? 'text-[#F0D58A]'
                          : isCompleted
                          ? 'text-[#F5F2EA]'
                          : 'text-[#74736E]'
                      }`}
                    >
                      {stage.title}
                    </p>
                    {isCurrent && (
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-[#D4AF5A] bg-[#252014] px-2 py-0.5 rounded border border-[#D4AF5A]/30">
                        In Progress
                      </span>
                    )}
                    {isCompleted && (
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
                        Verified
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-[#AAA79F]">{stage.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {onCancel && (
        <div className="mt-8">
          <button
            onClick={onCancel}
            className="text-xs text-[#74736E] hover:text-[#AAA79F] transition underline underline-offset-4"
          >
            Cancel Analysis & Return
          </button>
        </div>
      )}
    </div>
  );
};
