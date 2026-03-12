"use client";

const FRAMEWORKS = [
  { name: "React", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg" },
  { name: "Next.js", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nextjs/nextjs-original.svg", invert: true },
  { name: "Vue", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vuejs/vuejs-original.svg" },
  { name: "Angular", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/angularjs/angularjs-original.svg" },
  { name: "Node.js", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nodejs/nodejs-original.svg" },
  { name: "Express", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/express/express-original.svg", invert: true },
  { name: "FastAPI", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fastapi/fastapi-original.svg" },
  { name: "Flask", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/flask/flask-original.svg", invert: true },
  { name: "Go", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original.svg" },
  { name: "Rust", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/rust/rust-original.svg", invert: true },
  { name: "C++", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg" },
  { name: "Ruby", icon: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ruby/ruby-original.svg" },
];

// Duplicate for seamless loop
const DOUBLED_FRAMEWORKS = [...FRAMEWORKS, ...FRAMEWORKS];

export function TechStack() {
  return (
    <section className="py-10 border-y border-white/[0.04]">
      <div className="mx-auto max-w-4xl px-6">
        <p className="text-xs font-medium uppercase tracking-widest text-white/30 text-center mb-6">
          Framework-aware optimizations for
        </p>
      </div>
      
      <div className="relative mx-auto max-w-4xl overflow-hidden">
        {/* Fade edges */}
        <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-16 sm:w-24 z-10 bg-gradient-to-r from-black to-transparent" />
        <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-16 sm:w-24 z-10 bg-gradient-to-l from-black to-transparent" />
        
        {/* Scrolling track */}
        <div className="flex animate-marquee">
          {DOUBLED_FRAMEWORKS.map((framework, i) => (
            <div
              key={`${framework.name}-${i}`}
              className="flex items-center gap-2 px-5"
            >
              <img
                src={framework.icon}
                alt={framework.name}
                className={`h-6 w-6 sm:h-7 sm:w-7 ${framework.invert ? "invert" : ""}`}
              />
              <span className="text-xs sm:text-sm font-medium text-white/50 whitespace-nowrap">
                {framework.name}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      <style jsx>{`
        @keyframes marquee {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        .animate-marquee {
          animation: marquee 35s linear infinite;
        }
      `}</style>
    </section>
  );
}
