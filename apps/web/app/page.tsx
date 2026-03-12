import { Nav } from "@/components/nav";
import { Hero } from "@/components/landing/hero";
import { TechStack } from "@/components/landing/tech-stack";
import { WhyEvobase } from "@/components/landing/why-evobase";
import { Pipeline } from "@/components/landing/pipeline";
import { Features } from "@/components/landing/features";
import { DiffShowcase } from "@/components/landing/diff-showcase";
import { Pricing } from "@/components/landing/pricing";
import { Footer } from "@/components/landing/footer";

export default function Home() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main>
        <Hero />
        <TechStack />
        <WhyEvobase />
        <Pipeline />
        <DiffShowcase />
        <Features />
        <Pricing />
      </main>
      <Footer />
    </div>
  );
}
