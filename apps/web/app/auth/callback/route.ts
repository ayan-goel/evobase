import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=missing_code`);
  }

  const cookieStore = await cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        },
      },
    },
  );

  const { error: exchangeError } =
    await supabase.auth.exchangeCodeForSession(code);

  if (exchangeError) {
    return NextResponse.redirect(`${origin}/login?error=exchange_failed`);
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    const meta = user.user_metadata ?? {};
    try {
      await fetch(`${API_BASE}/auth/github-callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          supabase_user_id: user.id,
          github_id: meta.provider_id
            ? parseInt(meta.provider_id, 10)
            : 0,
          github_login: meta.user_name ?? meta.preferred_username ?? "",
          avatar_url: meta.avatar_url ?? "",
          email: user.email ?? "",
        }),
      });
    } catch {
      // Non-fatal: user row will be created by the JWT dependency on next API call
    }
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
