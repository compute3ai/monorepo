"use client";

import { Header, Footer } from "@compute3/shared-ui";
import GPUPricing from "@/components/GPUPricing";
import ParticleCanvas from "@/components/ParticleCanvas";

export default function GPUsPage() {
  return (
    <>
      <Header />
      <main className="min-h-screen bg-white">
        <div className="relative py-20 sm:py-28 bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] overflow-hidden">
          <ParticleCanvas />
          <div className="relative z-20 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h1 className="text-5xl md:text-6xl font-extrabold tracking-tighter text-gray-900 mb-6">
              State-of-the-Art <span className="text-[var(--color-primary)]">GPUs</span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-700 font-semibold mb-4">
              B200, H200, H100, A100, L40S, L4 and more.
            </p>
            <p className="text-lg text-gray-600 max-w-3xl mx-auto">
              On-demand and interruptible instances. Deploy in seconds. Pay per second.
            </p>
          </div>
        </div>

        <GPUPricing />
      </main>
      <Footer />
    </>
  );
}
