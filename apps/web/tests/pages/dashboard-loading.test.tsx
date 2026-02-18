import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardLoading from "@/app/dashboard/loading";

describe("DashboardLoading", () => {
  it("renders the loading skeleton container", () => {
    render(<DashboardLoading />);
    expect(screen.getByTestId("dashboard-loading")).toBeDefined();
  });

  it("renders three repo card skeletons", () => {
    render(<DashboardLoading />);
    const skeletons = screen.getAllByTestId("repo-card-skeleton");
    expect(skeletons).toHaveLength(3);
  });
});
