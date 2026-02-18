import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

const PUBLIC_ROUTES = new Set(["/", "/login", "/auth/callback"]);

export async function proxy(request: NextRequest) {
  const { user, supabaseResponse } = await updateSession(request);

  const { pathname } = request.nextUrl;

  if (!user && !PUBLIC_ROUTES.has(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
