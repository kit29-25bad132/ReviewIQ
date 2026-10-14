import React, { useEffect, useRef, useState } from 'react';
import {
  HelpCircle,
  Send,
  AlertCircle,
  Package,
  ShieldCheck,
  Search,
} from 'lucide-react';
import type { ProductSummary, RAGQueryResponse } from '../types/ecommerce';
import { askProductQuestion } from '../services/api';
import { ragAnswerState } from '../utils/ragAnswerState';
import { RAG_NO_ANSWER_HINT, RAG_NO_ANSWER_MESSAGE } from '../utils/ragQueryCopy';
import { ProductSearch } from './ProductSearch';

const MAX_QUERY_LENGTH = 2000;

/**
 * Phase 7 Gate 4 — UI surface for `POST /api/products/{product_id}/rag-query`.
 *
 * Renders exactly what the backend returns: a grounded answer with verbatim
 * evidence, or an honest empty/disabled state. Nothing is ever fabricated for
 * an empty answer (empty retrieval, disabled RAG, or an answer discarded by
 * citation validation all legitimately ship `answer: ""`).
 */
export const RagQueryPanel: React.FC = () => {
  const [product, setProduct] = useState<ProductSummary | null>(null);
  const [question, setQuestion] = useState<string>('');
  const [response, setResponse] = useState<RAGQueryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const handleSelectProduct = (selected: ProductSummary) => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setProduct(selected);
    setResponse(null);
    setError('');
    setLoading(false);
  };

  const handleSubmit = async () => {
    if (!product || !question.trim() || loading) return;

    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError('');
    setResponse(null);

    try {
      const res = await askProductQuestion(product.product_id, question, controller.signal);
      setResponse(res);
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'Request was cancelled.') {
        return;
      }
      setError(
        err instanceof Error ? err.message : 'Failed to answer the question from reviews.'
      );
      setResponse(null);
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  };

  const answerState = response ? ragAnswerState(response) : null;
  const canSubmit = Boolean(product) && Boolean(question.trim()) && !loading;

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="border-b border-slate-200 pb-4">
        <h2 className="text-2xl font-bold text-slate-900">Ask the Reviews</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Ask any question about a product — answers are grounded in real canonical dataset
          reviews, with every claim traceable to its evidence.
        </p>
      </div>

      <div className="modern-card p-6 space-y-4 max-w-3xl">
        <div className="space-y-1.5">
          <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
            <Package className="h-3.5 w-3.5 text-[#5B50E5]" />
            <span>Product</span>
          </label>
          <ProductSearch
            onSelectProduct={handleSelectProduct}
            selectedProductId={product?.product_id}
            activeProductName={product?.product_title}
            placeholder="Select a product to ask about (e.g. Zyra Nova 5G, Kelto Gamer 16...)"
          />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="rag-question-input"
            className="text-xs font-bold text-slate-700 flex items-center gap-1.5"
          >
            <HelpCircle className="h-3.5 w-3.5 text-[#5B50E5]" />
            <span>Your question</span>
          </label>
          <form
            className="space-y-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSubmit();
            }}
          >
            <textarea
              id="rag-question-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value.slice(0, MAX_QUERY_LENGTH))}
              maxLength={MAX_QUERY_LENGTH}
              rows={3}
              disabled={loading}
              placeholder="e.g. How is the battery life and what do buyers say about charging?"
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-[#5B50E5] focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-50"
            />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400">
                {question.length}/{MAX_QUERY_LENGTH}
              </span>
              <button
                type="submit"
                disabled={!canSubmit}
                className="primary-button inline-flex items-center gap-2 px-5 py-2.5 text-xs font-bold shadow-md shadow-indigo-500/20 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                <Send className="h-3.5 w-3.5" />
                <span>{loading ? 'Grounding…' : 'Ask the Reviews'}</span>
              </button>
            </div>
          </form>
        </div>
      </div>

      {loading && (
        <div
          role="status"
          aria-live="polite"
          className="modern-card p-8 text-center space-y-3 max-w-3xl animate-fadeIn"
        >
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-[#5B50E5] border-t-transparent" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-900">
              Searching reviews for {product?.product_title || 'the product'}
            </h3>
            <p className="text-xs text-slate-500">
              Semantic retrieval, bounded context, and grounded answer generation...
            </p>
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50/80 p-5 text-xs text-rose-700 flex items-start gap-2 max-w-3xl animate-fadeIn"
        >
          <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {response && answerState && !loading && (
        <div className="modern-card p-6 space-y-5 max-w-3xl animate-fadeIn">
          {answerState === 'disabled' && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-800 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>
                RAG answering is currently disabled on the backend, so no answer can be
                provided for this question.
              </span>
            </div>
          )}

          {answerState === 'no_answer' && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 space-y-1.5">
              <span className="font-bold text-slate-700 block">{RAG_NO_ANSWER_MESSAGE}</span>
              <span>{RAG_NO_ANSWER_HINT}</span>
            </div>
          )}

          {answerState === 'answer' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 border border-indigo-100 px-2.5 py-0.5 text-[10px] font-bold text-indigo-700">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Evidence-grounded answer</span>
                </span>
                {response.model_used && (
                  <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[10px] font-bold text-slate-600">
                    {response.model_used}
                  </span>
                )}
                {response.fallback_used && (
                  <span className="rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-700">
                    Lowered similarity threshold used
                  </span>
                )}
                <span className="rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[10px] font-bold text-slate-600">
                  {response.retrieval_count} review(s) retrieved
                </span>
              </div>

              <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
                {response.answer}
              </p>

              {response.evidence.length > 0 && (
                <div className="space-y-2.5">
                  <h4 className="text-xs font-bold text-slate-700">
                    Evidence ({response.evidence.length})
                  </h4>
                  {response.evidence.map((item) => (
                    <div
                      key={item.review_id}
                      className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-700">
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                          <span>{item.review_id}</span>
                        </span>
                        <span className="flex items-center gap-2 text-[10px] font-semibold text-slate-500">
                          <span className="text-amber-500 font-bold">
                            ★ {item.rating ?? '—'}/5
                          </span>
                          <span>{Math.round(item.similarity_score * 100)}% match</span>
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 italic leading-relaxed">
                        "{item.excerpt}"
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {!product && !response && !error && !loading && (
        <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-10 text-center space-y-3 max-w-3xl">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
            <Search className="h-6 w-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900">Select a product to begin</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Pick a product from the dataset, type a question, and get an answer grounded in
            real customer reviews — every claim cites its source review.
          </p>
        </div>
      )}
    </div>
  );
};

export default RagQueryPanel;
