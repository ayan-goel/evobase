import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { OnboardingBanner } from "@/components/onboarding-banner";
import type { Run } from "@/lib/types";

function makeRun(status: Run["status"], id = "run-1"): Run {
  return {
    id,
    repo_id: "repo-1",
    sha: "abc1234",
    status,
    compute_minutes: null,
    failure_step: null,
    commit_message: null,
    created_at: new Date().toISOString(),
  };
}

describe("OnboardingBanner", () => {
  it("renders when single queued run", () => {
    render(<OnboardingBanner runs={[makeRun("queued")]} />);
    expect(
      screen.getByText(/analyzing your repository for the first time/i),
    ).toBeInTheDocument();
  });

  it("renders when single running run", () => {
    render(<OnboardingBanner runs={[makeRun("running")]} />);
    expect(
      screen.getByText(/analyzing your repository for the first time/i),
    ).toBeInTheDocument();
  });

  it("hidden when run is completed", () => {
    const { container } = render(
      <OnboardingBanner runs={[makeRun("completed")]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("hidden when there are multiple runs", () => {
    const { container } = render(
      <OnboardingBanner
        runs={[makeRun("queued", "run-1"), makeRun("completed", "run-2")]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("hidden when runs array is empty", () => {
    const { container } = render(<OnboardingBanner runs={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
