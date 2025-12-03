"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import ParticleCanvas from "./ParticleCanvas";
import { ContactModal, NAV_URLS } from "@compute3/shared-ui";

export default function HeroSection() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalSource, setModalSource] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [placeholderText, setPlaceholderText] = useState("");
  const [animationState, setAnimationState] = useState("LOADING");
  const currentModelIndexRef = useRef(0);
  const charIndexRef = useRef(0);

  const openModal = (source: string) => {
    setModalSource(source);
    setIsModalOpen(true);
  };

  // Helper function to pick a random model different from current
  const getRandomModelIndex = (currentIndex: number, modelsLength: number): number => {
    if (modelsLength <= 1) return 0;
    let nextIndex;
    do {
      nextIndex = Math.floor(Math.random() * modelsLength);
    } while (nextIndex === currentIndex);
    return nextIndex;
  };

  // Fetch models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch("https://api.compute3.ai/llm/models");
        const data = await response.json();
        const modelList = Object.entries(data)
          .filter(([key]) => !key.toLowerCase().includes("embedding"))
          .map(([, value]) => {
            const name = (value as { name: string }).name;
            // Strip provider prefix (e.g., "Nous: Hermes 4 70B" -> "Hermes 4 70B")
            return name.includes(": ") ? name.split(": ")[1] : name;
          })
          .filter(Boolean);
        if (modelList.length === 0) throw new Error("No models");
        const shuffled = [...modelList].sort(() => Math.random() - 0.5);
        setModels(shuffled);
        currentModelIndexRef.current = Math.floor(Math.random() * shuffled.length);
        setAnimationState("TYPING_IN");
      } catch (err) {
        console.error("Failed to fetch models:", err);
        const fallbackModels = ["Claude Sonnet 4.5", "GPT-4o", "Llama 3.3 70B", "Gemini 2.5 Flash"];
        const shuffled = [...fallbackModels].sort(() => Math.random() - 0.5);
        setModels(shuffled);
        currentModelIndexRef.current = Math.floor(Math.random() * shuffled.length);
        setAnimationState("TYPING_IN");
      }
    };
    fetchModels();
  }, []);

  // FSM animation
  useEffect(() => {
    if (models.length === 0 || animationState === "LOADING") return;

    const currentModel = models[currentModelIndexRef.current] || models[0];
    if (!currentModel) return;

    const otherModelsCount = models.length - 1;
    const fullText = `One API key, use ${currentModel} or ${otherModelsCount}+ other models...`;
    let interval: NodeJS.Timeout | undefined;

    switch (animationState) {
      case "TYPING_IN":
        interval = setInterval(() => {
          if (charIndexRef.current < fullText.length) {
            charIndexRef.current++;
            setPlaceholderText(fullText.substring(0, charIndexRef.current));
          } else {
            clearInterval(interval);
            setAnimationState("PAUSED");
          }
        }, 50);
        break;

      case "PAUSED":
        const pauseTimeout = setTimeout(() => {
          setAnimationState("TYPING_OUT");
        }, 2000);
        return () => clearTimeout(pauseTimeout);

      case "TYPING_OUT":
        interval = setInterval(() => {
          if (charIndexRef.current > 0) {
            charIndexRef.current--;
            setPlaceholderText(fullText.substring(0, charIndexRef.current));
          } else {
            clearInterval(interval);
            setAnimationState("CYCLING");
          }
        }, 30);
        break;

      case "CYCLING":
        const cycleTimeout = setTimeout(() => {
          currentModelIndexRef.current = getRandomModelIndex(currentModelIndexRef.current, models.length);
          charIndexRef.current = 0;
          setAnimationState("TYPING_IN");
        }, 100);
        return () => clearTimeout(cycleTimeout);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [models, animationState]);

  const handleChatSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const encodedMessage = btoa(chatInput);
    window.location.href = `${NAV_URLS.chat}?message=${encodedMessage}`;
  };

  return (
    <>
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)]">
      <ParticleCanvas />

      <div className="absolute inset-0 bg-gradient-to-br from-white via-transparent to-white z-10 opacity-30"></div>

      <div className="relative z-20 max-w-7xl mx-auto px-6 pt-12 pb-8 hero-content">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Hero Content */}
          <div className="text-center lg:text-left">
            <h1
              className="text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tighter text-gray-900 leading-tight mb-6 hero-headline"
              style={{ animationDelay: "0.3s" }}
            >
              Private GPUs
              <br />
              in <span className="text-[var(--color-primary)]">&lt; 3 Seconds</span>
              <br />
              <span className="gradient-text">Pay Per Second.</span>
            </h1>

            <p
              className="text-xl md:text-2xl text-gray-700 font-semibold mb-6"
              style={{ animationDelay: "0.5s" }}
            >
              Secure GPU workloads. Your API keys, your container. 70+ models ready to deploy.
            </p>

            <p
              className="text-lg text-gray-600 mb-8 leading-relaxed max-w-2xl mx-auto lg:mx-0"
              style={{ animationDelay: "0.7s" }}
            >
              Custom Docker orchestration with secure API key provisioning. Only you can access your GPU.
              From A100s to B300s. <span className="text-[var(--color-primary)]">Per-second billing</span> means you only pay for what you use.
            </p>

          </div>

          {/* Hero Image */}
          <div className="hero-image relative">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] opacity-20 blur-3xl rounded-full"></div>
              <Image
                src="https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&q=80"
                alt="AI Infrastructure"
                width={800}
                height={600}
                className="relative rounded-2xl shadow-2xl w-full"
                priority
              />
            </div>
          </div>
        </div>

        {/* Chat Input - Full Width */}
        <div className="mt-20 w-full max-w-xl mx-auto text-center">
          <h3 className="text-2xl font-bold text-gray-900 mb-4">
            Chat with Compute3.<span className="text-[var(--color-primary)]">AI</span>
          </h3>
          <form onSubmit={handleChatSubmit} className="flex gap-2 bg-white/80 backdrop-blur-sm p-2 rounded-xl shadow-lg border border-gray-200 focus-within:border-[var(--color-primary)] focus-within:shadow-xl transition-all duration-300">
            <input
              type="text"
              className="flex-1 bg-transparent border-none text-gray-900 text-base px-4 py-3 outline-none placeholder:text-[var(--color-primary)]/60"
              placeholder={animationState !== "LOADING" ? placeholderText : "Loading..."}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onFocus={() => {
                if (!chatInput) {
                  setAnimationState("PAUSED");
                  setPlaceholderText("Ask me anything...");
                }
              }}
              onBlur={() => {
                if (!chatInput && animationState !== "LOADING") {
                  charIndexRef.current = 0;
                  setAnimationState("TYPING_IN");
                }
              }}
            />
            <button
              type="submit"
              disabled={!chatInput.trim()}
              className="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:bg-[var(--color-primary-dark)] disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-300 hover:scale-105 flex items-center justify-center"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </form>
        </div>

        {/* Scroll Indicator */}
        <div className="absolute bottom-10 left-1/2 transform -translate-x-1/2 scroll-indicator">
          <div className="flex flex-col items-center">
            <span className="text-sm text-gray-500 mb-2">Scroll to explore</span>
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M19 14l-7 7m0 0l-7-7m7 7V3"></path>
            </svg>
          </div>
        </div>
      </div>
    </section>

    <ContactModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} source={modalSource} />
    </>
  );
}