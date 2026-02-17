// This file contains patterns detectable inside loops.

function buildReport(items: any[]): string {
  // string concat in loop - should trigger
  let report = "";
  for (const item of items) {
    report += `Item: ${item.name}\n`;
  }
  return report;
}

function findAllMatches(data: any[], targets: any[]) {
  const results = [];
  // Array.find inside a loop - should trigger (AST)
  for (const target of targets) {
    const match = data.find(d => d.id === target.id);
    if (match) results.push(match);
  }
  return results;
}

function processItems(items: any[]) {
  let result: any = {};
  // Spread in loop - should trigger (AST)
  for (const item of items) {
    result = { ...result, [item.key]: item.value };
  }
  return result;
}

function validateAll(entries: string[]) {
  const results = [];
  // Regex in loop - should trigger
  for (const entry of entries) {
    const match = new RegExp("^[a-z]+$").test(entry);
    results.push(match);
  }
  return results;
}

// This should NOT trigger (regex outside loop)
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
function validateEmail(email: string): boolean {
  return EMAIL_RE.test(email);
}
