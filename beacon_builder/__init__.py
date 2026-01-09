"""
Beacon Builder Module

Provides functionality to build custom beacons by selecting modules
and generating both the beacon code and matching schema.
"""

from .builder import BeaconBuilder, ModuleManifest, get_supported_languages

__all__ = ['BeaconBuilder', 'ModuleManifest', 'get_supported_languages']
