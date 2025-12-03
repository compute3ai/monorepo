import { Header, Footer } from "@compute3/shared-ui";
import HeroSection from "@/components/HeroSection";
import ValuePropositions from "@/components/ValuePropositions";
import ProductFeatures from "@/components/ProductFeatures";
import GPUFleet from "@/components/GPUFleet";
import DistributedTraining from "@/components/DistributedTraining";
import CodeExample from "@/components/CodeExample";
import StatsSection from "@/components/StatsSection";
import FinalCTA from "@/components/FinalCTA";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <HeroSection />
        <ValuePropositions />
        <ProductFeatures />
        <GPUFleet />
        <DistributedTraining />
        <CodeExample />
        <StatsSection />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}