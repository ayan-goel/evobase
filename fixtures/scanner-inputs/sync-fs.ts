// This file contains synchronous fs calls.

import * as fs from "fs";
import * as path from "path";

// Should trigger: readFileSync in what looks like a handler
export function handleRequest(req: any, res: any) {
  const template = fs.readFileSync(path.join(__dirname, "template.html"), "utf8");
  res.send(template);
}

// Should trigger: existsSync
export function checkFile(filePath: string): boolean {
  return fs.existsSync(filePath);
}

// Should trigger: writeFileSync
export function saveData(filePath: string, data: string) {
  fs.writeFileSync(filePath, data);
}
