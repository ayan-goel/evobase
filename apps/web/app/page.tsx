import { Hero } from "@/components/landing/hero";
import { StatsBar } from "@/components/landing/stats-bar";
import { Pipeline } from "@/components/landing/pipeline";
import { Features } from "@/components/landing/features";
import { DiffShowcase } from "@/components/landing/diff-showcase";
import { CTA } from "@/components/landing/cta";
import { LandingNav } from "@/components/landing/landing-nav";
import { Footer } from "@/components/landing/footer";

export default function Home() {
  return (
    <div className="min-h-screen">
      <LandingNav />
      <main>
        <Hero />
        <StatsBar />
        <Pipeline />
        <DiffShowcase />
        <Features />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
