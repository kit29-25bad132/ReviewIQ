export interface RecentProductHistoryItem {
  productId: string;
  productTitle: string;
  category?: string | null;
  overallRating: number;
  reviewCount: number;
  analyzedAt: string;
}

const STORAGE_KEY = 'reviewiq-analyzed-products';

export function getProductHistory(): RecentProductHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function saveProductToHistory(item: Omit<RecentProductHistoryItem, 'analyzedAt'>): void {
  try {
    const existing = getProductHistory().filter((p) => p.productId !== item.productId);
    const updated: RecentProductHistoryItem = {
      ...item,
      analyzedAt: new Date().toISOString(),
    };
    const nextList = [updated, ...existing].slice(0, 10);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextList));
  } catch (e) {
    console.warn('Failed to save product to history:', e);
  }
}

export function clearProductHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    console.warn('Failed to clear product history:', e);
  }
}