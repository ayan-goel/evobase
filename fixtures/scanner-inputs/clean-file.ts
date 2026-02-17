// This file should NOT trigger any scanner opportunities.

interface User {
  id: string;
  name: string;
  email: string;
}

function getUserById(users: Map<string, User>, id: string): User | undefined {
  return users.get(id);
}

function formatUserList(users: User[]): string {
  return users.map(u => `${u.name} <${u.email}>`).join(", ");
}

async function fetchData(url: string): Promise<any> {
  const response = await fetch(url);
  return response.json();
}

export { getUserById, formatUserList, fetchData };
