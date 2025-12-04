"use client";

import { Header, Footer } from "@compute3/shared-ui";
import Link from "next/link";
import templatesIndex from "@/content/comfyui/index.json";
import ParticleCanvas from "@/components/ParticleCanvas";

type Template = {
  template_id: string;
  title: string;
  description: string;
  bundle: string;
  output_type: string;
  tags: string[];
};

function TemplateCard({ template }: { template: Template }) {
  const isVideo = template.output_type === "video";

  return (
    <Link
      href={`/playground/comfyui/${template.template_id}`}
      className="group block bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm card"
    >
      <div className="aspect-square bg-gray-100 relative overflow-hidden">
        {/* Animated webp auto-plays and loops natively in img tags */}
        <img
          src={`/comfyui/${template.template_id}/thumbnail.webp`}
          alt={template.title}
          className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
        />
        {/* Play indicator for video templates */}
        {isVideo && (
          <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-sm p-1.5 rounded-full">
            <svg className="h-3 w-3 text-white" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        )}
        <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-0.5 rounded text-xs font-medium text-gray-700 shadow-sm">
          {template.output_type}
        </div>
      </div>
      <div className="p-3">
        <h3 className="font-semibold text-gray-900 group-hover:text-[var(--color-primary)] transition-colors text-sm leading-tight">
          {template.title}
        </h3>
        {template.description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
            {template.description}
          </p>
        )}
      </div>
    </Link>
  );
}

function SectionHeader({ icon, title, count }: { icon: React.ReactNode; title: string; count: number }) {
  return (
    <div className="flex items-center gap-3 mb-6">
      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
        {icon}
      </div>
      <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
      <span className="text-sm font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-full">{count}</span>
    </div>
  );
}

export default function ComfyUIPlayground() {
  const templates = templatesIndex.templates as Template[];

  // Group by output type
  const videoTemplates = templates.filter(t => t.output_type === "video");
  const imageTemplates = templates.filter(t => t.output_type === "image");
  const threeDTemplates = templates.filter(t => t.output_type === "3D");
  const otherTemplates = templates.filter(t => !["video", "image", "3D"].includes(t.output_type));

  return (
    <>
      <Header />
      <main className="min-h-screen bg-white">
        {/* Hero Section */}
        <div className="relative py-20 sm:py-28 bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] overflow-hidden">
          <ParticleCanvas />
          <div className="relative z-20 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <nav className="mb-6 text-sm">
              <Link href="/playground" className="text-gray-500 hover:text-[var(--color-primary)] hover:underline transition-colors">
                Playground
              </Link>
              <span className="text-gray-400 mx-2">/</span>
              <span className="text-gray-900 font-medium">ComfyUI Templates</span>
            </nav>
            <h1 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 mb-4">
              ComfyUI Templates
            </h1>
            <p className="text-lg md:text-xl text-gray-600 max-w-2xl mx-auto">
              Production-ready workflows for video generation, image creation, and more.
              Run on Compute3 GPUs with a single command.
            </p>
          </div>
        </div>

        {/* Templates Sections */}
        <section className="py-16 bg-white">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
            {/* Video Templates */}
            {videoTemplates.length > 0 && (
              <div className="mb-16">
                <SectionHeader
                  icon={
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                  }
                  title="Video Generation"
                  count={videoTemplates.length}
                />
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {videoTemplates.map((template) => (
                    <TemplateCard key={template.template_id} template={template} />
                  ))}
                </div>
              </div>
            )}

            {/* Image Templates */}
            {imageTemplates.length > 0 && (
              <div className="mb-16">
                <SectionHeader
                  icon={
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                  }
                  title="Image Generation"
                  count={imageTemplates.length}
                />
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {imageTemplates.map((template) => (
                    <TemplateCard key={template.template_id} template={template} />
                  ))}
                </div>
              </div>
            )}

            {/* 3D Templates */}
            {threeDTemplates.length > 0 && (
              <div className="mb-16">
                <SectionHeader
                  icon={
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                    </svg>
                  }
                  title="3D Generation"
                  count={threeDTemplates.length}
                />
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {threeDTemplates.map((template) => (
                    <TemplateCard key={template.template_id} template={template} />
                  ))}
                </div>
              </div>
            )}

            {/* Other Templates */}
            {otherTemplates.length > 0 && (
              <div className="mb-16">
                <SectionHeader
                  icon={
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 16v-4M12 8h.01" />
                    </svg>
                  }
                  title="Other"
                  count={otherTemplates.length}
                />
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {otherTemplates.map((template) => (
                    <TemplateCard key={template.template_id} template={template} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
