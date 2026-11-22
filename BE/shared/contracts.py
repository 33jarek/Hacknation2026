from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class SourceNotice(TypedDict, total=False):
    name: str
    category: str
    url: str
    accessed_at: str
    status: str
    note: str


class Recommendation(TypedDict, total=False):
    title: str
    category: str
    priority: str
    rationale: str
    evidence: List[str]
    confidence: str


class ParcelSummary(TypedDict, total=False):
    id: str
    parcel_number: str
    voivodeship: str
    county: str
    commune: str
    region: str
    area_ha: float
    centroid: Dict[str, float]
    geometry: Dict[str, Any]
    bbox: List[float]


class AnalysisReport(TypedDict, total=False):
    parcel: ParcelSummary
    crop: str
    analysis_date: str
    current_status: Dict[str, Any]
    historical_context: Dict[str, Any]
    retention_context: Dict[str, Any]
    irrigation_guidance: Dict[str, Any]
    recommendations: List[Recommendation]
    sources: List[SourceNotice]
    limitations: List[str]
    missing_data: List[str]
    generated_at: str
