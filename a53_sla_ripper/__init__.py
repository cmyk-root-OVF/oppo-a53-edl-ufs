"""
A53 SLA Ripper - Secure Level Authentication Extraction Tool
For Oppo A53 (CPH2127) Devices

This package provides tools for extracting and analyzing SLA (Secure Level 
Authentication) certificates and security data from Oppo A53 devices via EDL.
"""

__version__ = "1.0.0"
__author__ = "Anonymous Security Researcher"
__license__ = "GPLv3"

from .sla_ripper import (
    SLACertificate,
    QFPROMExtractor,
    BootPartitionAnalyzer,
    SLAReport,
    setup_logging
)

__all__ = [
    'SLACertificate',
    'QFPROMExtractor',
    'BootPartitionAnalyzer',
    'SLAReport',
    'setup_logging'
]
