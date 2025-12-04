"use client";

import { Header, Footer } from "@compute3/shared-ui";
import Link from "next/link";
import ParticleCanvas from "@/components/ParticleCanvas";

const playgrounds = [
  {
    id: "comfyui",
    title: "ComfyUI Templates",
    description: "Production-ready workflows for video generation, image creation, and 3D modeling. Run on Compute3 GPUs.",
    icon: (
      <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path d="M7 4h10a3 3 0 013 3v10a3 3 0 01-3 3H7a3 3 0 01-3-3V7a3 3 0 013-3z" />
        <path d="M7 15l3-3 3 3 4-4" />
      </svg>
    ),
    count: 32,
    href: "/playground/comfyui",
  },
];

export default function PlaygroundIndex() {
  return (
    <>
      <Header />
      <main className="min-h-screen bg-white">
        {/* Hero Section */}
        <div className="relative py-20 sm:py-28 bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] overflow-hidden">
          <ParticleCanvas />
          <div className="relative z-20 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h1 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 mb-4">
              Playground
            </h1>
            <p className="text-lg md:text-xl text-gray-600 max-w-2xl mx-auto">
              Ready-to-run templates and workflows. Pick one, customize it, and run on GPU.
            </p>
          </div>
        </div>

        {/* Playground tiles */}
        <section className="py-16 bg-white">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {playgrounds.map((pg) => (
                <Link
                  key={pg.id}
                  href={pg.href}
                  className="group block bg-white border border-gray-200 p-6 rounded-2xl shadow-sm card"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
                      {pg.icon}
                    </div>
                    <h2 className="text-xl font-semibold text-gray-900 group-hover:text-[var(--color-primary)] transition-colors">
                      {pg.title}
                    </h2>
                  </div>
                  <p className="text-gray-600 mb-4">{pg.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">{pg.count} templates</span>
                    <span className="text-[var(--color-primary)] text-sm font-medium group-hover:translate-x-1 transition-transform">
                      Browse &rarr;
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
