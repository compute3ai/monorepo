"use client";

import { useEffect, useState } from "react";
import { ContactModal, NAV_URLS, GPU_INFO, getRegionFlag, getRegionName } from "@compute3/shared-ui";

interface GPUInfo {
  name: string;
  description: string;
  "on-demand": number | null;
  interruptible: number | null;
}

interface InstanceConfig {
  gpu_count: number;
  cpu_cores: number;
  memory_gb: number;
  storage_gb: number;
  regions: string[];
}

interface InstanceType {
  name: string;
  description: string;
  configs: InstanceConfig[];
}

interface GPU {
  key: string;
  name: string;
  description: string;
  memory: string;
  tier: "high-end" | "mid-range" | "cost-effective";
  onDemand: number | null;
  interruptible: number | null;
  isCheapest: boolean;
  regions: string[];
}

// Map GPU keys to tiers
const gpuTiers: Record<string, "high-end" | "mid-range" | "cost-effective"> = {
  b300: "high-end",
  b200: "high-end",
  h200: "high-end",
  h100: "high-end",
  rtxpro6000: "mid-range",
  a100_80: "mid-range",
  a100_40: "mid-range",
  l40s: "mid-range",
  rtx6000ada: "mid-range",
  a6000: "cost-effective",
  l4: "cost-effective",
  v100: "cost-effective",
};

// Mid-range GPU sort order
const midRangeOrder = ["rtxpro6000", "a100_80", "a100_40", "l40s", "rtx6000ada"];

// GPU display order (priority)
const gpuOrder = ["b300", "b200", "h200", "h100", "a100_80", "l40s", "rtxpro6000", "rtx6000ada", "a6000", "l4"];

export default function GPUFleet() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalSource, setModalSource] = useState("");
  const [gpus, setGpus] = useState<GPU[]>([]);
  const [loading, setLoading] = useState(true);

  const openModal = (source: string) => {
    setModalSource(source);
    setIsModalOpen(true);
  };

  useEffect(() => {
    const instancesApiUrl = process.env.NEXT_PUBLIC_INSTANCES_API_URL;

    if (!instancesApiUrl) {
      console.error('NEXT_PUBLIC_INSTANCES_API_URL is not set');
      setLoading(false);
      return;
    }

    Promise.all([
      fetch(`${instancesApiUrl}/gpus`).then(res => {
        if (!res.ok) throw new Error(`GPUs fetch failed: ${res.status}`);
        return res.json();
      }),
      fetch(`${instancesApiUrl}/types`).then(res => {
        if (!res.ok) throw new Error(`Types fetch failed: ${res.status}`);
        return res.json();
      })
    ])
      .then(([gpusData, typesData]: [Record<string, GPUInfo>, Record<string, InstanceType>]) => {
        // Build regions map from types
        const gpuRegions: Record<string, string[]> = {};
        Object.entries(typesData).forEach(([gpuKey, typeInfo]) => {
          const allRegions = new Set<string>();
          typeInfo.configs.forEach(config => {
            config.regions?.forEach(region => allRegions.add(region));
          });
          gpuRegions[gpuKey] = Array.from(allRegions);
        });

        // Find cheapest GPU
        let cheapestGpu = "";
        let cheapestPrice = Infinity;
        Object.entries(gpusData).forEach(([gpuKey, gpuInfo]) => {
          const price = gpuInfo.interruptible || gpuInfo["on-demand"] || Infinity;
          if (price < cheapestPrice) {
            cheapestPrice = price;
            cheapestGpu = gpuKey;
          }
        });

        // Build GPU list from API data
        const gpuList: GPU[] = Object.entries(gpusData)
          .map(([gpuKey, gpuInfo]) => {
            const gpuInfoLocal = GPU_INFO[gpuKey.toUpperCase()];
            return {
              key: gpuKey,
              name: gpuInfo.name,
              description: gpuInfo.description,
              memory: gpuInfoLocal?.vram || gpuInfo.description.match(/\d+GB/)?.[0] || "N/A",
              tier: gpuTiers[gpuKey] || "mid-range",
              onDemand: gpuInfo["on-demand"],
              interruptible: gpuInfo.interruptible,
              isCheapest: gpuKey === cheapestGpu,
              regions: gpuRegions[gpuKey] || [],
            };
          })
          .sort((a, b) => {
            // Sort by tier: high-end first, then mid-range, then cost-effective
            const tierOrder = { "high-end": 0, "mid-range": 1, "cost-effective": 2 };
            const tierDiff = tierOrder[a.tier] - tierOrder[b.tier];
            if (tierDiff !== 0) return tierDiff;

            // Within mid-range, use specific order
            if (a.tier === "mid-range") {
              const aIdx = midRangeOrder.indexOf(a.key);
              const bIdx = midRangeOrder.indexOf(b.key);
              if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
              if (aIdx !== -1) return -1;
              if (bIdx !== -1) return 1;
            }

            // Otherwise sort by on-demand price (higher = more powerful)
            return (b.onDemand || 0) - (a.onDemand || 0);
          });

        setGpus(gpuList);
        setLoading(false);
      })
      .catch(error => {
        console.error("Failed to fetch GPU data:", error);
        setLoading(false);
      });
  }, []);

  const tierColors = {
    "high-end": "from-purple-500 to-pink-500",
    "mid-range": "from-blue-500 to-cyan-500",
    "cost-effective": "from-green-500 to-emerald-500",
  };

  const tierLabels = {
    "high-end": "High-End",
    "mid-range": "Mid-Range",
    "cost-effective": "Cost-Effective",
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
  }, [gpus, loading]);

  return (
    <>
    <section className="py-20 sm:py-28 bg-[var(--color-bg-light)] overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold tracking-tighter text-gray-900 animate-on-scroll">
            World-Class GPU Fleet
          </h2>
          <p className="mt-4 max-w-2xl mx-auto text-lg text-gray-600 animate-on-scroll" style={{ transitionDelay: "100ms" }}>
            From cost-effective L4s to cutting-edge B300s. Choose the right GPU for your workload.
          </p>
        </div>

        {loading ? (
          <div className="mt-16 text-center text-gray-500">Loading GPUs...</div>
        ) : gpus.length === 0 ? (
          <div className="mt-16 text-center text-gray-500">No GPUs available</div>
        ) : (
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
            {gpus.map((gpu, index) => (
              <div
                key={gpu.key}
                className="relative bg-white rounded-2xl p-6 shadow-sm card animate-on-scroll group hover:shadow-xl transition-shadow duration-300"
                style={{ transitionDelay: `${index * 50}ms` }}
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${tierColors[gpu.tier]} opacity-0 group-hover:opacity-5 rounded-2xl transition-opacity duration-300`}></div>

                <div className="relative">
                  <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
                    <div className={`text-xs font-semibold px-2 py-1 rounded-full bg-gradient-to-r ${tierColors[gpu.tier]} text-white`}>
                      {tierLabels[gpu.tier]}
                    </div>
                  </div>

                  <h3 className="text-2xl md:text-3xl font-black text-gray-900 mb-1">
                    {gpu.name}
                  </h3>

                  <p className="text-lg text-gray-600 font-semibold">
                    {gpu.memory}
                  </p>

                  {(gpu.interruptible || gpu.onDemand) && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500">starting at</p>
                      <p className="text-xl font-bold text-[var(--color-primary)]">
                        ${(gpu.interruptible || gpu.onDemand)?.toFixed(2)}
                        <span className="text-xs text-gray-500 font-normal">/hr</span>
                      </p>
                    </div>
                  )}

                  {gpu.regions.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-1">Available in</p>
                      <div className="flex flex-wrap gap-1">
                        {gpu.regions.map((region) => (
                          <span
                            key={region}
                            className="inline-flex items-center gap-1 text-xs bg-gray-100 px-2 py-1 rounded"
                            title={getRegionName(region)}
                          >
                            <span>{getRegionFlag(region)}</span>
                            <span className="text-gray-600">{region.toUpperCase()}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-12 text-center animate-on-scroll" style={{ transitionDelay: "400ms" }}>
          <a
            href={NAV_URLS.gpus}
            className="inline-flex items-center gap-2 btn-secondary font-semibold py-3 px-8 rounded-lg text-lg"
          >
            Explore our GPUs
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
