import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  Target,
  BarChart3,
  CheckCircle,
  AlertCircle,
  Play,
  RefreshCw,
  Info,
  Layers,
  Scale,
  Percent,
} from 'lucide-react';
import { EvaluationMetrics } from '../types/review';
import { getEvaluation, runEvaluation } from '../services/api';
import { StatCard } from './StatCard';

export const EvaluationDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [limit, setLimit] = useState<number>(10);
  const [reanalyze, setReanalyze] = useState<boolean>(false);

  const fetchMetrics = () => {
    setLoading(true);
    setError('');
    getEvaluation()
      .then((data) => {
        setMetrics(data);
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Failed to fetch evaluation metrics.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleRunEvaluation = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await runEvaluation(limit, reanalyze);
      setMetrics(res);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to run evaluation. Please verify Gemini API key in backend/.env'
      );
    } finally {
      setRunning(false);
    }
  };

  // Helper to color confusion matrix cells based on density
  const getMatrixCellStyle = (val: number, maxVal: number, isDiagonal: boolean) => {
    if (val === 0) {
      return 'bg-slate-900/40 text-slate-600';
    }
    const intensity = Math.min(1, val / (maxVal || 1));
    if (isDiagonal) {
      // Correct predictions (Green tint)
      if (intensity > 0.6) return 'bg-emerald-500/40 text-emerald-200 font-bold border border-emerald-500/50';
      if (intensity > 0.3) return 'bg-emerald-500/25 text-emerald-300 font-semibold border border-emerald-500/30';
      return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20';
    } else {
      // Off-diagonal errors (Rose tint)
      if (intensity > 0.4) return 'bg-rose-500/30 text-rose-200 font-bold border border-rose-500/40';
      return 'bg-rose-500/15 text-rose-300 border border-rose-500/20';
    }
  };

  // Find max value in confusion matrix for proportional heatmap
  const maxMatrixVal = metrics?.confusion_matrix
    ? Math.max(...metrics.confusion_matrix.flat(), 1)
    : 1;

  return (
    <div className="space-y-6">
      {/* Evaluation Control Panel */}
      <section className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-400" />
              AI Model Evaluation & Benchmarking
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Quantify Gemini's predicted rating and sentiment accuracy against real ground-truth Amazon reviews.
            </p>
          </div>

          {/* Trigger controls */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400">Sample size:</span>
              <select
                disabled={running}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="rounded-xl border border-slate-700 bg-[#0B0F17] px-3 py-2 text-xs text-white focus:border-purple-500 focus:outline-none"
              >
                <option value="10">10 Reviews (Fast Test)</option>
                <option value="25">25 Reviews</option>
                <option value="50">50 Reviews</option>
                <option value="100">100 Reviews</option>
              </select>
            </div>

            <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                disabled={running}
                checked={reanalyze}
                onChange={(e) => setReanalyze(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-purple-600 focus:ring-purple-500"
              />
              <span>Force Re-analyze</span>
            </label>

            <button
              onClick={handleRunEvaluation}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:brightness-110 disabled:opacity-50 transition duration-200"
            >
              {running ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Evaluating with Gemini...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-white" />
                  <span>Run AI Evaluation</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Informational Banner */}
        <div className="flex items-start gap-2.5 rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-3.5 text-xs text-indigo-300">
          <Info className="h-4 w-4 shrink-0 text-indigo-400 mt-0.5" />
          <div className="leading-relaxed">
            <strong>Evaluation Pipeline:</strong> Evaluates dataset reviews through Gemini AI structured output.
            Actual ground truth rating from Kaggle is compared directly against AI predicted rating (1–5) and sentiment. Results are cached locally in <code className="font-mono bg-indigo-950/80 px-1 py-0.5 rounded">backend/evaluation_results/</code> to avoid redundant API calls.
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {/* Evaluation Results */}
      {loading ? (
        <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-12 text-center space-y-3">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
          <p className="text-xs text-slate-400 font-mono">Loading evaluation results...</p>
        </div>
      ) : !metrics ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-[#111827]/40 p-12 text-center space-y-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800 text-slate-400 mx-auto">
            <Target className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-300">Evaluation not run yet</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            No cached evaluation records found. Click <strong className="text-purple-400">"Run AI Evaluation"</strong> above to benchmark Gemini on a sample of real customer reviews.
          </p>
        </div>
      ) : (
        <div className="space-y-6 animate-fadeIn">
          {/* Metrics KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              title="Rating Accuracy"
              value={`${(metrics.rating_accuracy * 100).toFixed(1)}%`}
              icon={Target}
              color="emerald"
              subtitle="Exact star match"
            />
            <StatCard
              title="Rating MAE"
              value={metrics.rating_mae.toFixed(2)}
              icon={Scale}
              color="purple"
              subtitle="Mean Absolute Error"
            />
            <StatCard
              title="Sentiment Accuracy"
              value={`${(metrics.sentiment_accuracy * 100).toFixed(1)}%`}
              icon={Percent}
              color="cyan"
              subtitle="Derived baseline match"
            />
            <StatCard
              title="Evaluated Records"
              value={metrics.evaluated_reviews}
              icon={Layers}
              color="amber"
              subtitle="Cached benchmark pool"
            />
          </div>

          {/* Confusion Matrix & Methodology */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 5x5 Confusion Matrix */}
            <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-cyan-400" />
                  5x5 Rating Confusion Matrix (Actual vs Predicted)
                </h3>
                <span className="text-[11px] font-mono text-slate-400">
                  Green = Correct • Red = Deviation
                </span>
              </div>

              <div className="overflow-x-auto">
                <div className="inline-block min-w-full">
                  {/* Grid Header */}
                  <div className="text-center text-xs font-semibold text-slate-300 mb-2">
                    AI Predicted Rating (Columns →)
                  </div>

                  <table className="w-full text-center border-collapse">
                    <thead>
                      <tr>
                        <th className="p-2 text-xs font-bold text-slate-400 w-24">
                          Actual (↓)
                        </th>
                        {[1, 2, 3, 4, 5].map((pred) => (
                          <th
                            key={pred}
                            className="p-2 text-xs font-mono font-bold text-cyan-300 w-16"
                          >
                            Pred {pred}★
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.confusion_matrix.map((row, actIdx) => {
                        const actualStar = actIdx + 1;
                        return (
                          <tr key={actualStar}>
                            <td className="p-2 text-xs font-mono font-bold text-amber-300 text-left">
                              Actual {actualStar}★
                            </td>
                            {row.map((val, predIdx) => {
                              const isDiagonal = actIdx === predIdx;
                              const cellStyle = getMatrixCellStyle(
                                val,
                                maxMatrixVal,
                                isDiagonal
                              );
                              return (
                                <td key={predIdx} className="p-1.5">
                                  <div
                                    className={`rounded-lg py-2 font-mono text-xs transition ${cellStyle}`}
                                    title={`Actual: ${actualStar}★, Predicted: ${predIdx + 1}★ (Count: ${val})`}
                                  >
                                    {val}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Methodology & Quality Notes */}
            <div className="rounded-2xl border border-white/10 bg-[#111827]/80 p-6 backdrop-blur-xl shadow-glass flex flex-col justify-between space-y-4">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                  <CheckCircle className="h-4 w-4 text-emerald-400" />
                  Evaluation Methodology
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {metrics.methodology}
                </p>
                <div className="mt-4 space-y-2 text-xs text-slate-400">
                  <p>
                    • <strong>Exact Star Accuracy:</strong> Percentage of reviews where Gemini's rating exactly matches the customer's submitted rating.
                  </p>
                  <p>
                    • <strong>MAE (Mean Absolute Error):</strong> Average star deviation. An MAE of 0.2 means AI predictions deviate by only 0.2 stars on average.
                  </p>
                  <p>
                    • <strong>Anti-Hallucination:</strong> Evaluates purely on review content without leaking ground-truth metadata to the LLM.
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-[#0B0F17] p-3 text-[11px] font-mono text-slate-400 flex items-center justify-between">
                <span>Evaluated Pool: {metrics.evaluated_reviews} items</span>
                <button
                  onClick={fetchMetrics}
                  className="text-purple-400 hover:text-purple-300 transition"
                  title="Reload cached metrics"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
