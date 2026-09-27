import React from 'react';
import { AlertTriangle, WifiOff, Clock, SearchX, RefreshCw, ArrowLeft } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  type?: 'notFound' | 'offline' | 'timeout' | 'empty' | 'generic';
  onRetry?: () => void;
  onBack?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title,
  message,
  type = 'generic',
  onRetry,
  onBack,
}) => {
  const getIcon = () => {
    switch (type) {
      case 'notFound':
        return <SearchX className="h-8 w-8 text-[#D4AF5A]" />;
      case 'offline':
        return <WifiOff className="h-8 w-8 text-rose-400" />;
      case 'timeout':
        return <Clock className="h-8 w-8 text-amber-400" />;
      case 'empty':
        return <SearchX className="h-8 w-8 text-[#AAA79F]" />;
      default:
        return <AlertTriangle className="h-8 w-8 text-[#D4AF5A]" />;
    }
  };

  const defaultTitle = () => {
    switch (type) {
      case 'notFound':
        return 'Product Not Found';
      case 'offline':
        return 'Backend Service Unavailable';
      case 'timeout':
        return 'Analysis Request Timed Out';
      case 'empty':
        return 'No Review Data Found';
      default:
        return 'Product Intelligence Unavailable';
    }
  };

  const defaultMessage = () => {
    switch (type) {
      case 'notFound':
        return 'The requested product could not be located in the 4M review dataset. Try searching with a broader title or ASIN identifier.';
      case 'offline':
        return 'Unable to reach the ReviewIQ FastAPI backend service. Please verify that the API server is running on the configured host.';
      case 'timeout':
        return 'Processing high-volume review datasets took longer than the 60-second threshold. Please retry to query cached computations.';
      case 'empty':
        return 'No verified customer reviews exist for this product in the current dataset partition.';
      default:
        return 'An unexpected issue occurred while fetching or processing product review intelligence.';
    }
  };

  return (
    <div className="premium-panel mx-auto max-w-xl p-8 sm:p-10 text-center my-12 border border-[#292A2B] shadow-panel">
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-[#292A2B] bg-[#1A1815]">
        {getIcon()}
      </div>

      <h3 className="text-xl font-semibold tracking-tight text-[#F5F2EA]">
        {title || defaultTitle()}
      </h3>

      <p className="mt-3 text-sm leading-6 text-[#AAA79F] max-w-md mx-auto">
        {message || defaultMessage()}
      </p>

      <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
        {onRetry && (
          <button
            onClick={onRetry}
            className="gold-button inline-flex items-center gap-2 px-5 py-2.5 text-xs font-semibold w-full sm:w-auto justify-center"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Try Again
          </button>
        )}

        {onBack && (
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-lg border border-[#292A2B] bg-[#161719] px-5 py-2.5 text-xs font-medium text-[#AAA79F] transition hover:border-[#D4AF5A]/40 hover:text-[#F5F2EA] w-full sm:w-auto justify-center"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Return to Search
          </button>
        )}
      </div>
    </div>
  );
};
