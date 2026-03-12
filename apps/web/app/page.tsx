import { Nav } from "@/components/nav";
import { Hero } from "@/components/landing/hero";
import { TechStack } from "@/components/landing/tech-stack";
import { WhyEvobase } from "@/components/landing/why-evobase";
import { Pipeline } from "@/components/landing/pipeline";
import { Features } from "@/components/landing/features";
import { DiffShowcase } from "@/components/landing/diff-showcase";
import { CTA } from "@/components/landing/cta";
import { Footer } from "@/components/landing/footer";

export default function Home() {
  return (
    <div className="min-h-screen">
      <Nav maxWidthClass="max-w-5xl" />
      <main>
        <Hero />
        <TechStack />
        <WhyEvobase />
        <Pipeline />
        <DiffShowcase />
        <Features />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
