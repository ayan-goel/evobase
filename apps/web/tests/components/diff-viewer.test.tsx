import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffViewer } from "@/components/diff-viewer";

const SAMPLE_DIFF = `--- a/src/utils.ts
+++ b/src/utils.ts
@@ -1,3 +1,3 @@
 const x = 1;
-if (arr.indexOf(x) !== -1) {
+if (arr.includes(x)) {
   return true;`;

describe("DiffViewer", () => {
  it("renders the diff region", () => {
    render(<DiffViewer diff={SAMPLE_DIFF} />);
    expect(screen.getByRole("region", { name: /code diff/i })).toBeDefined();
  });

  it("renders deletion lines", () => {
    render(<DiffViewer diff={SAMPLE_DIFF} />);
    expect(screen.getByText(/indexOf/)).toBeDefined();
  });

  it("renders addition lines", () => {
    render(<DiffViewer diff={SAMPLE_DIFF} />);
    expect(screen.getByText(/includes/)).toBeDefined();
  });

  it("renders file header lines", () => {
    render(<DiffViewer diff={SAMPLE_DIFF} />);
    // Both --- and +++ headers contain the path — check at least one exists
    expect(screen.getAllByText(/src\/utils\.ts/).length).toBeGreaterThan(0);
  });

  it("shows empty message for blank diff", () => {
    render(<DiffViewer diff="" />);
    expect(screen.getByText(/No diff available/)).toBeDefined();
  });

  it("renders hunk header", () => {
    render(<DiffViewer diff={SAMPLE_DIFF} />);
    expect(screen.getByText(/@@/)).toBeDefined();
  });
});
