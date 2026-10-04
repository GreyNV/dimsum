/** Public client configuration. The publishable key is safe to ship: the saves table
 * has no direct access, and the save/load functions require the player's secret. */
export const SUPABASE_URL = 'https://blspmfqqwacvbxwcehur.supabase.co';
export const SUPABASE_KEY = 'sb_publishable_LAagZbcKaahrq4l67O4XLQ_-DGaVfO6';
export const LOCAL_SAVE_MS = 10_000;
export const CLOUD_SAVE_MS = 60_000;
