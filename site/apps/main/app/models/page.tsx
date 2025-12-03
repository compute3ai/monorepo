"use client";

import { Header, Footer } from "@compute3/shared-ui";
import ModelPricing from "@/components/ModelPricing";
import ParticleCanvas from "@/components/ParticleCanvas";

export default function ModelsPage() {
  return (
    <>
      <Header />
      <main className="min-h-screen bg-white">
        <div className="relative py-20 sm:py-28 bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] overflow-hidden">
          <ParticleCanvas />
          <div className="relative z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h1 className="text-5xl md:text-6xl font-extrabold tracking-tighter text-gray-900 mb-6">
              State-of-the-Art <span className="text-[var(--color-primary)]">AI Models</span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-700 font-semibold mb-4">
              API access to the latest models. Claude, GPT-5, Gemini, Qwen, and more.
            </p>
            <p className="text-lg text-gray-600 max-w-3xl mx-auto">
              Drop-in replacement for OpenAI and Anthropic APIs. Hosted on our B200 GPU fleet.
            </p>
          </div>
        </div>

        <ModelPricing />
      </main>
      <Footer />
    </>
  );
}
