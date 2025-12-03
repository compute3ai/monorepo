"use client";

import { useEffect, useState } from "react";
import { ContactModal } from "@compute3/shared-ui";

interface ModelInfo {
  name: string;
  description: string;
  context_length: number;
  external: boolean;
}

interface ModelPricing {
  max_tokens: number;
  input_cost_per_token: string;
  output_cost_per_token: string;
  input_price_per_1m: string;
  output_price_per_1m: string;
}

interface ModelGroups {
  "free-models": string[];
  "c3-models": string[];
  "external-models": string[];
}

interface Model {
  id: string;
  name: string;
  description: string;
  context_length: number;
  hosted: boolean;
  free: boolean;
  pricing?: ModelPricing;
}

export default function ModelPricing() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [filter, setFilter] = useState<"all" | "hosted" | "external">("all");
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [modelsRes, pricingRes, groupsRes] = await Promise.all([
          fetch("https://api.compute3.ai/llm/models"),
          fetch("https://api.compute3.ai/llm/pricing"),
          fetch("https://api.compute3.ai/llm/groups"),
        ]);

        const modelsData: Record<string, ModelInfo> = await modelsRes.json();
        const pricingData: Record<string, ModelPricing> = await pricingRes.json();
        const groupsData: ModelGroups = await groupsRes.json();

        const hostedModels = new Set([
          ...groupsData["free-models"],
          ...groupsData["c3-models"],
        ]);
        const freeModels = new Set(groupsData["free-models"]);

        const modelArray: Model[] = Object.entries(modelsData).map(([id, info]) => ({
          id,
          name: info.name,
          description: info.description,
          context_length: info.context_length,
          hosted: hostedModels.has(id),
          free: freeModels.has(id),
          pricing: pricingData[id],
        }));

        // Sort: hosted first, then by name
        modelArray.sort((a, b) => {
          if (a.hosted && !b.hosted) return -1;
          if (!a.hosted && b.hosted) return 1;
          if (a.free && !b.free) return -1;
          if (!a.free && b.free) return 1;
          return a.name.localeCompare(b.name);
        });

        setModels(modelArray);
        setSelectedModel(modelArray[0] || null);
        setLoading(false);
      } catch (err) {
        setError("Failed to load models");
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const filteredModels = models.filter((m) => {
    if (filter === "hosted") return m.hosted;
    if (filter === "external") return !m.hosted;
    return true;
  });

  if (loading) {
    return (
      <div className="py-20 text-center">
        <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-[var(--color-primary)] border-r-transparent"></div>
        <p className="mt-4 text-gray-600">Loading models...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-20 text-center">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <>
      <section className="py-4 sm:py-6">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
          {/* Filter Tabs */}
          <div className="flex justify-center gap-3 mb-8">
            {[
              { key: "all", label: "All Models" },
              { key: "hosted", label: "C3 Hosted" },
              { key: "external", label: "External" },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key as typeof filter)}
                className={`px-6 py-2 rounded-full font-semibold transition-all ${
                  filter === key
                    ? "bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] text-white shadow-md"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Model List */}
            <div className="lg:col-span-1 bg-white border border-gray-200 rounded-2xl overflow-hidden">
              <div className="max-h-[600px] overflow-y-auto">
                {filteredModels.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => setSelectedModel(model)}
                    className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                      selectedModel?.id === model.id ? "bg-blue-50 border-l-4 border-l-[var(--color-primary)]" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-900 text-sm">{model.id}</span>
                      <div className="flex gap-1">
                        {model.free && (
                          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-green-100 text-green-800">
                            FREE
                          </span>
                        )}
                        {model.hosted && !model.free && (
                          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-800">
                            C3
                          </span>
                        )}
                        {!model.hosted && (
                          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-gray-100 text-gray-600">
                            EXT
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-gray-500 truncate mt-1">{model.name}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Model Details */}
            <div className="lg:col-span-2">
              {selectedModel ? (
                <div className="bg-white border border-gray-200 rounded-2xl p-8">
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <h3 className="text-2xl font-bold text-gray-900">{selectedModel.name}</h3>
                      <p className="text-sm font-mono text-gray-500 mt-1">{selectedModel.id}</p>
                    </div>
                    <div className="flex gap-2">
                      {selectedModel.free && (
                        <span className="px-3 py-1 text-sm font-semibold rounded-full bg-green-100 text-green-800">
                          Free Tier
                        </span>
                      )}
                      <span
                        className={`px-3 py-1 text-sm font-semibold rounded-full ${
                          selectedModel.hosted
                            ? "bg-blue-100 text-blue-800"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {selectedModel.hosted ? "C3 Hosted" : "External"}
                      </span>
                    </div>
                  </div>

                  <p className="text-gray-600 mb-8 leading-relaxed">{selectedModel.description}</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    <div className="bg-gray-50 rounded-xl p-4">
                      <p className="text-sm text-gray-500 mb-1">Context Length</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {(selectedModel.context_length / 1000).toLocaleString()}K
                        <span className="text-sm font-normal text-gray-500 ml-1">tokens</span>
                      </p>
                    </div>

                    {selectedModel.pricing && (
                      <>
                        <div className="bg-gray-50 rounded-xl p-4">
                          <p className="text-sm text-gray-500 mb-1">Max Output Tokens</p>
                          <p className="text-2xl font-bold text-gray-900">
                            {(selectedModel.pricing.max_tokens / 1000).toLocaleString()}K
                          </p>
                        </div>
                      </>
                    )}
                  </div>

                  {selectedModel.pricing && (
                    <div className="border-t border-gray-200 pt-6">
                      <h4 className="text-lg font-semibold text-gray-900 mb-4">Pricing</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4">
                          <p className="text-sm text-blue-600 mb-1">Input</p>
                          <p className="text-2xl font-bold text-blue-900">
                            ${selectedModel.pricing.input_price_per_1m}
                            <span className="text-sm font-normal text-blue-600 ml-1">/1M tokens</span>
                          </p>
                        </div>
                        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4">
                          <p className="text-sm text-purple-600 mb-1">Output</p>
                          <p className="text-2xl font-bold text-purple-900">
                            ${selectedModel.pricing.output_price_per_1m}
                            <span className="text-sm font-normal text-purple-600 ml-1">/1M tokens</span>
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center text-gray-500">
                  Select a model to view details
                </div>
              )}
            </div>
          </div>

          {/* CTA */}
          <div className="mt-16 text-center">
            <h3 className="text-3xl font-bold text-gray-900 mb-4">
              Ready to Access Every Model?
            </h3>
            <p className="text-lg text-gray-600 mb-6 max-w-2xl mx-auto">
              Drop-in API replacement. Compatible with OpenAI SDK. Hosted on B200 GPUs.
            </p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-2 btn-primary text-white font-semibold py-3 px-8 rounded-lg text-lg"
            >
              Get API Access
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      </section>

      <ContactModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} source="models-api-access" />
    </>
  );
}
