import { createClient } from "@/lib/supabase/server";
import {
  getBillingSubscription,
  getBillingUsage,
  type BillingSubscription,
  type BillingUsage,
} from "@/lib/api-server";
import { AccountClient } from "./account-client";

export async function AccountContent() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  let subscription: BillingSubscription | null = null;
  let usage: BillingUsage | null = null;

  try {
    [subscription, usage] = await Promise.all([
      getBillingSubscription(),
      getBillingUsage(),
    ]);
  } catch {
    // Not authenticated or API unavailable — show limited UI
  }

  return (
    <AccountClient
      email={user?.email ?? ""}
      avatarUrl={user?.user_metadata?.avatar_url ?? null}
      githubLogin={user?.user_metadata?.user_name ?? null}
      subscription={subscription}
      usage={usage}
    />
  );
}
