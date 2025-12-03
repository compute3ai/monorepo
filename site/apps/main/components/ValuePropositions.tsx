"use client";

import { useEffect, ReactNode } from "react";

interface ValueProp {
  icon: ReactNode;
  title: string;
  description: string;
  features: string[];
  delay: number;
}

export default function ValuePropositions() {
  const values: ValueProp[] = [
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      title: "Lightning Fast",
      description: "Boot any GPU workload in under 3 seconds. Custom Docker orchestration means zero cold starts, zero wait times.",
      features: [
        "Sub-3 second boot times",
        "Instant container deployment",
        "Pre-warmed GPU instances"
      ],
      delay: 200
    },
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      title: "Pay Per Second",
      description: "No hourly minimums. No monthly commitments. Pay only for the exact seconds you use. Spin up, use, tear down.",
      features: [
        "Per-second billing granularity",
        "No hourly minimums",
        "No contracts or commitments"
      ],
      delay: 300
    },
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      ),
      title: "Secure & Private",
      description: "Your API keys provisioned directly to your container. No shared access. You're the only one with access to your GPU.",
      features: [
        "Isolated container environments",
        "Secure API key provisioning",
        "Private GPU access only"
      ],
      delay: 400
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
    <section id="features" className="py-20 sm:py-28 bg-[var(--color-bg-light)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 animate-on-scroll">
            Why <span className="text-[var(--color-primary)]">Compute</span>
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-600 animate-on-scroll" style={{ transitionDelay: "100ms" }}>
            The fastest, most flexible GPU infrastructure for AI workloads
          </p>
        </div>
        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {values.map((value, index) => (
            <div
              key={index}
              className="bg-white p-6 rounded-2xl shadow-sm card animate-on-scroll"
              style={{ transitionDelay: `${value.delay}ms` }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)] text-[var(--color-primary)] flex items-center justify-center flex-shrink-0">
                  {value.icon}
                </div>
                <h3 className="text-xl font-bold text-gray-900">{value.title}</h3>
              </div>
              <p className="text-gray-600 mb-4">{value.description}</p>
              <ul className="space-y-2 text-sm text-gray-600">
                {value.features.map((feature, featureIndex) => (
                  <li key={featureIndex} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[var(--color-primary)] flex-shrink-0"></span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}