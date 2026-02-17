// This file contains patterns that should trigger set_membership detection.

const ALLOWED_STATUSES = ["active", "pending", "verified"];

function checkStatus(status: string): boolean {
  // Should trigger: indexOf !== -1 pattern
  return ALLOWED_STATUSES.indexOf(status) !== -1;
}

function isValid(code: number, codes: number[]): boolean {
  // Should trigger: indexOf >= 0 pattern
  return codes.indexOf(code) >= 0;
}

function isNotFound(item: string, list: string[]): boolean {
  // Should trigger: indexOf === -1 pattern
  return list.indexOf(item) === -1;
}

// This should NOT trigger (includes is already good)
function hasItem(list: string[], item: string): boolean {
  return list.includes(item);
}
