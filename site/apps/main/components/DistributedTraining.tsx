"use client";

import { useEffect, useState } from "react";
import { ContactModal } from "@compute3/shared-ui";

export default function DistributedTraining() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalSource, setModalSource] = useState("");

  const openModal = (source: string) => {
    setModalSource(source);
    setIsModalOpen(true);
  };
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

  const clusters = [
    { size: "8x", description: "Small-scale fine-tuning", delay: 0 },
    { size: "16x", description: "Medium-scale training", delay: 100 },
    { size: "64x", description: "Large-scale training", delay: 200 },
    { size: "512x", description: "Massive distributed training", delay: 300 },
  ];

  return (
    <>
    <section className="py-20 sm:py-28 bg-gradient-to-br from-gray-900 to-gray-800 text-white overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tighter animate-on-scroll">
            Distributed Training at Scale
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-300 animate-on-scroll" style={{ transitionDelay: "100ms" }}>
            Train on 8x to 512x GPU clusters. Scale from fine-tuning to foundation model training.
          </p>
        </div>

        <div className="mt-16 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {clusters.map((cluster, index) => (
            <div
              key={index}
              className="relative bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 card animate-on-scroll hover:bg-white/10 transition-all duration-300"
              style={{ transitionDelay: `${cluster.delay}ms` }}
            >
              <div className="text-5xl font-black bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] bg-clip-text text-transparent mb-2">
                {cluster.size}
              </div>
              <p className="text-gray-300">{cluster.description}</p>
            </div>
          ))}
        </div>

        <div className="mt-16 bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 animate-on-scroll" style={{ transitionDelay: "400ms" }}>
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex-1">
              <h3 className="text-2xl md:text-3xl font-bold mb-3">
                Up to <span className="text-[var(--color-primary)]">512x B200</span> Clusters
              </h3>
              <p className="text-gray-300 text-lg">
                Need massive compute for foundation model training? We can provision up to 512 B200 GPUs with high-speed interconnects.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => openModal("distributed-training-quote")}
                className="btn-primary text-white font-semibold py-3 px-8 rounded-lg text-lg whitespace-nowrap text-center"
              >
                Ask for Quote
              </button>
              <p className="text-sm text-gray-400 text-center">Custom configurations available</p>
            </div>
          </div>
        </div>

        <div className="mt-12 grid md:grid-cols-3 gap-6">
          <div className="text-center animate-on-scroll" style={{ transitionDelay: "500ms" }}>
            <div className="h-12 w-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h4 className="text-lg font-semibold mb-2">High-Speed Interconnects</h4>
            <p className="text-gray-400">InfiniBand & NVLink for maximum throughput</p>
          </div>

          <div className="text-center animate-on-scroll" style={{ transitionDelay: "600ms" }}>
            <div className="h-12 w-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <h4 className="text-lg font-semibold mb-2">Flexible Frameworks</h4>
            <p className="text-gray-400">DeepSpeed, PyTorch FSDP, Megatron-LM</p>
          </div>

          <div className="text-center animate-on-scroll" style={{ transitionDelay: "700ms" }}>
            <div className="h-12 w-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center">
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.286zm0 13.036h.008v.008h-.008v-.008z" />
              </svg>
            </div>
            <h4 className="text-lg font-semibold mb-2">Checkpointing & Monitoring</h4>
            <p className="text-gray-400">Built-in fault tolerance and observability</p>
          </div>
        </div>

        <div className="mt-12 text-center animate-on-scroll" style={{ transitionDelay: "800ms" }}>
          <button
            onClick={() => openModal("distributed-training-ready")}
            className="inline-flex items-center gap-2 btn-secondary font-semibold py-3 px-8 rounded-lg text-lg bg-white text-gray-900 hover:bg-gray-100"
          >
            Ready to Train Your Model?
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </section>

    <ContactModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} source={modalSource} />
    </>
  );
}
