import { Suspense } from "react";
import { NavWithUser } from "@/components/nav-server";
import { AccountContent } from "./account-content";

export const metadata = { title: "Account — Evobase" };

export default function AccountPage() {
  return (
    <div className="min-h-screen pt-24 pb-16">
      <NavWithUser />
      <div className="mx-auto w-full max-w-2xl px-4">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Account</h1>
          <p className="mt-1 text-sm text-white/50">
            Manage your profile, plan, and billing.
          </p>
        </div>
        <Suspense fallback={<AccountSkeleton />}>
          <AccountContent />
        </Suspense>
      </div>
    </div>
  );
}

function AccountSkeleton() {
  return (
    <div className="space-y-6">
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          className="h-32 rounded-xl border border-white/10 bg-white/[0.03] animate-pulse"
        />
      ))}
    </div>
  );
}
