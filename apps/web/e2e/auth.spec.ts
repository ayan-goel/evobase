import { test, expect } from "@playwright/test";

test.describe("Auth", () => {
  test("login page loads with sign-in button", async ({ page }) => {
    await page.goto("/login");
    const button = page.getByRole("button", { name: /sign in with github/i });
    await expect(button).toBeVisible();
  });

  test("unauthenticated users are redirected to /login from /dashboard", async ({
    page,
  }) => {
    // Mock the Supabase session check so the middleware treats the request as
    // unauthenticated. The middleware reads the sb-* cookies; with no cookies
    // present the session is null and the redirect should fire.
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
