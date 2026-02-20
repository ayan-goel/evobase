export const FRAMEWORK_LABELS: Record<string, string> = {
  nextjs: "Next.js",
  react: "React",
  "react-vite": "React + Vite",
  vue: "Vue.js",
  nuxt: "Nuxt",
  angular: "Angular",
  svelte: "Svelte",
  sveltekit: "SvelteKit",
  remix: "Remix",
  gatsby: "Gatsby",
  astro: "Astro",
  solidjs: "Solid.js",
  express: "Express",
  nestjs: "NestJS",
  fastify: "Fastify",
  koa: "Koa",
  hapi: "Hapi",
  trpc: "tRPC",
  fastapi: "FastAPI",
  django: "Django",
  flask: "Flask",
  rails: "Ruby on Rails",
  go: "Go",
  gin: "Gin",
  echo: "Echo",
  fiber: "Fiber",
  chi: "Chi",
  rust: "Rust",
  axum: "Axum",
  actix: "Actix Web",
  warp: "Warp",
  springboot: "Spring Boot",
};

export const PM_LABELS: Record<string, string> = {
  npm: "npm",
  pnpm: "pnpm",
  yarn: "Yarn",
  bun: "Bun",
  pip: "pip",
  uv: "uv",
  cargo: "Cargo",
  go: "Go modules",
  bundler: "Bundler",
  maven: "Maven",
  gradle: "Gradle",
};

const ICON_FILE_MAP: Record<string, string> = {
  nextjs: "nextjs.svg",
  react: "react.svg",
  "react-vite": "react.svg",
  vue: "vue.svg",
  nuxt: "nuxt.svg",
  angular: "angular.svg",
  svelte: "svelte.svg",
  sveltekit: "svelte.svg",
  remix: "remix.svg",
  gatsby: "gatsby.svg",
  astro: "astro.svg",
  solidjs: "solidjs.svg",
  express: "express.svg",
  nestjs: "nestjs.svg",
  fastify: "fastify.svg",
  koa: "nodejs.svg",
  hapi: "nodejs.svg",
  trpc: "nodejs.svg",
  fastapi: "fastapi.svg",
  django: "django.svg",
  flask: "flask.svg",
  rails: "rails.svg",
  go: "go.svg",
  gin: "go.svg",
  echo: "go.svg",
  fiber: "go.svg",
  chi: "go.svg",
  rust: "rust.svg",
  axum: "rust.svg",
  actix: "rust.svg",
  warp: "rust.svg",
  springboot: "springboot.svg",
};

const PM_ICON_FILE_MAP: Record<string, string> = {
  npm: "npm.svg",
  pnpm: "pnpm.svg",
  yarn: "yarn.svg",
  bun: "bun.svg",
  pip: "python.svg",
  uv: "python.svg",
  cargo: "rust.svg",
  go: "go.svg",
  bundler: "ruby.svg",
  maven: "java.svg",
  gradle: "java.svg",
};

export function getFrameworkLabel(framework: string | null): string {
  if (!framework) return "Unknown";
  return FRAMEWORK_LABELS[framework] ?? framework;
}

export function getFrameworkIconPath(framework: string | null): string {
  if (!framework) return "/framework-icons/code.svg";
  const file = ICON_FILE_MAP[framework];
  return file ? `/framework-icons/${file}` : "/framework-icons/code.svg";
}

export function getPmLabel(pm: string | null): string {
  if (!pm) return "";
  return PM_LABELS[pm] ?? pm;
}

export function getPmIconPath(pm: string | null): string {
  if (!pm) return "";
  const file = PM_ICON_FILE_MAP[pm];
  return file ? `/framework-icons/${file}` : "/framework-icons/code.svg";
}
