import { createClient } from "@/lib/supabase/server";
import { Nav } from "@/components/nav";

/** Server wrapper that fetches session user and passes to the client Nav. */
export async function NavWithUser({
  maxWidthClass,
}: {
  maxWidthClass?: string;
} = {}) {
  let navUser = null;

  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (user) {
      const meta = user.user_metadata ?? {};
      navUser = {
        avatar_url: meta.avatar_url ?? undefined,
        github_login:
          meta.user_name ?? meta.preferred_username ?? undefined,
      };
    }
  } catch {
    // Session unavailable — render without user
  }

  return <Nav user={navUser} maxWidthClass={maxWidthClass} />;
}
