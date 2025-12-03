"""Instances API - GPU types, regions, and pricing"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


@dataclass
class GPUConfig:
    """Configuration for a specific GPU count"""
    gpu_count: int
    cpu_cores: float
    memory_gb: float
    storage_gb: float
    regions: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "GPUConfig":
        return cls(
            gpu_count=data.get("gpu_count", 1),
            cpu_cores=data.get("cpu_cores", 0),
            memory_gb=data.get("memory_gb", 0),
            storage_gb=data.get("storage_gb", 0),
            regions=data.get("regions", []),
        )


@dataclass
class GPUType:
    """GPU type with its configurations"""
    id: str
    name: str
    description: str
    configs: list[GPUConfig]

    @classmethod
    def from_dict(cls, id: str, data: dict) -> "GPUType":
        return cls(
            id=id,
            name=data.get("name", id),
            description=data.get("description", ""),
            configs=[GPUConfig.from_dict(c) for c in data.get("configs", [])],
        )

    def available_regions(self, gpu_count: int = 1) -> list[str]:
        """Get regions where this GPU is available for given count"""
        for config in self.configs:
            if config.gpu_count == gpu_count:
                return config.regions
        return []

    def available_counts(self) -> list[int]:
        """Get available GPU counts for this type"""
        return [c.gpu_count for c in self.configs if c.regions]


@dataclass
class Region:
    """A datacenter region"""
    id: str
    description: str
    country: str

    @classmethod
    def from_dict(cls, id: str, data: dict) -> "Region":
        return cls(
            id=id,
            description=data.get("description", id),
            country=data.get("country", ""),
        )


@dataclass
class PricingTier:
    """Pricing for a specific region"""
    region: str
    on_demand: float | None = None
    interruptible: float | None = None

    @classmethod
    def from_dict(cls, region: str, data: dict) -> "PricingTier":
        return cls(
            region=region,
            on_demand=data.get("on-demand"),
            interruptible=data.get("interruptable"),  # Note: API has typo
        )


@dataclass
class GPUPricing:
    """Pricing for a GPU configuration"""
    gpu_type: str
    gpu_count: int
    tiers: list[PricingTier]

    @classmethod
    def from_key(cls, key: str, data: dict) -> "GPUPricing":
        # Parse key like "h100_x8" -> gpu_type="h100", gpu_count=8
        parts = key.rsplit("_x", 1)
        gpu_type = parts[0]
        gpu_count = int(parts[1]) if len(parts) > 1 else 1

        tiers = [PricingTier.from_dict(region, prices) for region, prices in data.items()]
        return cls(gpu_type=gpu_type, gpu_count=gpu_count, tiers=tiers)

    def get_price(self, region: str, interruptible: bool = True) -> float | None:
        """Get price for a specific region and tier"""
        for tier in self.tiers:
            if tier.region == region:
                return tier.interruptible if interruptible else tier.on_demand
        return None


class Instances:
    """Instances API - GPU types, regions, and pricing"""

    def __init__(self, http: "HTTPClient"):
        self._http = http
        self._types_cache: dict[str, GPUType] | None = None
        self._regions_cache: dict[str, Region] | None = None
        self._pricing_cache: dict[str, GPUPricing] | None = None

    def types(self, refresh: bool = False) -> dict[str, GPUType]:
        """Get available GPU types"""
        if self._types_cache is None or refresh:
            data = self._http.get("/instances/types")
            self._types_cache = {
                id: GPUType.from_dict(id, info) for id, info in data.items()
            }
        return self._types_cache

    def regions(self, refresh: bool = False) -> dict[str, Region]:
        """Get available regions"""
        if self._regions_cache is None or refresh:
            data = self._http.get("/instances/regions")
            self._regions_cache = {
                id: Region.from_dict(id, info) for id, info in data.items()
            }
        return self._regions_cache

    def pricing(self, refresh: bool = False) -> dict[str, GPUPricing]:
        """Get pricing information"""
        if self._pricing_cache is None or refresh:
            data = self._http.get("/instances/pricing")
            self._pricing_cache = {
                key: GPUPricing.from_key(key, prices) for key, prices in data.items()
            }
        return self._pricing_cache

    def get_type(self, gpu_type: str) -> GPUType | None:
        """Get a specific GPU type by ID"""
        return self.types().get(gpu_type)

    def get_region(self, region_id: str) -> Region | None:
        """Get a specific region by ID"""
        return self.regions().get(region_id)

    def get_price(
        self, gpu_type: str, gpu_count: int = 1, region: str = None, interruptible: bool = True
    ) -> float | None:
        """Get price for a specific GPU configuration"""
        key = f"{gpu_type}_x{gpu_count}"
        pricing = self.pricing().get(key)
        if pricing and region:
            return pricing.get_price(region, interruptible)
        return None

    def list_available(self, gpu_type: str = None, region: str = None) -> list[dict]:
        """List available GPU configurations, optionally filtered"""
        types = self.types()
        regions = self.regions()
        pricing = self.pricing()

        results = []
        for type_id, gpu in types.items():
            if gpu_type and type_id != gpu_type:
                continue

            for config in gpu.configs:
                if not config.regions:
                    continue
                if region and region not in config.regions:
                    continue

                key = f"{type_id}_x{config.gpu_count}"
                gpu_pricing = pricing.get(key)

                for r in config.regions:
                    if region and r != region:
                        continue

                    region_info = regions.get(r)
                    price_info = gpu_pricing.get_price(r, True) if gpu_pricing else None
                    on_demand_price = gpu_pricing.get_price(r, False) if gpu_pricing else None

                    results.append({
                        "gpu_type": type_id,
                        "gpu_name": gpu.name,
                        "gpu_count": config.gpu_count,
                        "cpu_cores": config.cpu_cores,
                        "memory_gb": config.memory_gb,
                        "storage_gb": config.storage_gb,
                        "region": r,
                        "region_name": region_info.description if region_info else r,
                        "country": region_info.country if region_info else "",
                        "price_spot": price_info,
                        "price_on_demand": on_demand_price,
                    })

        return results
