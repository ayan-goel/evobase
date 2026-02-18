import { test, expect } from "@playwright/test";

const REPO_ID = "00000000-0000-0000-0000-000000000100";
const RUN_ID = "00000000-0000-0000-0000-000000000200";
const PROPOSAL_ID = "00000000-0000-0000-0000-000000000300";

const STUB_PROPOSAL = {
  id: PROPOSAL_ID,
  run_id: RUN_ID,
  summary: "Reduce p95 latency by replacing Array.includes with Set.has",
  diff: "--- a/utils.ts\n+++ b/utils.ts\n@@ -1 +1 @@\n-old\n+new\n",
  metrics_before: { latency_ms: 100 },
  metrics_after: { latency_ms: 88 },
  risk_score: 0.1,
  pr_url: null,
  created_at: new Date().toISOString(),
};

test.describe("Proposal Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`**/proposals/${PROPOSAL_ID}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STUB_PROPOSAL),
      })
    );
    await page.route(`**/repos/${REPO_ID}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: REPO_ID,
          github_full_name: "acme/api",
          default_branch: "main",
          package_manager: "npm",
          github_repo_id: 42,
          install_cmd: null,
          build_cmd: null,
          test_cmd: null,
          typecheck_cmd: null,
          installation_id: 1,
          latest_run_status: "completed",
          created_at: new Date().toISOString(),
        }),
      })
    );
    await page.route("**/auth/v1/user", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          email: "test@example.com",
          user_metadata: { user_name: "testuser" },
        }),
      })
    );
  });

  test("proposal page renders the proposal summary", async ({ page }) => {
    await page.goto(`/repos/${REPO_ID}/proposals/${PROPOSAL_ID}`);
    await expect(
      page.getByText(/reduce p95 latency/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test("Create PR button is visible on a proposal without a PR", async ({ page }) => {
    await page.goto(`/repos/${REPO_ID}/proposals/${PROPOSAL_ID}`);
    await expect(
      page.getByRole("button", { name: /create pr/i })
    ).toBeVisible({ timeout: 5000 });
  });
});
