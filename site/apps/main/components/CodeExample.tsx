"use client";

import { useState, useEffect } from "react";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import bash from "react-syntax-highlighter/dist/esm/languages/hljs/bash";
import { tomorrow } from "react-syntax-highlighter/dist/esm/styles/hljs";

// Register the bash language
SyntaxHighlighter.registerLanguage("bash", bash);

export default function CodeExample() {
  const [copied, setCopied] = useState(false);

  const codeString = `# Deploy vLLM with Llama 3 70B on H100
c3 deploy vllm \\
  --model meta-llama/Llama-3-70b \\
  --gpu h100

# Launch ComfyUI on A100
c3 deploy comfyui \\
  --gpu a100-80gb

# Start JupyterLab with CUDA
c3 deploy jupyter \\
  --gpu a100-40gb \\
  --image pytorch/pytorch:latest

# Deploy Ollama with custom models
c3 deploy ollama \\
  --gpu l40s \\
  --models llama3,mistral

# Fine-tune with Axolotl on 8x H100
c3 train axolotl \\
  --config fine-tune.yml \\
  --gpus 8 \\
  --gpu-type h100`;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

  return (
    <section id="code" className="py-20 sm:py-28 bg-gradient-to-br from-[var(--gradient-start)] to-[var(--gradient-end)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 animate-on-scroll">
            One Command. <span className="text-[var(--color-primary)]">&lt;3 Seconds.</span>
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-600 animate-on-scroll" style={{ transitionDelay: "100ms" }}>
            Deploy any workload with our CLI. From inference to training, boots in under 3 seconds.
          </p>
        </div>
        <div className="mt-12 animate-on-scroll code-block-glow" style={{ transitionDelay: "200ms" }}>
          <div className="relative bg-gray-900/80 backdrop-blur-sm rounded-xl p-1 border border-white/10">
            <button
              onClick={handleCopy}
              className="absolute top-4 right-4 bg-gray-700/50 hover:bg-gray-600 text-gray-300 font-mono text-xs py-1 px-2 rounded-md transition"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
            <SyntaxHighlighter
              language="bash"
              style={tomorrow}
              customStyle={{
                padding: "1.5rem",
                borderRadius: "0.75rem",
                fontSize: "0.875rem",
                lineHeight: "1.8",
                backgroundColor: "transparent",
                color: "#ffffff",
              }}
              showLineNumbers={false}
            >
              {codeString}
            </SyntaxHighlighter>
          </div>
        </div>
      </div>
    </section>
  );
}