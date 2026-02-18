import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RepoLoading from "@/app/repos/[repoId]/loading";

describe("RepoLoading", () => {
  it("renders the loading skeleton container", () => {
    render(<RepoLoading />);
    expect(screen.getByTestId("repo-loading")).toBeDefined();
  });

  it("renders run skeleton placeholders", () => {
    render(<RepoLoading />);
    const runSkeletons = screen.getAllByTestId("run-skeleton");
    expect(runSkeletons.length).toBeGreaterThan(0);
  });
});
