"use client";

import React, { useEffect, useState, useRef, useMemo } from "react";
import { Header, Footer, useAuth, getGPUDisplayName, getRegionFlag, getRegionName } from "@compute3/shared-ui";
import { useRouter } from "next/navigation";

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

interface RegionPricing {
  "on-demand"?: number;
  "interruptable"?: number;
}

interface PricingData {
  [key: string]: {
    [region: string]: RegionPricing;
  };
}

interface RegionInfo {
  description: string;
  country: string;
}

// Convert HuggingFace space to registry URL
// Accepts either:
//   - Space ID: "FireRedTeam/FireRedTTS2"
//   - Full URL: "https://huggingface.co/spaces/yasserrmd/VibeVoice?query=params"
// Returns: "registry.hf.space/fireredteam-fireredtts2:latest"
function resolveHfSpaceToImage(space: string): string {
  let spaceId = space.trim();

  // Check if it's a URL
  if (spaceId.includes('huggingface.co/spaces/')) {
    try {
      const url = new URL(spaceId);
      // Extract path after /spaces/ and remove any trailing slashes
      const match = url.pathname.match(/\/spaces\/([^/]+\/[^/]+)/);
      if (match) {
        spaceId = match[1];
      }
    } catch {
      // If URL parsing fails, try simple regex extraction
      const match = spaceId.match(/huggingface\.co\/spaces\/([^/?#]+\/[^/?#]+)/);
      if (match) {
        spaceId = match[1];
      }
    }
  }

  const normalized = spaceId.toLowerCase().replace('/', '-');
  return `registry.hf.space/${normalized}:latest`;
}

// Default values when no localStorage exists
const DEFAULTS = {
  gpuMode: 'single' as 'single' | 'multi',
  gpuType: '',
  gpuCount: 1,
  interruptible: true,
  selectedRegion: 'fi',
  containerSource: 'image' as 'image' | 'dockerfile' | 'hfspace',
  dockerImage: 'nvidia/cuda:12.6.0-runtime-ubuntu22.04',
  hfSpace: '',
  dockerfile: '',
  command: '/bin/sh -c "sleep 5 && nvidia-smi && sleep 600"',
  envVars: [] as {key: string, value: string}[],
  ports: [] as {container: string, host: string}[],
  httpsLbEnabled: false,
  httpsLbPort: '',
  httpsLbAuth: false,
  runtime: 600,
};

const STORAGE_KEY = 'launchJobConfig';

function loadFromStorage<T>(key: keyof typeof DEFAULTS, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (key in parsed) {
        const value = parsed[key];
        // Treat empty string as "no stored value" for command field
        if (key === 'command' && value === '') return fallback;
        return value;
      }
    }
  } catch {}
  return fallback;
}

function saveToStorage(values: Partial<typeof DEFAULTS>) {
  if (typeof window === 'undefined') return;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const existing = stored ? JSON.parse(stored) : {};
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...existing, ...values }));
  } catch {}
}

export default function LaunchPage() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  // API Data
  const [gpuList, setGpuList] = useState<Record<string, GPUInfo>>({});
  const [instanceTypes, setInstanceTypes] = useState<Record<string, InstanceType>>({});
  const [pricing, setPricing] = useState<PricingData>({});
  const [regions, setRegions] = useState<Record<string, RegionInfo>>({});
  const loadedFromCloneRef = useRef(false);

  // Loading FSM: idle -> loading -> ready | error
  const [loadingState, setLoadingState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const isDataReady = loadingState === 'ready';

  // Step 1: Single or Multi-GPU
  const [gpuMode, setGpuMode] = useState<'single' | 'multi'>(DEFAULTS.gpuMode);

  // Step 2: GPU Type selection
  const [gpuType, setGpuType] = useState<string>(DEFAULTS.gpuType);

  // Step 3: GPU Count (for multi-GPU)
  const [gpuCount, setGpuCount] = useState<number>(DEFAULTS.gpuCount);

  // Step 4: Pricing type (interruptible/on-demand)
  const [interruptible, setInterruptible] = useState(DEFAULTS.interruptible);

  // Step 5: Region
  const [selectedRegion, setSelectedRegion] = useState<string>(DEFAULTS.selectedRegion);

  // Container configuration
  const [containerSource, setContainerSource] = useState<'image' | 'dockerfile' | 'hfspace'>(DEFAULTS.containerSource);
  const [dockerImage, setDockerImage] = useState(DEFAULTS.dockerImage);
  const [hfSpace, setHfSpace] = useState(DEFAULTS.hfSpace);
  const [dockerfile, setDockerfile] = useState(DEFAULTS.dockerfile);
  const [command, setCommand] = useState(DEFAULTS.command);
  const [envVars, setEnvVars] = useState<{key: string, value: string}[]>(DEFAULTS.envVars);
  const [ports, setPorts] = useState<{container: string, host: string}[]>(DEFAULTS.ports);
  const [httpsLbEnabled, setHttpsLbEnabled] = useState(DEFAULTS.httpsLbEnabled);
  const [httpsLbPort, setHttpsLbPort] = useState(DEFAULTS.httpsLbPort);
  const [httpsLbAuth, setHttpsLbAuth] = useState(DEFAULTS.httpsLbAuth);
  const [runtime, setRuntime] = useState(DEFAULTS.runtime);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    if (loadedFromCloneRef.current) return;
    setGpuMode(loadFromStorage('gpuMode', DEFAULTS.gpuMode));
    setGpuType(loadFromStorage('gpuType', DEFAULTS.gpuType));
    setGpuCount(loadFromStorage('gpuCount', DEFAULTS.gpuCount));
    setInterruptible(loadFromStorage('interruptible', DEFAULTS.interruptible));
    setSelectedRegion(loadFromStorage('selectedRegion', DEFAULTS.selectedRegion));
    setContainerSource(loadFromStorage('containerSource', DEFAULTS.containerSource));
    setDockerImage(loadFromStorage('dockerImage', DEFAULTS.dockerImage));
    setHfSpace(loadFromStorage('hfSpace', DEFAULTS.hfSpace));
    setDockerfile(loadFromStorage('dockerfile', DEFAULTS.dockerfile));
    setCommand(loadFromStorage('command', DEFAULTS.command));
    setEnvVars(loadFromStorage('envVars', DEFAULTS.envVars));
    setPorts(loadFromStorage('ports', DEFAULTS.ports));
    setHttpsLbEnabled(loadFromStorage('httpsLbEnabled', DEFAULTS.httpsLbEnabled));
    setHttpsLbPort(loadFromStorage('httpsLbPort', DEFAULTS.httpsLbPort));
    setHttpsLbAuth(loadFromStorage('httpsLbAuth', DEFAULTS.httpsLbAuth));
    setRuntime(loadFromStorage('runtime', DEFAULTS.runtime));
  }, []);

  // Save to localStorage when values change
  useEffect(() => { saveToStorage({ gpuMode }); }, [gpuMode]);
  useEffect(() => { saveToStorage({ gpuType }); }, [gpuType]);
  useEffect(() => { saveToStorage({ gpuCount }); }, [gpuCount]);
  useEffect(() => { saveToStorage({ interruptible }); }, [interruptible]);
  useEffect(() => { saveToStorage({ selectedRegion }); }, [selectedRegion]);
  useEffect(() => { saveToStorage({ containerSource }); }, [containerSource]);
  useEffect(() => { saveToStorage({ dockerImage }); }, [dockerImage]);
  useEffect(() => { saveToStorage({ hfSpace }); }, [hfSpace]);
  useEffect(() => { saveToStorage({ dockerfile }); }, [dockerfile]);
  useEffect(() => { saveToStorage({ command }); }, [command]);
  useEffect(() => { saveToStorage({ envVars }); }, [envVars]);
  useEffect(() => { saveToStorage({ ports }); }, [ports]);
  useEffect(() => { saveToStorage({ httpsLbEnabled }); }, [httpsLbEnabled]);
  useEffect(() => { saveToStorage({ httpsLbPort }); }, [httpsLbPort]);
  useEffect(() => { saveToStorage({ httpsLbAuth }); }, [httpsLbAuth]);
  useEffect(() => { saveToStorage({ runtime }); }, [runtime]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isLoading, isAuthenticated, router]);

  // Load cloned job config from sessionStorage
  useEffect(() => {
    const cloneConfig = sessionStorage.getItem('cloneJobConfig');
    if (cloneConfig) {
      try {
        const config = JSON.parse(cloneConfig);
        // Normalize gpu_type to lowercase to match API format
        if (config.gpu_type) setGpuType(config.gpu_type.toLowerCase());
        if (config.gpu_count) {
          setGpuCount(config.gpu_count);
          setGpuMode(config.gpu_count > 1 ? 'multi' : 'single');
        }
        if (config.region) setSelectedRegion(config.region);
        if (typeof config.interruptible === 'boolean') setInterruptible(config.interruptible);
        if (config.hf_space) {
          setContainerSource('hfspace');
          setHfSpace(config.hf_space);
        } else if (config.dockerfile) {
          setContainerSource('dockerfile');
          try {
            setDockerfile(atob(config.dockerfile));
          } catch {
            setDockerfile(config.dockerfile);
          }
        } else if (config.docker_image) {
          setContainerSource('image');
          setDockerImage(config.docker_image);
        }
        if (config.command) {
          try {
            setCommand(atob(config.command));
          } catch {
            if (Array.isArray(config.command)) {
              if (config.command.length >= 3 && config.command[0] === '/bin/bash' && config.command[1] === '-c') {
                setCommand(config.command[2]);
              } else {
                setCommand(config.command.join(' '));
              }
            } else {
              setCommand(config.command);
            }
          }
        }
        if (config.env_vars) {
          const envArray = Object.entries(config.env_vars).map(([key, value]) => ({
            key,
            value: String(value)
          }));
          setEnvVars(envArray);
        }
        if (config.ports) {
          if (config.ports.lb) {
            setHttpsLbEnabled(true);
            setHttpsLbPort(String(config.ports.lb));
          }
          const portsArray = Object.entries(config.ports)
            .filter(([key]) => key !== 'lb')
            .map(([container, host]) => ({
              container,
              host: String(host)
            }));
          setPorts(portsArray);
        }
        if (typeof config.auth === 'boolean') setHttpsLbAuth(config.auth);
        if (config.runtime) setRuntime(config.runtime);

        loadedFromCloneRef.current = true;
        sessionStorage.removeItem('cloneJobConfig');
      } catch (err) {
        console.error('Failed to parse cloned job config:', err);
        sessionStorage.removeItem('cloneJobConfig');
      }
    }
  }, []);

  // Fetch all API data
  useEffect(() => {
    const fetchInstanceData = async () => {
      setLoadingState('loading');

      try {
        const instancesUrl = process.env.NEXT_PUBLIC_INSTANCES_API_URL;
        if (!instancesUrl) {
          console.error('NEXT_PUBLIC_INSTANCES_API_URL not configured');
          setLoadingState('error');
          return;
        }

        const [gpusResponse, typesResponse, pricingResponse, regionsResponse] = await Promise.all([
          fetch(`${instancesUrl}/gpus`),
          fetch(`${instancesUrl}/types`),
          fetch(`${instancesUrl}/pricing`),
          fetch(`${instancesUrl}/regions`)
        ]);

        if (!gpusResponse.ok || !typesResponse.ok || !pricingResponse.ok || !regionsResponse.ok) {
          console.error('Failed to fetch instance data');
          setLoadingState('error');
          return;
        }

        const [gpusData, typesData, pricingData, regionsData] = await Promise.all([
          gpusResponse.json(),
          typesResponse.json(),
          pricingResponse.json(),
          regionsResponse.json()
        ]);

        setGpuList(gpusData);
        setInstanceTypes(typesData);
        setPricing(pricingData);
        setRegions(regionsData);

        // Set default GPU type if not loaded from clone and no localStorage value
        const storedGpuType = loadFromStorage('gpuType', '');
        if (!loadedFromCloneRef.current && !storedGpuType) {
          const gpuKeys = Object.keys(gpusData);
          // Default to cheapest interruptible GPU
          const cheapestGpu = gpuKeys.reduce((cheapest, key) => {
            const gpu = gpusData[key];
            const cheapestPrice = gpusData[cheapest]?.interruptible || Infinity;
            const currentPrice = gpu.interruptible || Infinity;
            return currentPrice < cheapestPrice ? key : cheapest;
          }, gpuKeys[0]);

          if (cheapestGpu) {
            setGpuType(cheapestGpu);
          }
        }

        setLoadingState('ready');
      } catch (error) {
        console.error('Failed to fetch instance data:', error);
        setLoadingState('error');
      }
    };

    fetchInstanceData();
  }, []);

  // Get available GPUs based on mode (single vs multi)
  const availableGpus = useMemo(() => {
    if (!isDataReady) return [];

    return Object.entries(gpuList)
      .filter(([gpuKey]) => {
        const typeInfo = instanceTypes[gpuKey];
        if (!typeInfo) return false;

        // Check if any config has available regions for this mode
        return typeInfo.configs.some(config => {
          if (gpuMode === 'single') {
            return config.gpu_count === 1 && config.regions.length > 0;
          } else {
            return config.gpu_count > 1 && config.regions.length > 0;
          }
        });
      })
      .map(([key, info]) => ({ key, ...info }))
      .sort((a, b) => {
        // Sort by interruptible price
        const priceA = a.interruptible || a["on-demand"] || Infinity;
        const priceB = b.interruptible || b["on-demand"] || Infinity;
        return priceA - priceB;
      });
  }, [gpuList, instanceTypes, gpuMode, isDataReady]);

  // Get available GPU counts for selected GPU type
  const availableGpuCounts = useMemo(() => {
    if (!gpuType || !instanceTypes[gpuType]) return [];

    const typeInfo = instanceTypes[gpuType];
    return typeInfo.configs
      .filter(config => {
        if (gpuMode === 'single') {
          return config.gpu_count === 1 && config.regions.length > 0;
        } else {
          return config.gpu_count > 1 && config.regions.length > 0;
        }
      })
      .map(config => ({
        count: config.gpu_count,
        cpu_cores: config.cpu_cores,
        memory_gb: config.memory_gb,
        storage_gb: config.storage_gb,
        regions: config.regions
      }))
      .sort((a, b) => a.count - b.count);
  }, [gpuType, instanceTypes, gpuMode]);

  // Get available regions for current GPU + count selection
  const availableRegions = useMemo(() => {
    if (!gpuType || !gpuCount) return [];

    const pricingKey = `${gpuType}_x${gpuCount}`;
    const regionPricing = pricing[pricingKey];
    if (!regionPricing) return [];

    return Object.entries(regionPricing)
      .map(([regionCode, prices]) => ({
        code: regionCode,
        info: regions[regionCode],
        onDemand: prices["on-demand"] || null,
        interruptible: prices["interruptable"] || null,
      }))
      .filter(r => interruptible ? r.interruptible !== null : r.onDemand !== null)
      .sort((a, b) => {
        const priceA = interruptible ? (a.interruptible || Infinity) : (a.onDemand || Infinity);
        const priceB = interruptible ? (b.interruptible || Infinity) : (b.onDemand || Infinity);
        return priceA - priceB;
      });
  }, [gpuType, gpuCount, pricing, regions, interruptible]);

  // Auto-select first GPU when mode changes
  useEffect(() => {
    if (availableGpus.length > 0 && !loadedFromCloneRef.current) {
      const currentGpuAvailable = availableGpus.some(g => g.key === gpuType);
      if (!currentGpuAvailable) {
        setGpuType(availableGpus[0].key);
      }
    }
  }, [availableGpus, gpuType]);

  // Auto-select first GPU count when GPU type changes
  useEffect(() => {
    if (availableGpuCounts.length > 0 && !loadedFromCloneRef.current) {
      const currentCountAvailable = availableGpuCounts.some(c => c.count === gpuCount);
      if (!currentCountAvailable) {
        setGpuCount(availableGpuCounts[0].count);
      }
    }
  }, [availableGpuCounts, gpuCount]);

  // Auto-select first region when options change
  useEffect(() => {
    if (availableRegions.length > 0 && !loadedFromCloneRef.current) {
      const currentRegionAvailable = availableRegions.some(r => r.code === selectedRegion);
      if (!currentRegionAvailable) {
        setSelectedRegion(availableRegions[0].code);
      }
    }
  }, [availableRegions, selectedRegion]);

  // Check if pricing type is available
  const pricingAvailability = useMemo(() => {
    if (!gpuType || !gpuCount) return { interruptible: false, onDemand: false };

    const pricingKey = `${gpuType}_x${gpuCount}`;
    const regionPricing = pricing[pricingKey];
    if (!regionPricing) return { interruptible: false, onDemand: false };

    let hasInterruptible = false;
    let hasOnDemand = false;

    Object.values(regionPricing).forEach(prices => {
      if (prices["interruptable"]) hasInterruptible = true;
      if (prices["on-demand"]) hasOnDemand = true;
    });

    return { interruptible: hasInterruptible, onDemand: hasOnDemand };
  }, [gpuType, gpuCount, pricing]);

  // Auto-switch pricing type if not available
  useEffect(() => {
    if (interruptible && !pricingAvailability.interruptible && pricingAvailability.onDemand) {
      setInterruptible(false);
    } else if (!interruptible && !pricingAvailability.onDemand && pricingAvailability.interruptible) {
      setInterruptible(true);
    }
  }, [pricingAvailability, interruptible]);

  // Get current pricing
  const currentPricing = useMemo(() => {
    if (!gpuType || !gpuCount || !selectedRegion) return null;

    const pricingKey = `${gpuType}_x${gpuCount}`;
    const regionPricing = pricing[pricingKey]?.[selectedRegion];
    if (!regionPricing) return null;

    return {
      onDemand: regionPricing["on-demand"] || null,
      interruptible: regionPricing["interruptable"] || null
    };
  }, [gpuType, gpuCount, selectedRegion, pricing]);

  const currentPrice = currentPricing
    ? (interruptible ? currentPricing.interruptible : currentPricing.onDemand)
    : null;
  const estimatedCost = currentPrice ? (currentPrice * runtime / 3600) : null;

  // Get selected config specs
  const selectedConfig = useMemo(() => {
    if (!gpuType || !gpuCount || !instanceTypes[gpuType]) return null;
    return instanceTypes[gpuType].configs.find(c => c.gpu_count === gpuCount) || null;
  }, [gpuType, gpuCount, instanceTypes]);

  const createJob = async () => {
    setIsCreating(true);
    setError(null);

    try {
      if (httpsLbEnabled && !httpsLbPort.trim()) {
        setError('HTTPS Load Balancer port is required');
        setIsCreating(false);
        return;
      }

      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) {
        setError('No auth token found');
        setIsCreating(false);
        return;
      }

      const envVarsObj: Record<string, string> = {};
      envVars.forEach(({key, value}) => {
        if (key.trim()) {
          envVarsObj[key.trim()] = value;
        }
      });

      const portsObj: Record<string, number> = {};
      ports.forEach(({container, host}) => {
        if (container.trim() && host.trim()) {
          portsObj[container.trim()] = parseInt(host.trim());
        }
      });

      if (httpsLbEnabled && httpsLbPort.trim()) {
        portsObj['lb'] = parseInt(httpsLbPort.trim());
      }

      // Resolve docker image based on source
      const resolvedDockerImage = containerSource === 'hfspace'
        ? resolveHfSpaceToImage(hfSpace)
        : dockerImage;

      // HF spaces need python app.py as they don't have an entrypoint
      const resolvedCommand = containerSource === 'hfspace'
        ? 'python app.py'
        : command;

      const jobSpec: any = {
        gpu_type: gpuType.toUpperCase(),
        gpu_count: gpuCount,
        region: selectedRegion,
        interruptible: interruptible,
        docker_image: resolvedDockerImage,
        command: btoa(resolvedCommand),
        env_vars: Object.keys(envVarsObj).length > 0 ? envVarsObj : undefined,
        ports: Object.keys(portsObj).length > 0 ? portsObj : undefined,
        auth: httpsLbAuth,
        runtime: runtime
      };

      if (containerSource === 'dockerfile' && dockerfile.trim()) {
        jobSpec.dockerfile = btoa(dockerfile);
      }

      if (containerSource === 'hfspace' && hfSpace.trim()) {
        jobSpec.hf_space = hfSpace.trim();
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(jobSpec)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create job');
      }

      const createdJob = await response.json();
      router.push(`/job/${createdJob.job_id}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-900 text-xl">Loading...</div>
      </div>
    );
  }

  if (loadingState === 'error') {
    return (
      <div className="min-h-screen flex flex-col overflow-x-hidden">
        <Header />
        <main className="flex-1 pt-20 relative">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
              <h2 className="text-xl font-bold mb-2">Error Loading Instance Data</h2>
              <p>Failed to load GPU types and pricing. Please try again later.</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 btn-primary text-white font-semibold py-2 px-4 rounded-lg"
              >
                Retry
              </button>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <Header />

      <main className="flex-1 pt-20 relative">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-8">Launch GPU</h1>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: GPU Selection */}
            <div className="lg:col-span-2 space-y-6">
              {/* Step 1: Single vs Multi-GPU */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold text-gray-900 mb-4">1. Select GPU Mode</h2>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setGpuMode('single')}
                    disabled={!isDataReady}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      gpuMode === 'single'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-semibold text-gray-900">Single GPU</div>
                    <div className="text-sm text-gray-500">1 GPU for inference, fine-tuning, development</div>
                  </button>
                  <button
                    onClick={() => setGpuMode('multi')}
                    disabled={!isDataReady}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      gpuMode === 'multi'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-semibold text-gray-900">Multi-GPU</div>
                    <div className="text-sm text-gray-500">2-8 GPUs for training, large models</div>
                  </button>
                </div>
              </div>

              {/* Step 2: GPU Type */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold text-gray-900 mb-4">2. Select GPU Type</h2>
                {!isDataReady ? (
                  <div className="text-gray-500">Loading GPUs...</div>
                ) : availableGpus.length === 0 ? (
                  <div className="text-gray-500">No GPUs available for {gpuMode} mode</div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {availableGpus.map((gpu) => (
                      <button
                        key={gpu.key}
                        onClick={() => setGpuType(gpu.key)}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          gpuType === gpu.key
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="font-semibold text-gray-900">{gpu.name}</div>
                        <div className="text-xs text-gray-500 mt-1">{gpu.description}</div>
                        <div className="text-sm font-medium text-green-600 mt-2">
                          from ${(gpu.interruptible || gpu["on-demand"] || 0).toFixed(2)}/hr
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Step 3: GPU Count (for multi-GPU) */}
              {gpuMode === 'multi' && availableGpuCounts.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h2 className="text-lg font-bold text-gray-900 mb-4">3. Select GPU Count</h2>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {availableGpuCounts.map((config) => (
                      <button
                        key={config.count}
                        onClick={() => setGpuCount(config.count)}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          gpuCount === config.count
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="font-semibold text-gray-900">{config.count}x GPUs</div>
                        <div className="text-xs text-gray-500 mt-1">
                          {config.cpu_cores} vCPUs, {config.memory_gb}GB RAM
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 4: Pricing Type */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold text-gray-900 mb-4">
                  {gpuMode === 'multi' ? '4' : '3'}. Select Pricing Type
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setInterruptible(true)}
                    disabled={!pricingAvailability.interruptible}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      interruptible
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    } ${!pricingAvailability.interruptible ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-gray-900">Interruptible (Spot)</span>
                      {interruptible && (
                        <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">Lower cost, may be interrupted if demand is high</p>
                    {!pricingAvailability.interruptible && (
                      <p className="text-xs text-red-500 mt-1">Not available for this configuration</p>
                    )}
                  </button>

                  <button
                    onClick={() => setInterruptible(false)}
                    disabled={!pricingAvailability.onDemand}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      !interruptible
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    } ${!pricingAvailability.onDemand ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-gray-900">On-Demand</span>
                      {!interruptible && (
                        <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">Guaranteed to run, no interruptions</p>
                    {!pricingAvailability.onDemand && (
                      <p className="text-xs text-red-500 mt-1">Not available for this configuration</p>
                    )}
                  </button>
                </div>
              </div>

              {/* Step 5: Region */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold text-gray-900 mb-4">
                  {gpuMode === 'multi' ? '5' : '4'}. Select Region
                </h2>
                {availableRegions.length === 0 ? (
                  <div className="text-gray-500">No regions available for this configuration</div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {availableRegions.map((region) => {
                      const price = interruptible ? region.interruptible : region.onDemand;
                      return (
                        <button
                          key={region.code}
                          onClick={() => setSelectedRegion(region.code)}
                          className={`p-4 rounded-lg border-2 transition-all text-left ${
                            selectedRegion === region.code
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{getRegionFlag(region.code)}</span>
                            <span className="font-semibold text-gray-900">
                              {region.info?.description || getRegionName(region.code)}
                            </span>
                          </div>
                          {price && (
                            <div className="text-sm font-medium text-green-600 mt-1">
                              ${price.toFixed(2)}/hr
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Container Configuration */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold text-gray-900 mb-4">Container Configuration</h2>

                <div className="space-y-4">
                  <div>
                    <div className="flex gap-4 mb-3">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={containerSource === 'image'}
                          onChange={() => setContainerSource('image')}
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="text-sm text-gray-700">Docker Image</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={containerSource === 'dockerfile'}
                          onChange={() => setContainerSource('dockerfile')}
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="text-sm text-gray-700">Dockerfile</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={containerSource === 'hfspace'}
                          onChange={() => {
                            setContainerSource('hfspace');
                            // Auto-set command for HF spaces
                            if (!command.trim()) {
                              setCommand('python app.py');
                            }
                            // Auto-enable HTTPS load balancer on port 7860 (Gradio default)
                            setHttpsLbEnabled(true);
                            setHttpsLbPort('7860');
                          }}
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="text-sm text-gray-700">HF Space</span>
                      </label>
                    </div>

                    {containerSource === 'image' && (
                      <input
                        type="text"
                        value={dockerImage}
                        onChange={(e) => setDockerImage(e.target.value)}
                        placeholder="e.g., nvidia/cuda:12.6.0-runtime-ubuntu22.04"
                        className="w-full border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                      />
                    )}
                    {containerSource === 'dockerfile' && (
                      <textarea
                        value={dockerfile}
                        onChange={(e) => setDockerfile(e.target.value)}
                        rows={6}
                        placeholder="FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04&#10;RUN apt-get update && apt-get install -y python3&#10;..."
                        className="w-full border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                      />
                    )}
                    {containerSource === 'hfspace' && (
                      <div>
                        <input
                          type="text"
                          value={hfSpace}
                          onChange={(e) => setHfSpace(e.target.value)}
                          placeholder="e.g., FireRedTeam/FireRedTTS2"
                          className="w-full border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        {hfSpace.trim() && (
                          <p className="mt-2 text-xs text-gray-500">
                            Resolves to: <code className="bg-gray-100 px-1 rounded">{resolveHfSpaceToImage(hfSpace)}</code>
                          </p>
                        )}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-sm font-semibold text-gray-700">
                        Command (Optional)
                      </label>
                      <button
                        type="button"
                        onClick={() => setCommand("nvidia-smi")}
                        className="text-xs text-blue-600 hover:text-blue-700"
                      >
                        Use nvidia-smi
                      </button>
                    </div>
                    <textarea
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                      rows={3}
                      placeholder="nvidia-smi"
                      className="w-full border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Environment Variables
                    </label>
                    {envVars.map((envVar, index) => (
                      <div key={index} className="flex gap-2 mb-2">
                        <input
                          type="text"
                          value={envVar.key}
                          onChange={(e) => {
                            const updated = [...envVars];
                            updated[index].key = e.target.value;
                            setEnvVars(updated);
                          }}
                          placeholder="KEY"
                          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        <input
                          type="text"
                          value={envVar.value}
                          onChange={(e) => {
                            const updated = [...envVars];
                            updated[index].value = e.target.value;
                            setEnvVars(updated);
                          }}
                          placeholder="value"
                          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setEnvVars(envVars.filter((_, i) => i !== index))}
                          className="px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => setEnvVars([...envVars, {key: "", value: ""}])}
                      className="text-sm text-blue-600 hover:text-blue-700"
                    >
                      + Add Environment Variable
                    </button>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Port Forwarding
                    </label>
                    {ports.map((port, index) => (
                      <div key={index} className="flex gap-2 mb-2 items-center">
                        <input
                          type="text"
                          value={port.container}
                          onChange={(e) => {
                            const updated = [...ports];
                            updated[index].container = e.target.value;
                            setPorts(updated);
                          }}
                          placeholder="Container Port"
                          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        <span className="text-gray-500">→</span>
                        <input
                          type="text"
                          value={port.host}
                          onChange={(e) => {
                            const updated = [...ports];
                            updated[index].host = e.target.value;
                            setPorts(updated);
                          }}
                          placeholder="Host Port"
                          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setPorts(ports.filter((_, i) => i !== index))}
                          className="px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => setPorts([...ports, {container: "", host: ""}])}
                      className="text-sm text-blue-600 hover:text-blue-700"
                    >
                      + Add Port Mapping
                    </button>
                  </div>

                  <div>
                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                      <input
                        type="checkbox"
                        checked={httpsLbEnabled}
                        onChange={(e) => setHttpsLbEnabled(e.target.checked)}
                        className="w-4 h-4 text-blue-600"
                      />
                      <span className="text-sm font-semibold text-gray-700">Enable HTTPS Load Balancer</span>
                    </label>
                    {httpsLbEnabled && (
                      <div className="ml-6 space-y-2">
                        <input
                          type="text"
                          value={httpsLbPort}
                          onChange={(e) => setHttpsLbPort(e.target.value)}
                          placeholder="Container Port (e.g., 8188)"
                          className="w-full border border-gray-300 rounded-lg px-4 py-2 font-mono text-sm"
                        />
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={httpsLbAuth}
                            onChange={(e) => setHttpsLbAuth(e.target.checked)}
                            className="w-4 h-4 text-blue-600"
                          />
                          <span className="text-sm text-gray-700">Require authentication cookie</span>
                        </label>
                      </div>
                    )}
                  </div>

                </div>
              </div>
            </div>

            {/* Right Column: Summary & Launch */}
            <div className="lg:col-span-1">
              <div className="bg-white p-6 rounded-lg shadow sticky top-24">
                <h2 className="text-lg font-bold text-gray-900 mb-4">Summary</h2>

                <div className="space-y-3 mb-6">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">GPU</span>
                    <span className="font-medium text-gray-900">
                      {gpuType ? `${gpuCount}x ${getGPUDisplayName(gpuType)}` : '-'}
                    </span>
                  </div>

                  {selectedConfig && (
                    <>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">vCPUs</span>
                        <span className="font-medium text-gray-900">{selectedConfig.cpu_cores}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">RAM</span>
                        <span className="font-medium text-gray-900">{selectedConfig.memory_gb} GB</span>
                      </div>
                      {selectedConfig.storage_gb > 0 && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500">Storage</span>
                          <span className="font-medium text-gray-900">{selectedConfig.storage_gb} GB</span>
                        </div>
                      )}
                    </>
                  )}

                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Region</span>
                    <span className="font-medium text-gray-900">
                      {selectedRegion ? `${getRegionFlag(selectedRegion)} ${getRegionName(selectedRegion)}` : '-'}
                    </span>
                  </div>

                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Pricing</span>
                    <span className="font-medium text-gray-900">
                      {interruptible ? 'Interruptible' : 'On-Demand'}
                    </span>
                  </div>

                  <div className="border-t pt-3 mt-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Price</span>
                      <span className="font-bold text-lg text-gray-900">
                        {currentPrice ? `$${currentPrice.toFixed(2)}/hr` : '-'}
                      </span>
                    </div>
                    {estimatedCost !== null && (
                      <div className="flex justify-between text-sm mt-1">
                        <span className="text-gray-500">Est. Cost</span>
                        <span className="font-medium text-green-600">${estimatedCost.toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Runtime Budget in Summary */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-500 mb-2">Runtime Budget</label>
                  <div className="space-y-2">
                    <input
                      type="range"
                      min="60"
                      max="14400"
                      step="60"
                      value={runtime}
                      onChange={(e) => setRuntime(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <div className="flex gap-2 items-center">
                      <input
                        type="text"
                        value={runtime === 0 ? '' : runtime}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (val === '') {
                            setRuntime(0);
                          } else {
                            const num = parseInt(val);
                            if (!isNaN(num)) {
                              setRuntime(Math.min(86400, Math.max(0, num)));
                            }
                          }
                        }}
                        onBlur={() => {
                          if (runtime < 60) setRuntime(60);
                        }}
                        placeholder="sec"
                        className="w-20 border border-gray-300 rounded-lg px-2 py-1 text-sm"
                      />
                      <span className="text-xs text-gray-500">sec</span>
                    </div>
                    <div className="flex gap-1">
                      {[600, 1800, 3600, 7200].map((preset) => (
                        <button
                          key={preset}
                          type="button"
                          onClick={() => setRuntime(preset)}
                          className={`flex-1 px-2 py-1 text-xs rounded ${runtime === preset ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                        >
                          {preset >= 3600 ? `${preset / 3600}h` : `${preset / 60}m`}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                    {error}
                  </div>
                )}

                <button
                  onClick={createJob}
                  disabled={isCreating || !gpuType || !selectedRegion || !currentPrice}
                  className="w-full btn-primary text-white font-semibold py-3 px-6 rounded-lg disabled:opacity-50"
                >
                  {isCreating ? 'Launching...' : 'Launch GPU'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
