import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PaymentForm } from "@/components/billing/payment-form";

const createCheckoutSession = vi.fn();
const getBillingConfig = vi.fn();
const upgradePlan = vi.fn();
const confirmPayment = vi.fn();
const submit = vi.fn();
const mount = vi.fn();
const create = vi.fn(() => ({ mount }));
const elementsFactory = vi.fn(() => ({ create, submit }));
const loadStripe = vi.fn(async () => ({
  elements: elementsFactory,
  confirmPayment,
}));

vi.mock("@/lib/api", () => ({
  createCheckoutSession: (...args: unknown[]) => createCheckoutSession(...args),
  getBillingConfig: (...args: unknown[]) => getBillingConfig(...args),
  upgradePlan: (...args: unknown[]) => upgradePlan(...args),
}));

vi.mock("@stripe/stripe-js", () => ({
  loadStripe: (...args: unknown[]) => loadStripe(...args),
}));

describe("PaymentForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getBillingConfig.mockResolvedValue({ publishable_key: "pk_test_123" });
    createCheckoutSession.mockResolvedValue({ client_secret: "cs_test_123" });
    confirmPayment.mockResolvedValue({});
    submit.mockResolvedValue({});
    upgradePlan.mockResolvedValue({ tier: "hobby", status: "active" });
  });

  it("reuses one checkout session and syncs the plan after payment succeeds", async () => {
    const onSuccess = vi.fn();

    render(
      <PaymentForm
        selectedTier="hobby"
        onSuccess={onSuccess}
        onCancel={() => {}}
      />,
    );

    await waitFor(() => {
      expect(createCheckoutSession).toHaveBeenCalledTimes(1);
    });

    const button = await screen.findByRole("button", { name: "Upgrade to hobby" });
    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });

    fireEvent.click(button);

    await waitFor(() => {
      expect(confirmPayment).toHaveBeenCalledTimes(1);
    });

    expect(createCheckoutSession).toHaveBeenCalledTimes(1);
    expect(upgradePlan).toHaveBeenCalledWith("hobby");
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });
});
