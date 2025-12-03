export const GPU_INFO: Record<string, { vram: string; arch: string; displayName: string }> = {
  B300: { vram: "260GB HBM3e", arch: "Blackwell", displayName: "B300" },
  B200: { vram: "180GB HBM3e", arch: "Blackwell", displayName: "B200" },
  H200: { vram: "140GB HBM3e", arch: "Hopper", displayName: "H200" },
  H100: { vram: "80GB HBM3", arch: "Hopper", displayName: "H100" },
  A100_80: { vram: "80GB HBM2e", arch: "Ampere", displayName: "A100 80GB" },
  A100_40: { vram: "40GB HBM2e", arch: "Ampere", displayName: "A100 40GB" },
  A6000: { vram: "48GB GDDR6", arch: "Ampere", displayName: "A6000" },
  V100: { vram: "32GB HBM2", arch: "Volta", displayName: "V100" },
  L40S: { vram: "48GB GDDR6", arch: "Ada Lovelace", displayName: "L40S" },
  L4: { vram: "24GB GDDR6", arch: "Ada Lovelace", displayName: "L4" },
  RTX6000ADA: { vram: "48GB GDDR6", arch: "Ada Lovelace", displayName: "RTX 6000 Ada" },
  RTXPRO6000: { vram: "96GB GDDR7", arch: "Blackwell", displayName: "RTX PRO 6000" },
};

export const REGION_INFO: Record<string, { name: string; flag: string }> = {
  se: { name: "Sweden", flag: "🇸🇪" },
  fi: { name: "Finland", flag: "🇫🇮" },
  is: { name: "Iceland", flag: "🇮🇸" },
  va: { name: "Virginia", flag: "🇺🇸" },
  oh: { name: "Ohio", flag: "🇺🇸" },
  br: { name: "Brazil", flag: "🇧🇷" },
  kr: { name: "South Korea", flag: "🇰🇷" },
  or: { name: "Oregon", flag: "🇺🇸" },
  ga: { name: "Georgia", flag: "🇺🇸" },
  ae: { name: "UAE", flag: "🇦🇪" },
  uk: { name: "United Kingdom", flag: "🇬🇧" },
};

export const getGPUDisplayName = (gpuType: string): string => {
  const key = gpuType.toUpperCase();
  return GPU_INFO[key]?.displayName || gpuType.replace("_", " ");
};

export const getGPUVram = (gpuType: string): string => {
  const key = gpuType.toUpperCase();
  return GPU_INFO[key]?.vram || "N/A";
};

export const getGPUArch = (gpuType: string): string => {
  const key = gpuType.toUpperCase();
  return GPU_INFO[key]?.arch || "Unknown";
};

export const getRegionName = (regionCode: string): string => {
  return REGION_INFO[regionCode]?.name || regionCode;
};

export const getRegionFlag = (regionCode: string): string => {
  return REGION_INFO[regionCode]?.flag || "🌍";
};
