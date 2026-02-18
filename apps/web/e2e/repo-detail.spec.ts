import { test, expect } from "@playwright/test";

const REPO_ID = "00000000-0000-0000-0000-000000000100";

const STUB_REPO = {
  id: REPO_ID,
  github_full_name: "acme/api",
  github_repo_id: 42,
  default_branch: "main",
  package_manager: "npm",
  install_cmd: null,
  build_cmd: null,
  test_cmd: null,
  typecheck_cmd: null,
  installation_id: null,
  latest_run_status: "running",
  created_at: new Date().toISOString(),
};

const STUB_RUNS = [
  {
    id: "run-1",
    repo_id: REPO_ID,
    sha: "abc1234",
    status: "running",
    compute_minutes: null,
    created_at: new Date().toISOString(),
  },
];

test.describe("Repo Detail", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`**/repos/${REPO_ID}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STUB_REPO),
      })
    );
    await page.route(`**/repos/${REPO_ID}/runs`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ runs: STUB_RUNS }),
      })
    );
    await page.route(`**/runs/*/proposals`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ proposals: [] }),
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

  test("repo page shows run status badge", async ({ page }) => {
    await page.goto(`/repos/${REPO_ID}`);
    await expect(page.getByText("running")).toBeVisible({ timeout: 5000 });
  });

  test("trigger run button is present on the repo page", async ({ page }) => {
    await page.goto(`/repos/${REPO_ID}`);
    await expect(
      page.getByRole("button", { name: /trigger run/i })
    ).toBeVisible({ timeout: 5000 });
  });
});
