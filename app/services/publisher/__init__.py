"""Publisher and Export Studio package for Fábrica de Shorts.

Generates SEO-optimized publication metadata, A/B titles, chapters,
and packages ready-to-upload ZIP bundles for YouTube Shorts, Reels and TikTok.
"""

from .metadata_generator import MetadataGenerator, PublicationMetadata, generate_ab_titles
from .package_exporter import PackageExporter

__all__ = [
    "MetadataGenerator",
    "PackageExporter",
    "PublicationMetadata",
    "generate_ab_titles",
]
