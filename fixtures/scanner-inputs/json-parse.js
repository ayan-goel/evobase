// This file contains patterns that should trigger json_parse_cache detection.

function processConfig(rawConfig) {
  // Each of these should trigger
  const config1 = JSON.parse(rawConfig);
  const config2 = JSON.parse(rawConfig);
  return { ...config1, ...config2 };
}

function safeJsonParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return null;
  }
}
