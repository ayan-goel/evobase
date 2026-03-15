"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createCheckoutSession, getBillingConfig, upgradePlan } from "@/lib/api";

interface PaymentFormProps {
  selectedTier: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function PaymentForm({ selectedTier, onSuccess, onCancel }: PaymentFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stripeLoaded, setStripeLoaded] = useState(false);
  const [stripeInstance, setStripeInstance] = useState<unknown>(null);
  const [elements, setElements] = useState<unknown>(null);
  const [publishableKey, setPublishableKey] = useState<string>("");
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const isPreparingPaymentForm = !error && (!stripeLoaded || !clientSecret || !elements);

  useEffect(() => {
    getBillingConfig()
      .then((config) => {
        setPublishableKey(config.publishable_key);
      })
      .catch(() => {
        setError("Billing not configured. Contact support.");
      });
  }, []);

  useEffect(() => {
    if (!publishableKey) return;
    import("@stripe/stripe-js").then(({ loadStripe }) => {
      loadStripe(publishableKey).then((stripe) => {
        setStripeInstance(stripe);
        setStripeLoaded(true);
      });
    });
  }, [publishableKey]);

  useEffect(() => {
    setClientSecret(null);
    setElements(null);
    setError(null);
    if (containerRef.current) containerRef.current.innerHTML = "";
  }, [selectedTier]);

  useEffect(() => {
    if (!stripeInstance || clientSecret) return;

    let isActive = true;

    void createCheckoutSession(selectedTier)
      .then(({ client_secret }) => {
        if (isActive) setClientSecret(client_secret);
      })
      .catch((err) => {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : "Could not load payment form");
      });

    return () => {
      isActive = false;
    };
  }, [stripeInstance, clientSecret, selectedTier]);

  useEffect(() => {
    if (!clientSecret || !stripeInstance || !containerRef.current || elements) return;

    const stripe = stripeInstance as {
      elements: (opts: object) => {
        create: (type: string, opts: object) => {
          mount: (el: HTMLDivElement) => void;
        };
      };
    };

    const stripeElements = stripe.elements({
      clientSecret: clientSecret,
      appearance: {
        theme: "night",
        variables: { colorBackground: "#111", colorText: "#fff" },
      },
    });
    const paymentElement = stripeElements.create("payment", {});
    paymentElement.mount(containerRef.current);
    setElements(stripeElements);
  }, [clientSecret, stripeInstance, elements]);

  const handleSubmit = useCallback(async () => {
    if (!stripeInstance || !elements || !clientSecret) return;
    setIsLoading(true);
    setError(null);

    try {
      const stripe = stripeInstance as {
        confirmPayment: (opts: object) => Promise<{ error?: { message: string } }>;
      };
      const elems = elements as { submit: () => Promise<{ error?: { message: string } }> };

      const submitResult = await elems.submit();
      if (submitResult.error) {
        setError(submitResult.error.message ?? "Payment submission failed");
        return;
      }

      const result = await stripe.confirmPayment({
        elements,
        clientSecret: clientSecret,
        confirmParams: { return_url: window.location.href },
        redirect: "if_required",
      });

      if (result.error) {
        setError(result.error.message ?? "Payment failed");
      } else {
        await upgradePlan(selectedTier);
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }, [stripeInstance, elements, clientSecret, selectedTier, onSuccess]);

  if (!publishableKey)
    return (
      <div className="rounded-lg border border-white/10 bg-white/[0.03] p-6 text-sm text-white/50">
        {error ?? "Loading billing..."}
      </div>
    );

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-6">
      <p className="mb-4 text-sm text-white/60">
        Enter your payment details to upgrade to <strong className="text-white capitalize">{selectedTier}</strong>.
      </p>

      {isPreparingPaymentForm && (
        <div className="flex min-h-[120px] items-center gap-2 text-sm text-white/40">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
          Preparing secure payment form…
        </div>
      )}

      <div
        ref={containerRef}
        className={isPreparingPaymentForm ? "hidden min-h-[120px]" : "min-h-[120px]"}
      />

      {error && (
        <p className="mt-3 text-xs text-red-400">{error}</p>
      )}

      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !elements}
          className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-black transition-colors hover:bg-white/90 disabled:opacity-50"
        >
          {isLoading ? "Processing…" : `Upgrade to ${selectedTier}`}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-white/10 px-5 py-2 text-sm text-white/70 transition-colors hover:bg-white/[0.04]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
