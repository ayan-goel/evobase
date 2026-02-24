
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Singleton Supabase client to avoid repeated initialization overhead
let _supabaseClient: ReturnType<typeof createClient> | null = null;

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    _supabaseClient ??= createClient();
    const {
      data: { session },
    } = await _supabaseClient.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
    return undefined as T;
  }

  // Modern typed APIs reliably return JSON; parse directly.
  try {
    return (await res.json()) as T;
  } catch {
    return undefined as T;
  }
}

