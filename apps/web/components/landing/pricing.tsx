import Link from "next/link";

interface Tier {
  id: string;
  name: string;
  price: string | null;
  period?: string;
  description: string;
  highlight: boolean;
  cta: string;
  ctaHref: string;
  features: string[];
}

const TIERS: Tier[] = [
  {
    id: "free",
    name: "Free",
    price: null,
    description: "Try it out — no card required.",
    highlight: false,
    cta: "Start for free",
    ctaHref: "/login",
    features: [
      "1 repository",
      "$5 of included usage",
      "Run stops when budget is reached",
      "All AI providers & models",
      "Automated PR proposals",
    ],
  },
  {
    id: "hobby",
    name: "Hobby",
    price: "$20",
    period: "/month",
    description: "For solo developers and side projects.",
    highlight: false,
    cta: "Get started",
    ctaHref: "/login",
    features: [
      "Up to 5 repositories",
      "$20 of included usage / month",
      "Pay-as-you-go after included usage",
      "All AI providers & models",
      "Automated PR proposals",
      "Usage dashboard",
    ],
  },
  {
    id: "premium",
    name: "Premium",
    price: "$60",
    period: "/month",
    description: "For teams shipping at speed.",
    highlight: true,
    cta: "Get started",
    ctaHref: "/login",
    features: [
      "Unlimited repositories",
      "$60 of included usage / month",
      "Pay-as-you-go after included usage",
      "All AI providers & models",
      "Automated PR proposals",
      "Usage dashboard",
      "Priority support",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "$200",
    period: "/month",
    description: "For power users and large codebases.",
    highlight: false,
    cta: "Get started",
    ctaHref: "/login",
    features: [
      "Unlimited repositories",
      "$200 of included usage / month",
      "Pay-as-you-go after included usage",
      "All AI providers & models",
      "Automated PR proposals",
      "Usage dashboard",
      "Priority support",
      "Custom run schedules",
    ],
  },
];

const ENTERPRISE: Tier = {
  id: "enterprise",
  name: "Enterprise",
  price: null,
  description: "Custom pricing, SLAs, and dedicated support for teams that need more.",
  highlight: false,
  cta: "Contact sales",
  ctaHref: "mailto:ayan@evobase.dev",
  features: [
    "Unlimited repositories",
    "Negotiated usage budget",
    "Custom AI model configuration",
    "Dedicated support & SLA",
    "Custom integrations",
    "SSO / audit logs",
  ],
};

const CHECK_ICON = (
  <svg
    className="h-4 w-4 shrink-0 text-white/50"
    fill="none"
    viewBox="0 0 16 16"
    aria-hidden="true"
  >
    <path
      d="M2.5 8.5l3.5 3.5 7-8"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

function TierCard({ tier }: { tier: Tier }) {
  const isHighlighted = tier.highlight;

  return (
    <div
      className={[
        "relative flex flex-col rounded-2xl border p-6 transition-colors",
        isHighlighted
          ? "border-white/20 bg-white/[0.06]"
          : "border-white/10 bg-white/[0.03]",
      ].join(" ")}
    >
      {isHighlighted && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-white px-3 py-0.5 text-xs font-semibold text-black">
            Most popular
          </span>
        </div>
      )}

      <div className="mb-6">
        <p className="text-sm font-medium text-white/60">{tier.name}</p>
        <div className="mt-2 flex items-baseline gap-1">
          {tier.price ? (
            <>
              <span className="text-3xl font-bold text-white">{tier.price}</span>
              {tier.period && (
                <span className="text-sm text-white/50">{tier.period}</span>
              )}
            </>
          ) : (
            <span className="text-3xl font-bold text-white">Free</span>
          )}
        </div>
        <p className="mt-2 text-sm text-white/50">{tier.description}</p>
      </div>

      <ul className="mb-8 flex flex-col gap-2.5 flex-1">
        {tier.features.map((feature) => (
          <li key={feature} className="flex items-start gap-2.5">
            {CHECK_ICON}
            <span className="text-sm text-white/70">{feature}</span>
          </li>
        ))}
      </ul>

      <Link
        href={tier.ctaHref}
        className={[
          "rounded-lg h-10 px-4 text-sm transition-colors inline-flex items-center justify-center",
          isHighlighted
            ? "bg-white text-black font-semibold hover:bg-white/90"
            : "border border-white/10 text-white font-medium hover:bg-white/[0.06]",
        ].join(" ")}
      >
        {tier.cta}
      </Link>
    </div>
  );
}

function EnterpriseCard({ tier }: { tier: Tier }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 flex flex-col sm:flex-row sm:items-center gap-6">
      {/* Left: name + price + description */}
      <div className="shrink-0 sm:w-48">
        <p className="text-sm font-medium text-white/60">{tier.name}</p>
        <p className="mt-1 text-3xl font-bold text-white">Custom</p>
        <p className="mt-1.5 text-sm text-white/50">{tier.description}</p>
      </div>

      {/* Middle: features in two even columns */}
      <ul className="grid grid-cols-2 gap-x-8 gap-y-2 flex-1">
        {tier.features.map((feature) => (
          <li key={feature} className="flex items-center gap-2">
            {CHECK_ICON}
            <span className="text-sm text-white/70">{feature}</span>
          </li>
        ))}
      </ul>

      {/* Right: CTA */}
      <div className="shrink-0">
        <a
          href={tier.ctaHref}
          className="rounded-lg border border-white/10 text-white h-10 px-6 text-sm font-medium transition-colors hover:bg-white/[0.06] inline-flex items-center justify-center whitespace-nowrap"
        >
          {tier.cta}
        </a>
      </div>
    </div>
  );
}

export function Pricing() {
  return (
    <section className="w-full py-24">
      <div className="mx-auto max-w-4xl px-4">
        <div className="mb-12 text-center">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl text-white">
            Simple, usage-based pricing
          </h2>
          <p className="mt-3 text-sm text-white/50">
            Pay for what you use. No surprises.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {TIERS.map((tier) => (
            <TierCard key={tier.id} tier={tier} />
          ))}
        </div>

        <div className="mt-4">
          <EnterpriseCard tier={ENTERPRISE} />
        </div>

        <p className="mt-8 text-center text-xs text-white/30">
          Usage resets monthly. Pay as you go once your usage limit is met.
        </p>
      </div>
    </section>
  );
}
