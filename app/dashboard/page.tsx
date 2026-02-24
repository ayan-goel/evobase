
/** RSC page — fetches data then delegates to DashboardView. */
export default async function DashboardPage() {
  const [repos, installations] = await Promise.all([
    getRepos(),
    getInstallations(),
  ]);

  return (
