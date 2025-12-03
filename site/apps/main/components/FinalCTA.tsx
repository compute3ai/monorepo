"use client";

import { useEffect } from "react";
import { NAV_URLS } from "@compute3/shared-ui";

export default function FinalCTA() {
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
    <section className="py-32 bg-gradient-to-br from-[var(--color-primary)] via-[var(--color-secondary)] to-orange-600 relative overflow-hidden">
      {/* Pattern Background */}
      <div className="absolute inset-0 opacity-10">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center">
          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight text-white sm:text-4xl animate-on-scroll">
            Deploy your first model in 60 seconds
          </h2>
          <p
            className="mx-auto mt-6 max-w-xl text-lg leading-8 text-white/90 animate-on-scroll"
            style={{ transitionDelay: "100ms" }}
          >
            No credit card required. Our free tier is perfect for getting started with open-source{" "}
            <span className="font-bold">AI</span>.
          </p>
          <div
            className="mt-10 flex items-center justify-center gap-x-6 animate-on-scroll"
            style={{ transitionDelay: "200ms" }}
          >
            <a
              href={NAV_URLS.console}
              className="bg-white text-gray-900 font-semibold py-3 px-8 rounded-lg text-lg hover:bg-gray-100 transition transform hover:scale-105"
            >
              Start Free Trial
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}