"use client";

import { useEffect } from "react";

interface Stat {
  value: string;
  label: string;
  delay: number;
}

export default function StatsSection() {
  const stats: Stat[] = [
    {
      value: "10,000+",
      label: "GPUs Connected",
      delay: 0
    },
    {
      value: "99.9%",
      label: "Uptime SLA",
      delay: 100
    },
    {
      value: "20,000+",
      label: "GPU Workloads Launched",
      delay: 200
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
    <section className="py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid md:grid-cols-3 gap-12">
          {stats.map((stat, index) => (
            <div
              key={index}
              className="text-center animate-on-scroll"
              style={{ transitionDelay: `${stat.delay}ms` }}
            >
              <div className="text-5xl md:text-6xl font-black bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] bg-clip-text text-transparent mb-2">
                {stat.value}
              </div>
              <p className="text-xl text-gray-600 font-semibold">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}