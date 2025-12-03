"use client";

import { useEffect, useState, ReactNode } from "react";
import { ContactModal, NAV_URLS } from "@compute3/shared-ui";

interface Feature {
  icon: ReactNode;
  title: string;
  description: string;
  features: string[];
  delay: number;
}

export default function ProductFeatures() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalSource, setModalSource] = useState("");

  const openModal = (source: string) => {
    setModalSource(source);
    setIsModalOpen(true);
  };

  const features: Feature[] = [
    {
      icon: (
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M8 9h8M8 13h6M6 3h12a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V5a2 2 0 012-2z" />
        </svg>
      ),
      title: "LLM Inference Servers",
      description: "Deploy production-ready LLM servers in under 3 seconds. Run any model with vLLM, SGLang, Ollama, or TGI.",
      features: [
        "vLLM for maximum throughput",
        "SGLang for structured generation",
        "Ollama & TGI support",
        "Any model from HuggingFace"
      ],
      delay: 0
    },
    {
      icon: (
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M7 4h10a3 3 0 013 3v10a3 3 0 01-3 3H7a3 3 0 01-3-3V7a3 3 0 013-3z" />
          <path d="M7 15l3-3 3 3 4-4" />
        </svg>
      ),
      title: "Media Generation",
      description: "ComfyUI, Automatic1111, and Fooocus ready to go. Images with Flux & HiDream, video with Wan 2.2, audio with Whisper & 50+ more models.",
      features: [
        "ComfyUI node-based workflows",
        "Image: Flux, HiDream, Qwen",
        "Video: Wan 2.2, Hunyan",
        "Audio: Whisper, CSM + many more"
      ],
      delay: 50
    },
    {
      icon: (
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <rect x="3" y="4" width="18" height="14" rx="3" />
          <path d="M7 20h10" />
        </svg>
      ),
      title: "Development Environments",
      description: "GPU-accelerated JupyterLab, VSCode Server, or bring your own Docker container. Perfect for research and experimentation.",
      features: [
        "JupyterLab with GPU support",
        "VSCode Server with CUDA",
        "Custom Docker containers",
        "PyTorch environments ready to go"
      ],
      delay: 100
    },
    {
      icon: (
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      ),
      title: "Training & Fine-tuning",
      description: "Fine-tune models with Axolotl, LLaMA Factory, Unsloth, or DeepSpeed. Faster training, lower costs.",
      features: [
        "Axolotl for easy fine-tuning",
        "LLaMA Factory WebUI",
        "Unsloth for 2x faster training",
        "DeepSpeed for distributed training"
      ],
      delay: 150
    }
  ];

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        });
      },
      { threshold: 0.1 }
    );

    const elements = document.querySelectorAll(".animate-on-scroll");
    elements.forEach((el) => observer.observe(el));

    return () => {
      elements.forEach((el) => observer.unobserve(el));
    };
  }, []);

  return (
    <>
    <section id="product" className="py-20 sm:py-28 bg-white overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 animate-on-scroll">
            GPU Workloads in <span className="text-[var(--color-primary)]">&lt; 3 Seconds</span>
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-600 animate-on-scroll" style={{ transitionDelay: "100ms" }}>
            Deploy any AI workload with secure, per-second billing. Your API keys, your GPU.
          </p>
        </div>

        <div className="mt-16 grid md:grid-cols-2 gap-6">
          {features.map((feature, index) => (
            <div
              key={index}
              className="bg-white border border-gray-200 p-6 rounded-2xl shadow-sm card animate-on-scroll"
              style={{ transitionDelay: `${feature.delay}ms` }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold">{feature.title}</h3>
              </div>
              <p className="text-gray-600 mb-4">{feature.description}</p>
              <ul className="space-y-2 text-sm text-gray-600">
                {feature.features.map((item, itemIndex) => (
                  <li key={itemIndex} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[var(--color-primary)]"></span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center animate-on-scroll" style={{ transitionDelay: "300ms" }}>
          <a
            href={NAV_URLS.launch}
            className="inline-flex items-center gap-2 btn-primary text-white font-semibold py-3 px-8 rounded-lg text-lg"
          >
            Ready to Launch a Workload?
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </a>
        </div>
      </div>
    </section>

    <ContactModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} source={modalSource} />
    </>
  );
}