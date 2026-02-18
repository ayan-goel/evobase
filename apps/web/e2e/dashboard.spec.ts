import { test, expect } from "@playwright/test";

const STUB_REPOS = [
  {
    id: "repo-1",
    github_full_name: "acme/frontend",
    github_repo_id: 1,
    default_branch: "main",
    package_manager: "npm",
    install_cmd: null,
    build_cmd: null,
    test_cmd: null,
    typecheck_cmd: null,
    installation_id: null,
    latest_run_status: "completed",
    created_at: new Date().toISOString(),
  },
];

test.describe("Dashboard", () => {
  test("dashboard loads with repo cards when repos exist", async ({ page }) => {
    // Mock the API and Supabase session
    await page.route("**/repos", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ repos: STUB_REPOS }),
      })
    );

    // Bypass auth redirect by mocking supabase auth endpoint
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

    await page.goto("/dashboard");
    await expect(page.getByText("acme/frontend")).toBeVisible({ timeout: 5000 });
  });

  test("empty dashboard shows Connect Repository CTA", async ({ page }) => {
    await page.route("**/repos", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ repos: [] }),
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

    await page.goto("/dashboard");
    await expect(
      page.getByRole("link", { name: /connect repository/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });
});
