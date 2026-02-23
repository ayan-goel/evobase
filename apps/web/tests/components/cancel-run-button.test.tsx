import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CancelRunButton } from "@/components/run-detail/cancel-run-button";

describe("CancelRunButton", () => {
  it("renders the cancel button", () => {
    render(<CancelRunButton runId="run-1" onCancelled={() => {}} />);
    expect(screen.getByText("Cancel Run")).toBeDefined();
  });

  it("shows confirmation dialog on click", () => {
    render(<CancelRunButton runId="run-1" onCancelled={() => {}} />);

    fireEvent.click(screen.getByText("Cancel Run"));

    expect(screen.getByText("Cancel this run?")).toBeDefined();
    expect(screen.getByText("Yes, cancel")).toBeDefined();
    expect(screen.getByText("No")).toBeDefined();
  });

  it("hides confirmation on No click", () => {
    render(<CancelRunButton runId="run-1" onCancelled={() => {}} />);

    fireEvent.click(screen.getByText("Cancel Run"));
    fireEvent.click(screen.getByText("No"));

    expect(screen.getByText("Cancel Run")).toBeDefined();
  });
});
