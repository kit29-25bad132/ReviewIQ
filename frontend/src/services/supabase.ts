import { createClient, SupabaseClient } from '@supabase/supabase-js';

const isPlaceholderValue = (value: string): boolean =>
  /your-project|your-supabase|change-me|replace-me|placeholder/i.test(value);

const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL || '').trim();
const supabaseKeyCandidates = [
  (import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim(),
  (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '').trim(),
];
const supabaseKey =
  supabaseKeyCandidates.find((value) => value && !isPlaceholderValue(value)) || '';

const isValidSupabaseUrl = (value: string): boolean => {
  if (!value || isPlaceholderValue(value)) return false;

  try {
    const parsedUrl = new URL(value);
    return (
      (parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:') &&
      Boolean(parsedUrl.hostname)
    );
  } catch {
    return false;
  }
};

const hasValidEnvironment = Boolean(
  isValidSupabaseUrl(supabaseUrl) &&
    supabaseKey &&
    !isPlaceholderValue(supabaseKey)
);

let configurationError: string | null = null;
let client: SupabaseClient | null = null;

if (!hasValidEnvironment) {
  configurationError =
    'Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (or VITE_SUPABASE_PUBLISHABLE_KEY) in frontend/.env, then restart or rebuild the frontend.';
} else {
  try {
    client = createClient(supabaseUrl, supabaseKey);
  } catch (error) {
    configurationError = 'The Supabase client could not be initialized from the frontend environment.';
    console.error('Supabase client initialization error', {
      code: 'SUPABASE_CLIENT_INIT_FAILED',
      message: error instanceof Error ? error.message : String(error),
      details: null,
      hint: 'Verify VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (or VITE_SUPABASE_PUBLISHABLE_KEY), then restart or rebuild the frontend.',
    });
  }
}

export const supabase: SupabaseClient | null = client;
export const isSupabaseConfigured = client !== null;
export const supabaseConfigurationError: string | null = configurationError;
