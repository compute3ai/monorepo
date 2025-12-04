"use client";

import dynamic from "next/dynamic";

const ParticleCanvas = dynamic(() => import("@/components/ParticleCanvas"), { ssr: false });

export default function ClientParticleCanvas() {
  return <ParticleCanvas />;
}
