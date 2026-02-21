#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A53 SLA Ripper - Secure Level Authentication Extraction Tool
Version: 1.0
Purpose: Extract and analyze SLA from Oppo A53 devices
Author: Anonymous
License: GPLv3

SLA (Secure Level Authentication) is a Qualcomm security feature that prevents
unauthorized firmware modification. This tool helps extract and analyze SLA data
from Oppo A53 (CPH2127) devices in EDL mode.
"""

import os
import sys
import json
import hashlib
import argparse
import struct
import binascii
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import subprocess
import logging

try:
    import usb.core
    import usb.util
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False

# ============================================================================
# CONSTANTS
# ============================================================================

# Device Constants
DEVICE_VID = "05C6"
DEVICE_PID = "9008"
DEVICE_MODEL = "Oppo A53 (CPH2127)"
DEVICE_SECTOR_SIZE = 4096

# SLA Signature Constants
SLA_MAGIC = b"SLA\x00"
SLA_VERSION = 1
SLA_SIZE_BYTES = 2048  # Typical SLA certificate size

# QFPROM Fuse Addresses (Qualcomm)
QFPROM_BASE = 0x780000
QFPROM_OEM_CONFIG = 0x780000
QFPROM_ANTI_ROLLBACK = 0x780100
QFPROM_SERIAL_NUM = 0x780200

# Partition Offsets
BOOT_PARTITION_START = 79366  # LUN 4
SYSTEM_PARTITION_START = 0
RECOVERY_PARTITION_START = 0

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(verbose: bool = False, logfile: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger("A53_SLA_Ripper")
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    if logfile:
        fh = logging.FileHandler(logfile)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger

logger = setup_logging()

# ============================================================================
# SLA PARSING
# ============================================================================

class SLACertificate:
    """Parse and extract SLA certificate data"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.size = len(data)
        self.magic = None
        self.version = None
        self.issuer = None
        self.subject = None
        self.serial = None
        self.signature = None
        
    def parse(self) -> bool:
        """Parse SLA certificate"""
        logger.info(f"Parsing SLA certificate ({self.size} bytes)...")
        
        try:
            # Check magic
            if len(self.data) < 4:
                logger.error("Data too small for SLA magic check")
                return False
            
            self.magic = self.data[0:4]
            if self.magic != SLA_MAGIC:
                logger.warning(f"Invalid SLA magic: {self.magic.hex()}")
                return False
            
            # Parse version
            if len(self.data) < 8:
                logger.error("Data too small for version")
                return False
            
            self.version = struct.unpack("<I", self.data[4:8])[0]
            logger.info(f"SLA Version: {self.version}")
            
            # Parse certificate components
            offset = 8
            
            # Serial number (4 bytes)
            if offset + 4 <= len(self.data):
                self.serial = struct.unpack("<I", self.data[offset:offset+4])[0]
                logger.info(f"Serial: 0x{self.serial:08x}")
                offset += 4
            
            # Extract remaining data as signature
            if offset < len(self.data):
                self.signature = self.data[offset:]
                logger.info(f"Signature size: {len(self.signature)} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"Error parsing SLA: {str(e)}")
            return False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "magic": self.magic.hex() if self.magic else None,
            "version": self.version,
            "serial": f"0x{self.serial:08x}" if self.serial else None,
            "size": self.size,
            "signature_size": len(self.signature) if self.signature else 0
        }

# ============================================================================
# FIREHOSE XML HANDLER - STANDARD PROTOCOL SUPPORT
# ============================================================================

class FirehoseXMLHandler:
    """
    Robust Firehose XML protocol handler for standard read/configure commands.
    
    Supports:
    - <read> commands for memory operations
    - <configure> commands for device configuration
    - UFS storage with 4096-byte sector size
    - Proper XML request/response parsing
    - Response validation and error detection
    """
    
    def __init__(self, usb_device=None, logger_instance=None):
        """
        Initialize Firehose XML handler.
        
        Args:
            usb_device: USB device handle (pyusb)
            logger_instance: Logger for diagnostics
        """
        self.device = usb_device
        self.logger = logger_instance or logger
        self.endpoint_in = 0x81
        self.endpoint_out = 0x01
        self.timeout_ms = 5000
        
        # UFS constants
        self.SECTOR_SIZE = 4096
        self.MAX_SECTORS_PER_READ = 512  # 2MB per request
        
    def build_read_command(self, address: int, size: int, physical: bool = True) -> str:
        """
        Build standard Firehose <read> command XML.
        
        Args:
            address: Memory address or sector number
            size: Bytes to read
            physical: True for physical address, False for sector offset
            
        Returns:
            XML command string
        """
        addr_type = "physical_address" if physical else "start_sector"
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<data>
  <read {addr_type}="0x{address:x}" num_partition_sectors="{size // self.SECTOR_SIZE}" />
</data>
'''
        return xml
    
    def build_configure_command(self, **kwargs) -> str:
        """
        Build standard Firehose <configure> command XML.
        
        Args:
            **kwargs: Configuration parameters (e.g., target_type="UFS")
            
        Returns:
            XML command string
        """
        attrs = " ".join(f'{k}="{v}"' for k, v in kwargs.items())
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<data>
  <configure {attrs} />
</data>
'''
        return xml
    
    def build_nop_command(self) -> str:
        """Build NOP (no-operation) heartbeat command."""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<data>
  <nop />
</data>
'''
        return xml
    
    def send_command(self, xml_command: str) -> Optional[bytes]:
        """
        Send Firehose XML command to device.
        
        Args:
            xml_command: XML command string
            
        Returns:
            Raw response bytes or None on error
        """
        if not self.device:
            self.logger.error("No USB device available")
            return None
        
        try:
            self.logger.debug(f"Sending Firehose command: {len(xml_command)} bytes")
            
            # Send command
            self.device.write(self.endpoint_out, xml_command.encode())
            self.logger.debug("Command sent successfully")
            
            # Read response with timeout
            try:
                response = self.device.read(self.endpoint_in, 4096, timeout=self.timeout_ms)
                self.logger.debug(f"Received response: {len(response)} bytes")
                return bytes(response)
            except Exception as read_err:
                self.logger.warning(f"Read timeout or error: {read_err}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to send Firehose command: {e}")
            return None
    
    def parse_response(self, response: bytes) -> Dict:
        """
        Parse Firehose XML response for status and data.
        
        Args:
            response: Raw response bytes from device
            
        Returns:
            Dictionary with parsed response data
        """
        try:
            response_str = response.decode('utf-8', errors='ignore')
            
            result = {
                "raw": response.hex(),
                "text": response_str,
                "status": "unknown",
                "error": None,
                "data": None
            }
            
            # Check for common response patterns
            if "ACK" in response_str:
                result["status"] = "ack"
            elif "NAK" in response_str:
                result["status"] = "nak"
                result["error"] = "Device NAK response"
            elif "ERROR" in response_str or "error" in response_str:
                result["status"] = "error"
                # Extract error message if present
                import re
                match = re.search(r'value="([^"]+)"', response_str)
                if match:
                    result["error"] = match.group(1)
            elif "<log " in response_str:
                result["status"] = "log"
            
            # Check for 0x04 error code
            if response[0:1] == b'\x04':
                result["status"] = "error_code_0x04"
                result["error"] = "Device returned error code 0x04 (Non-standard response)"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
            return {
                "raw": response.hex(),
                "status": "parse_error",
                "error": str(e)
            }


# ============================================================================
# USB ERROR RECOVERY - GRACEFUL DEGRADATION
# ============================================================================

class USBErrorRecovery:
    """
    Enhanced USB error recovery logic with graceful degradation.
    
    Handles non-standard responses, connection drops, and device errors
    without losing the entire scan or connection.
    """
    
    def __init__(self, logger_instance=None):
        """Initialize error recovery."""
        self.logger = logger_instance or logger
        self.error_threshold = 5  # Errors before shifting address
        self.error_count = 0
        self.last_error = None
        self.last_good_address = None
        self.skip_regions = []  # Regions to skip due to repeated errors
        
    def handle_error(self, address: int, error_code: int, response_data: bytes = None) -> Dict:
        """
        Handle USB/device error with recovery strategy.
        
        Args:
            address: Address where error occurred
            error_code: Error code (0x04, 0xff, etc.)
            response_data: Raw response bytes for analysis
            
        Returns:
            Recovery action dict with "action", "next_address", "skip_size"
        """
        self.error_count += 1
        self.last_error = {
            "address": address,
            "code": error_code,
            "count": self.error_count,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.warning(
            f"USB Error at 0x{address:08x}: code=0x{error_code:02x}, "
            f"consecutive_errors={self.error_count}"
        )
        
        # Recovery strategy based on error count
        if error_code == 0x04:
            # Non-standard response - skip to next 4KB boundary
            if self.error_count >= self.error_threshold:
                next_addr = ((address + 0x1000) // 0x1000) * 0x1000
                self.skip_regions.append({
                    "start": address,
                    "end": next_addr,
                    "reason": "0x04_errors"
                })
                
                self.logger.warning(
                    f"Threshold reached ({self.error_count}x). "
                    f"Skipping to 0x{next_addr:08x}"
                )
                
                return {
                    "action": "skip_to_next_block",
                    "next_address": next_addr,
                    "skip_size": 0x1000,
                    "reason": "error_code_0x04"
                }
        
        elif error_code == 0xff:
            # Timeout/device disconnect - wait and retry
            self.logger.warning("Device timeout (0xff). Waiting 2 seconds before retry...")
            time.sleep(2)
            
            if self.error_count < 3:
                return {
                    "action": "retry",
                    "next_address": address,
                    "delay_ms": 2000,
                    "reason": "timeout_recovery"
                }
        
        # Default: skip this address and continue
        if self.error_count >= 3:
            self.error_count = 0  # Reset counter
            
        return {
            "action": "skip_address",
            "next_address": address + 4,
            "skip_size": 4,
            "reason": "graceful_skip"
        }
    
    def reset_error_count(self):
        """Reset error counter on successful read."""
        if self.error_count > 0:
            self.logger.debug(f"Error recovery successful. Reset counter from {self.error_count}")
        self.error_count = 0
    
    def get_skip_report(self) -> str:
        """Generate report of skipped regions."""
        if not self.skip_regions:
            return "No regions skipped."
        
        report = "Skipped Regions:\n"
        for region in self.skip_regions:
            report += (f"  0x{region['start']:08x} - 0x{region['end']:08x} "
                      f"({region['reason']})\n")
        return report


# ============================================================================
# SLA RESPONSE LOGGER - DIAGNOSTIC DEBUGGING
# ============================================================================

class SLAResponseLogger:
    """
    SLA Response Logger for comprehensive diagnostic debugging.
    
    Logs all device responses, errors, and SLA-specific messages to help
    diagnose connection issues with authorized loaders.
    """
    
    def __init__(self, log_file: str = None):
        """
        Initialize SLA response logger.
        
        Args:
            log_file: Path to log file (default: sla_response_log.json)
        """
        self.log_file = log_file or "sla_response_log.json"
        self.responses = []
        self.sla_challenges = []
        self.loader_responses = []
        self.errors = []
        
    def log_response(self, timestamp: str, source: str, response_type: str, 
                     data: bytes, status: str = "OK") -> None:
        """
        Log a device response for diagnostics.
        
        Args:
            timestamp: ISO format timestamp
            source: Source of response (device, loader, protocol)
            response_type: Type of response (ack, nak, data, error)
            data: Raw response data
            status: Status code or message
        """
        entry = {
            "timestamp": timestamp,
            "source": source,
            "type": response_type,
            "status": status,
            "data_hex": data.hex() if isinstance(data, bytes) else data,
            "data_size": len(data) if isinstance(data, bytes) else 0,
            "data_ascii": self._safe_decode(data)
        }
        
        self.responses.append(entry)
        logger.debug(f"[{source}] {response_type}: {status}")
    
    def log_sla_challenge(self, timestamp: str, challenge_data: bytes) -> None:
        """
        Log SLA challenge received from device.
        
        Args:
            timestamp: ISO format timestamp
            challenge_data: Challenge hex data from device
        """
        entry = {
            "timestamp": timestamp,
            "challenge_hex": challenge_data.hex() if isinstance(challenge_data, bytes) else challenge_data,
            "size": len(challenge_data) if isinstance(challenge_data, bytes) else 0
        }
        
        self.sla_challenges.append(entry)
        
        # Also save to separate file for offline analysis
        challenge_file = "sla_challenge_vault.hex"
        try:
            with open(challenge_file, 'ab') as f:
                f.write(f"# {timestamp}\n".encode())
                f.write(challenge_data if isinstance(challenge_data, bytes) else challenge_data.encode())
                f.write(b"\n\n")
            logger.info(f"SLA challenge saved to {challenge_file}")
        except Exception as e:
            logger.error(f"Failed to save challenge: {e}")
    
    def log_loader_response(self, timestamp: str, loader_name: str, 
                           response: str, success: bool) -> None:
        """
        Log Firehose loader response for connection debugging.
        
        Args:
            timestamp: ISO format timestamp
            loader_name: Name of loader file
            response: Response message
            success: Whether loader loaded successfully
        """
        entry = {
            "timestamp": timestamp,
            "loader": loader_name,
            "response": response,
            "success": success
        }
        
        self.loader_responses.append(entry)
        logger.info(f"Loader [{loader_name}] result: {success}")
    
    def log_error(self, timestamp: str, error_type: str, error_msg: str, 
                  context: Dict = None) -> None:
        """
        Log protocol or connection error.
        
        Args:
            timestamp: ISO format timestamp
            error_type: Type of error (usb, protocol, timeout, etc.)
            error_msg: Error message
            context: Additional context dict
        """
        entry = {
            "timestamp": timestamp,
            "type": error_type,
            "message": error_msg,
            "context": context or {}
        }
        
        self.errors.append(entry)
        logger.error(f"[{error_type}] {error_msg}")
    
    def _safe_decode(self, data: bytes, max_length: int = 200) -> str:
        """Safely decode data to ASCII/UTF-8 for logging."""
        if not isinstance(data, bytes):
            return str(data)
        
        try:
            decoded = data[:max_length].decode('utf-8', errors='replace')
            if len(data) > max_length:
                decoded += f"... (+{len(data) - max_length} bytes)"
            return decoded
        except:
            return "[binary data]"
    
    def save_diagnostics(self) -> str:
        """
        Save comprehensive diagnostics to JSON file.
        
        Returns:
            Path to saved diagnostics file
        """
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "total_responses": len(self.responses),
            "sla_challenges_count": len(self.sla_challenges),
            "loader_responses": len(self.loader_responses),
            "errors_count": len(self.errors),
            "responses": self.responses[-100:],  # Last 100
            "sla_challenges": self.sla_challenges,
            "loader_responses": self.loader_responses,
            "errors": self.errors[-50:]  # Last 50
        }
        
        try:
            with open(self.log_file, 'w') as f:
                json.dump(diagnostics, f, indent=2)
            logger.info(f"Diagnostics saved to {self.log_file}")
            return self.log_file
        except Exception as e:
            logger.error(f"Failed to save diagnostics: {e}")
            return None
    
    def get_connection_summary(self) -> str:
        """Generate human-readable connection summary."""
        summary = f"""
SLA Response Diagnostics Summary
{'='*50}
Total Responses: {len(self.responses)}
SLA Challenges Received: {len(self.sla_challenges)}
Loader Responses: {len(self.loader_responses)}
Errors: {len(self.errors)}

Last Response: {self.responses[-1]['timestamp'] if self.responses else 'None'}
Last Error: {self.errors[-1]['type'] if self.errors else 'None'}

Loader Success Rate: {sum(1 for r in self.loader_responses if r['success']) / max(len(self.loader_responses), 1) * 100:.1f}%
"""
        return summary


# ============================================================================
# MEMORY SCANNER - QFPROM EXPLORATION TOOL
# ============================================================================

class QFPROMExtractor:
    """
    Memory Scanner for Snapdragon 460 QFPROM and Shared RAM exploration.
    
    Aggressive memory scanner with 10ms delay between 4-byte reads to prevent
    SLA (Secure Level Authentication) timeouts on Snapdragon 460 (Oppo A53).
    
    Scans memory ranges and reports only non-zero 4-byte values.
    Useful for discovering actual QFPROM data when addresses are honeypotted
    (returning all zeros).
    
    Key Features:
    - Aggressive scanning with 10ms timing protection
    - Only reports non-zero values (filters out honeypots)
    - Real-time logging to file and console
    - 4-byte aligned reads with configurable step size
    - Supports full range: 0x00700000 to 0x00800000 (512 KB)
    """
    
    # Qualcomm Firehose protocol constants
    FIREHOSE_BULK_IN_EP = 0x81
    FIREHOSE_BULK_OUT_EP = 0x01
    QUALCOMM_VID = 0x05C6
    QUALCOMM_PID = 0x9008
    
    # Memory scan constants
    PEEK_COMMAND_DELAY = 0.01  # 10ms delay between peek commands (CRITICAL for Snapdragon 460)
    DEVICE_DETECT_TIMEOUT = 5.0
    USB_READ_TIMEOUT = 5000  # milliseconds
    USB_WRITE_TIMEOUT = 5000  # milliseconds
    
    # Memory range constants
    SCAN_START_ADDR = 0x00700000  # QFPROM base and Shared RAM region
    SCAN_END_ADDR = 0x00800000    # End of scan range (512 KB span)
    DEFAULT_STEP = 4              # 4-byte aligned reads
    
    # Null pattern (honeypot detection)
    NULL_PATTERN = b'\x00\x00\x00\x00'
    
    def __init__(self, edl_binary: str = None, loader: str = None, log_file: str = None,
                 enable_diagnostics: bool = True, diagnostic_log: str = None):
        """
        Initialize Memory Scanner with optional EDL fallback and diagnostics.
        
        Args:
            edl_binary: Path to EDL binary (fallback method)
            loader: Path to Firehose loader (fallback method)
            log_file: Path to log file for scan results (default: memory_scan.log)
            enable_diagnostics: Enable SLA response logging
            diagnostic_log: Path to diagnostic log file
        """
        self.edl_binary = edl_binary
        self.loader = loader
        self.device = None
        self.use_pyusb = HAS_PYUSB
        self.log_file = log_file or "memory_scan.log"
        self.scan_results = {}  # Store results as dict: {address: hex_string}
        
        # Diagnostic tools
        self.enable_diagnostics = enable_diagnostics
        self.sla_logger = SLAResponseLogger(diagnostic_log or "sla_response_log.json") if enable_diagnostics else None
        self.error_recovery = USBErrorRecovery(logger)
        self.firehose_handler = FirehoseXMLHandler(logger_instance=logger)
        
        if self.use_pyusb:
            self._init_device()
    
    def _init_device(self) -> bool:
        """Initialize USB device connection for pyusb access"""
        if not HAS_PYUSB:
            logger.warning("pyusb not available, will use EDL binary fallback")
            return False
        
        try:
            logger.debug("Searching for Qualcomm device in EDL mode...")
            self.device = usb.core.find(find_all=False, idVendor=self.QUALCOMM_VID, 
                                       idProduct=self.QUALCOMM_PID)
            
            if self.device is None:
                logger.warning("Device not found via pyusb, will use EDL fallback")
                self.use_pyusb = False
                return False
            
            logger.info(f"Found device: {self.device.manufacturer} {self.device.product}")
            
            # Set configuration
            self.device.set_configuration()
            logger.debug("USB device configured successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to initialize pyusb device: {str(e)}")
            logger.debug("Falling back to EDL binary method")
            self.use_pyusb = False
            return False
    
    
    def _read_memory_pyusb(self, address: int) -> Optional[bytes]:
        """
        Read 4 bytes from memory using raw pyusb (Snapdragon 460 optimized).
        
        Implements proper Firehose PEEK command structure with 10ms safety delays.
        Integrates error recovery and diagnostic logging.
        
        Args:
            address: Physical memory address to read (4-byte aligned)
            
        Returns:
            4 bytes of data or None on failure
        """
        if not self.device or not self.use_pyusb:
            return None
        
        try:
            # Construct Firehose PEEK command XML
            peek_cmd = f'<?xml version="1.0" encoding="UTF-8"?><data><peek address="0x{address:08x}" size_in_bytes="4" /></data>\n'
            
            # Send peek command
            self.device.write(self.FIREHOSE_BULK_OUT_EP, peek_cmd.encode())
            
            # Apply 10ms delay (CRITICAL for Snapdragon 460 SLA)
            time.sleep(self.PEEK_COMMAND_DELAY)
            
            # Read response with timeout
            try:
                response = self.device.read(self.FIREHOSE_BULK_IN_EP, 512, timeout=self.USB_READ_TIMEOUT)
                response_bytes = bytes(response)
                
                # Log response if diagnostics enabled
                if self.enable_diagnostics and self.sla_logger:
                    self.sla_logger.log_response(
                        timestamp=datetime.now().isoformat(),
                        source="pyusb",
                        response_type="peek_response",
                        data=response_bytes[:16],  # Log first 16 bytes
                        status="OK"
                    )
                
                # Check for error codes
                if len(response_bytes) > 0 and response_bytes[0] == 0x04:
                    # Non-standard response - trigger error recovery
                    recovery_action = self.error_recovery.handle_error(
                        address, 0x04, response_bytes
                    )
                    logger.warning(f"Error code 0x04 at 0x{address:08x}: {recovery_action['reason']}")
                    
                    if self.enable_diagnostics and self.sla_logger:
                        self.sla_logger.log_error(
                            timestamp=datetime.now().isoformat(),
                            error_type="usb_error_0x04",
                            error_msg=f"Non-standard response at 0x{address:08x}",
                            context=recovery_action
                        )
                    return None
                
                # Reset error counter on successful read
                self.error_recovery.reset_error_count()
                
                # Extract 4 bytes of data
                return response_bytes[:4] if len(response_bytes) >= 4 else None
                
            except usb.core.USBTimeoutError:
                # Timeout handling
                recovery_action = self.error_recovery.handle_error(
                    address, 0xff, None
                )
                logger.warning(f"USB timeout at 0x{address:08x}")
                
                if self.enable_diagnostics and self.sla_logger:
                    self.sla_logger.log_error(
                        timestamp=datetime.now().isoformat(),
                        error_type="usb_timeout",
                        error_msg=f"Read timeout at 0x{address:08x}",
                        context=recovery_action
                    )
                return None
            
        except Exception as e:
            logger.debug(f"pyusb read failed for 0x{address:08x}: {e}")
            
            if self.enable_diagnostics and self.sla_logger:
                self.sla_logger.log_error(
                    timestamp=datetime.now().isoformat(),
                    error_type="usb_exception",
                    error_msg=str(e),
                    context={"address": f"0x{address:08x}"}
                )
            return None
    
    def _read_memory_fallback(self, address: int) -> Optional[bytes]:
        """
        Fallback method using EDL binary to read 4 bytes (with 10ms delay).
        
        Args:
            address: Physical memory address to read (4-byte aligned)
            
        Returns:
            4 bytes of data or None on failure
        """
        if not self.edl_binary or not self.loader:
            return None
        
        try:
            temp_file = f"/tmp/peek_{address:08x}.bin"
            
            # Call EDL binary: edl peek <address> 4 <output_file>
            cmd = [
                "python3", self.edl_binary,
                "peek", f"0x{address:08x}", "4", temp_file,
                f"--loader={self.loader}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            # Apply 10ms delay after EDL command
            time.sleep(self.PEEK_COMMAND_DELAY)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                with open(temp_file, 'rb') as f:
                    data = f.read(4)
                try:
                    os.remove(temp_file)
                except:
                    pass
                return data if len(data) == 4 else None
            
            return None
            
        except Exception as e:
            logger.debug(f"EDL fallback failed for 0x{address:08x}: {e}")
            return None
    
    def _read_single_address(self, address: int) -> Optional[bytes]:
        """
        Read 4 bytes from a single address with automatic fallback.
        
        Args:
            address: Physical memory address to read
            
        Returns:
            4 bytes of data or None on failure
        """
        # Try pyusb first
        if self.use_pyusb and self.device:
            data = self._read_memory_pyusb(address)
            if data is not None:
                return data
        
        # Fallback to EDL binary
        return self._read_memory_fallback(address)
    
    def scan_memory(self, start_addr: int, end_addr: int, step: int = 4) -> Dict[int, str]:
        """
        Aggressively scan memory range for non-zero 4-byte values.
        
        Scans from start_addr to end_addr with specified step size.
        Only logs and prints addresses containing non-zero data (filters honeypots).
        Applies 10ms delay between reads to prevent SLA timeouts on Snapdragon 460.
        
        Args:
            start_addr: Starting address (e.g., 0x00700000)
            end_addr: Ending address (e.g., 0x00800000)
            step: Bytes to step between reads (default 4)
            
        Returns:
            Dictionary mapping addresses to hex string values of non-zero reads
        """
        if step < 1:
            step = 4
        
        self.scan_results = {}
        scan_start_time = time.time()
        total_reads = (end_addr - start_addr) // step
        reads_completed = 0
        non_zero_count = 0
        
        logging.info("=" * 80)
        logging.info(f"MEMORY SCAN STARTED")
        logging.info(f"Range: 0x{start_addr:08x} to 0x{end_addr:08x}")
        logging.info(f"Step: {step} bytes")
        logging.info(f"Expected iterations: {total_reads:,}")
        logging.info(f"Expected time (with 10ms delays): ~{total_reads * 0.01:.1f} seconds")
        logging.info(f"Honeypot filtering: ENABLED (skipping 0x00000000 values)")
        logging.info("=" * 80)
        
        print(f"\n[*] Starting memory scan: 0x{start_addr:08x} → 0x{end_addr:08x}")
        print(f"[*] Step size: {step} bytes, Expected iterations: {total_reads:,}")
        print(f"[*] Estimated time: ~{total_reads * 0.01:.1f} seconds (with 10ms safety delays)\n")
        
        try:
            current_addr = start_addr
            
            while current_addr < end_addr:
                reads_completed += 1
                
                # Read 4 bytes at current address
                data = self._read_single_address(current_addr)
                
                if data is None or len(data) < 4:
                    # Handle short reads
                    logging.debug(f"0x{current_addr:08x}: Read failed")
                else:
                    # Check if result is non-zero (skip honeypots)
                    if data != self.NULL_PATTERN:
                        # Convert to hex string
                        hex_value = ' '.join(f'{b:02x}' for b in data)
                        
                        # Log immediately
                        log_msg = f"0x{current_addr:08x}: {hex_value}"
                        self.scan_results[current_addr] = hex_value
                        logging.info(f"[NON-ZERO] {log_msg}")
                        print(f"[+] {log_msg}")
                        
                        non_zero_count += 1
                        
                        # Save immediately to file
                        with open(self.log_file, 'a') as f:
                            f.write(f"{log_msg}\n")
                    else:
                        logging.debug(f"0x{current_addr:08x}: 0x00000000 (honeypot, skipped)")
                
                # Progress indicator every 256 reads
                if reads_completed % 256 == 0:
                    elapsed = time.time() - scan_start_time
                    pct = (reads_completed / total_reads) * 100
                    print(f"[*] Progress: {reads_completed:,}/{total_reads:,} ({pct:.1f}%) - Elapsed: {elapsed:.1f}s - Non-zero: {non_zero_count}")
                    logging.debug(f"Progress: {pct:.1f}% ({reads_completed:,}/{total_reads:,}), Non-zero found: {non_zero_count}")
                
                # Move to next address
                current_addr += step
            
            # Scan complete
            elapsed = time.time() - scan_start_time
            logging.info("=" * 80)
            logging.info(f"MEMORY SCAN COMPLETED")
            logging.info(f"Total reads: {reads_completed:,}")
            logging.info(f"Non-zero addresses: {non_zero_count}")
            logging.info(f"Elapsed time: {elapsed:.2f} seconds")
            logging.info(f"Results saved to: {self.log_file}")
            logging.info("=" * 80)
            
            print(f"\n[*] Scan complete!")
            print(f"[*] Total reads: {reads_completed:,}")
            print(f"[*] Non-zero addresses found: {non_zero_count}")
            print(f"[*] Elapsed time: {elapsed:.2f} seconds")
            print(f"[*] Results saved to: {self.log_file}\n")
            
            return self.scan_results
            
        except KeyboardInterrupt:
            logging.warning("Memory scan interrupted by user")
            print("\n[!] Scan interrupted by user")
            elapsed = time.time() - scan_start_time
            logging.info(f"Partial results: {non_zero_count} non-zero addresses in {elapsed:.2f} seconds")
            return self.scan_results
            
        except Exception as e:
            logging.error(f"Scan error: {e}")
            print(f"[!] Scan error: {e}")
            return self.scan_results
    
    def extract_oem_config(self) -> Optional[bytes]:
        """
        Extract OEM config fuses from QFPROM at 0x780000.
        
        Note: Memory Scanner mode doesn't extract; use traditional extraction for this.
        """
        logger.warning("extract_oem_config() not supported in Memory Scanner mode")
        logger.info("Tip: Use scan-memory to find actual QFPROM data at 0x00700000-0x00800000")
        return None
    
    def extract_anti_rollback(self) -> Optional[bytes]:
        """
        Extract anti-rollback version fuses from QFPROM at 0x780100.
        
        Note: Memory Scanner mode doesn't extract; use traditional extraction for this.
        """
        logger.warning("extract_anti_rollback() not supported in Memory Scanner mode")
        return None
    
    def extract_serial_number(self) -> Optional[bytes]:
        """
        Extract device serial number fuses from QFPROM at 0x780200.
        
        Note: Memory Scanner mode doesn't extract; use traditional extraction for this.
        """
        logger.warning("extract_serial_number() not supported in Memory Scanner mode")
        return None

class BootPartitionAnalyzer:
    """Analyze boot partition for SLA and security data"""
    
    def __init__(self, boot_image: bytes):
        self.boot_image = boot_image
        self.size = len(boot_image)
    
    def find_sla_signatures(self) -> List[Tuple[int, bytes]]:
        """Find SLA magic signatures in boot image"""
        logger.info("Scanning boot image for SLA signatures...")
        
        signatures = []
        magic = b"SLA\x00"
        offset = 0
        
        while True:
            pos = self.boot_image.find(magic, offset)
            if pos == -1:
                break
            
            # Extract SLA data (assume max 2KB)
            sla_data = self.boot_image[pos:pos+SLA_SIZE_BYTES]
            signatures.append((pos, sla_data))
            logger.info(f"Found SLA signature at offset 0x{pos:08x}")
            offset = pos + 4
        
        return signatures
    
    def analyze_boot_header(self) -> Optional[Dict]:
        """Analyze Android boot image header"""
        logger.info("Analyzing boot image header...")
        
        try:
            if len(self.boot_image) < 2048:
                logger.error("Boot image too small")
                return None
            
            # Android boot header constants
            BOOT_MAGIC = b"ANDROID!"
            
            if self.boot_image[0:8] != BOOT_MAGIC:
                logger.warning("Not an Android boot image")
                return None
            
            # Parse header fields
            kernel_size = struct.unpack("<I", self.boot_image[8:12])[0]
            kernel_addr = struct.unpack("<I", self.boot_image[12:16])[0]
            ramdisk_size = struct.unpack("<I", self.boot_image[16:20])[0]
            ramdisk_addr = struct.unpack("<I", self.boot_image[20:24])[0]
            second_size = struct.unpack("<I", self.boot_image[24:28])[0]
            second_addr = struct.unpack("<I", self.boot_image[28:32])[0]
            tags_addr = struct.unpack("<I", self.boot_image[32:36])[0]
            page_size = struct.unpack("<I", self.boot_image[36:40])[0]
            
            header = {
                "magic": BOOT_MAGIC.decode('ascii'),
                "kernel_size": kernel_size,
                "kernel_addr": f"0x{kernel_addr:08x}",
                "ramdisk_size": ramdisk_size,
                "ramdisk_addr": f"0x{ramdisk_addr:08x}",
                "second_size": second_size,
                "second_addr": f"0x{second_addr:08x}",
                "tags_addr": f"0x{tags_addr:08x}",
                "page_size": page_size
            }
            
            logger.info(f"Boot header parsed: page_size={page_size}, kernel_size={kernel_size}")
            return header
            
        except Exception as e:
            logger.error(f"Error analyzing boot header: {str(e)}")
            return None
    
    def extract_kernel(self, output_file: str) -> bool:
        """Extract kernel from boot image"""
        logger.info("Extracting kernel from boot image...")
        
        try:
            # Typical offset: 2048 (one page)
            kernel_start = 2048
            
            # Find kernel size from header
            if len(self.boot_image) >= 12:
                kernel_size = struct.unpack("<I", self.boot_image[8:12])[0]
                kernel_data = self.boot_image[kernel_start:kernel_start+kernel_size]
                
                with open(output_file, 'wb') as f:
                    f.write(kernel_data)
                
                logger.info(f"Kernel extracted to {output_file} ({len(kernel_data)} bytes)")
                return True
        except Exception as e:
            logger.error(f"Error extracting kernel: {str(e)}")
        
        return False
    
    def extract_ramdisk(self, output_file: str) -> bool:
        """Extract ramdisk from boot image"""
        logger.info("Extracting ramdisk from boot image...")
        
        try:
            header = self.analyze_boot_header()
            if not header:
                return False
            
            kernel_size = header["kernel_size"]
            ramdisk_size = header["ramdisk_size"]
            
            # Align to page size
            page_size = header["page_size"]
            kernel_pages = (kernel_size + page_size - 1) // page_size
            ramdisk_start = page_size + (kernel_pages * page_size)
            ramdisk_data = self.boot_image[ramdisk_start:ramdisk_start+ramdisk_size]
            
            with open(output_file, 'wb') as f:
                f.write(ramdisk_data)
            
            logger.info(f"Ramdisk extracted to {output_file} ({len(ramdisk_data)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Error extracting ramdisk: {str(e)}")
        
        return False

# ============================================================================
# REPORT GENERATION
# ============================================================================

class SLAReport:
    """Generate comprehensive SLA analysis report"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.report = {}
    
    def add_sla_data(self, sla_cert: SLACertificate):
        """Add SLA certificate data to report"""
        self.report["sla_certificate"] = sla_cert.to_dict()
    
    def add_boot_analysis(self, analysis: Dict):
        """Add boot image analysis to report"""
        self.report["boot_analysis"] = analysis
    
    def add_qfprom_data(self, qfprom_data: Dict):
        """Add QFPROM data to report"""
        self.report["qfprom"] = qfprom_data
    
    def add_checksums(self, files: Dict[str, str]):
        """Add file checksums"""
        self.report["checksums"] = files
    
    def save_json(self, filename: str = "sla_report.json"):
        """Save report as JSON"""
        output_path = os.path.join(self.output_dir, filename)
        
        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        logger.info(f"Report saved to {output_path}")
    
    def save_text(self, filename: str = "sla_report.txt"):
        """Save report as human-readable text"""
        output_path = os.path.join(self.output_dir, filename)
        
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("A53 SLA RIPPER - SECURITY ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Device: {DEVICE_MODEL}\n\n")
            
            if "sla_certificate" in self.report:
                f.write("SLA CERTIFICATE:\n")
                f.write("-" * 40 + "\n")
                for key, value in self.report["sla_certificate"].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
            
            if "boot_analysis" in self.report:
                f.write("BOOT IMAGE ANALYSIS:\n")
                f.write("-" * 40 + "\n")
                for key, value in self.report["boot_analysis"].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
            
            if "qfprom" in self.report:
                f.write("QFPROM FUSES:\n")
                f.write("-" * 40 + "\n")
                for key, value in self.report["qfprom"].items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
        
        logger.info(f"Text report saved to {output_path}")

# ============================================================================
# MAIN FUNCTIONALITY
# ============================================================================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="A53 SLA Ripper - Extract, analyze, and scan device memory"
    )
    
    parser.add_argument("action", choices=["analyze", "extract", "report", "scan-memory", 
                                          "diagnose-firehose", "diagnose-usb"],
                       help="Action to perform")
    parser.add_argument("--boot-image", help="Path to boot image file")
    parser.add_argument("--edl-binary", default="edl/edl",
                       help="Path to EDL binary (default: edl/edl)")
    parser.add_argument("--loader", default="prog_firehose_ddr_fwupdate.elf",
                       help="Path to Firehose loader")
    parser.add_argument("--output-dir", default="a53_sla_ripper/output",
                       help="Output directory for extracted data")
    parser.add_argument("--start-addr", type=lambda x: int(x, 16), default=0x00700000,
                       help="Start address for memory scan (hex, default: 0x00700000)")
    parser.add_argument("--end-addr", type=lambda x: int(x, 16), default=0x00800000,
                       help="End address for memory scan (hex, default: 0x00800000)")
    parser.add_argument("--step", type=int, default=4,
                       help="Step size for memory scan (default: 4 bytes)")
    parser.add_argument("--log-file", default="memory_scan.log",
                       help="Output file for scan results (default: memory_scan.log)")
    parser.add_argument("--diagnostic-log", default="sla_response_log.json",
                       help="Output file for diagnostic logs (default: sla_response_log.json)")
    parser.add_argument("--enable-diagnostics", action="store_true", default=True,
                       help="Enable comprehensive diagnostic logging")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    logger.info(f"A53 SLA Ripper v1.3 - Enhanced Diagnostics Edition")
    logger.info(f"Device: {DEVICE_MODEL}")
    logger.info(f"Action: {args.action}")
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Perform action
    if args.action == "scan-memory":
        """Scan memory range for non-zero values (memory scanner mode)"""
        logger.info("=" * 80)
        logger.info("MEMORY SCANNER MODE - With Enhanced Diagnostics")
        logger.info("=" * 80)
        
        scanner = QFPROMExtractor(args.edl_binary, args.loader, args.log_file,
                                 enable_diagnostics=args.enable_diagnostics,
                                 diagnostic_log=args.diagnostic_log)
        
        logger.info(f"Memory scan range: 0x{args.start_addr:08x} to 0x{args.end_addr:08x}")
        logger.info(f"Step size: {args.step} bytes")
        logger.info(f"Results will be saved to: {args.log_file}")
        logger.info(f"Diagnostics saved to: {args.diagnostic_log}")
        
        results = scanner.scan_memory(args.start_addr, args.end_addr, args.step)
        
        logger.info(f"Scan complete. Found {len(results)} non-zero addresses.")
        logger.info(f"Results saved to: {args.log_file}")
        
        # Save diagnostics
        if scanner.enable_diagnostics and scanner.sla_logger:
            diag_file = scanner.sla_logger.save_diagnostics()
            logger.info(f"Full diagnostics saved to: {diag_file}")
            print(scanner.sla_logger.get_connection_summary())
        
        # Print error recovery report
        logger.info(scanner.error_recovery.get_skip_report())
        
        return 0
    
    elif args.action == "diagnose-firehose":
        """Diagnose Firehose connection and protocol issues"""
        logger.info("=" * 80)
        logger.info("FIREHOSE PROTOCOL DIAGNOSTICS")
        logger.info("=" * 80)
        
        scanner = QFPROMExtractor(args.edl_binary, args.loader,
                                 enable_diagnostics=True,
                                 diagnostic_log=args.diagnostic_log)
        
        logger.info("Testing Firehose protocol with standard <read> command...")
        
        # Build and send a test read command
        firehose = scanner.firehose_handler
        
        # Test 1: NOP heartbeat
        logger.info("Test 1: Sending NOP heartbeat...")
        nop_cmd = firehose.build_nop_command()
        response = firehose.send_command(nop_cmd)
        if response:
            logger.info(f"NOP Response: {response[:50].hex()}...")
            scanner.sla_logger.log_response(
                timestamp=datetime.now().isoformat(),
                source="firehose",
                response_type="nop_heartbeat",
                data=response,
                status="OK"
            )
        else:
            logger.warning("NOP heartbeat failed")
            scanner.sla_logger.log_error(
                timestamp=datetime.now().isoformat(),
                error_type="firehose_nop",
                error_msg="Failed to send NOP heartbeat"
            )
        
        # Test 2: Configure command
        logger.info("Test 2: Sending configure command...")
        config_cmd = firehose.build_configure_command(
            target_type="UFS",
            sector_size="4096"
        )
        response = firehose.send_command(config_cmd)
        if response:
            parsed = firehose.parse_response(response)
            logger.info(f"Configure Response Status: {parsed['status']}")
            if parsed['error']:
                logger.warning(f"Error: {parsed['error']}")
        
        # Save diagnostics
        logger.info("Saving diagnostics...")
        diag_file = scanner.sla_logger.save_diagnostics()
        logger.info(f"Diagnostics saved to: {diag_file}")
        print(scanner.sla_logger.get_connection_summary())
        
        return 0
    
    elif args.action == "diagnose-usb":
        """Diagnose USB error recovery and resilience"""
        logger.info("=" * 80)
        logger.info("USB ERROR RECOVERY DIAGNOSTICS")
        logger.info("=" * 80)
        
        recovery = USBErrorRecovery(logger)
        
        # Simulate error scenarios
        logger.info("Simulating USB error scenarios...")
        
        # Test 1: 0x04 error (non-standard response)
        logger.info("Test 1: 0x04 error code handling...")
        for i in range(5):
            action = recovery.handle_error(0x00701000 + i * 4, 0x04)
            logger.info(f"  Attempt {i+1}: {action['action']}")
        
        logger.info("\nRecovery Actions Summary:")
        print(recovery.get_skip_report())
        
        return 0
    
    # Initialize report
    report = SLAReport(args.output_dir)
    
    # Perform action
    if args.action == "analyze":
        if not args.boot_image:
            logger.error("--boot-image required for analyze action")
            return 1
        
        if not os.path.exists(args.boot_image):
            logger.error(f"Boot image not found: {args.boot_image}")
            return 1
        
        with open(args.boot_image, 'rb') as f:
            boot_data = f.read()
        
        analyzer = BootPartitionAnalyzer(boot_data)
        boot_analysis = analyzer.analyze_boot_header()
        
        if boot_analysis:
            report.add_boot_analysis(boot_analysis)
            
            # Extract kernel and ramdisk
            kernel_file = os.path.join(args.output_dir, "kernel")
            ramdisk_file = os.path.join(args.output_dir, "ramdisk.gz")
            
            analyzer.extract_kernel(kernel_file)
            analyzer.extract_ramdisk(ramdisk_file)
        
        # Find SLA signatures
        sla_sigs = analyzer.find_sla_signatures()
        logger.info(f"Found {len(sla_sigs)} SLA signature(s)")
        
        if sla_sigs:
            for idx, (offset, sla_data) in enumerate(sla_sigs):
                sla_file = os.path.join(args.output_dir, f"sla_{idx}.bin")
                with open(sla_file, 'wb') as f:
                    f.write(sla_data)
                
                sla_cert = SLACertificate(sla_data)
                if sla_cert.parse():
                    report.add_sla_data(sla_cert)
    
    elif args.action == "extract":
        # Extract QFPROM data
        extractor = QFPROMExtractor(args.edl_binary, args.loader)
        
        qfprom_data = {}
        
        oem_config = extractor.extract_oem_config()
        if oem_config:
            oem_file = os.path.join(args.output_dir, "qfprom_oem_config.bin")
            with open(oem_file, 'wb') as f:
                f.write(oem_config)
            qfprom_data["oem_config"] = oem_file
        
        anti_rb = extractor.extract_anti_rollback()
        if anti_rb:
            anti_file = os.path.join(args.output_dir, "qfprom_anti_rollback.bin")
            with open(anti_file, 'wb') as f:
                f.write(anti_rb)
            qfprom_data["anti_rollback"] = anti_file
        
        serial = extractor.extract_serial_number()
        if serial:
            serial_file = os.path.join(args.output_dir, "qfprom_serial.bin")
            with open(serial_file, 'wb') as f:
                f.write(serial)
            qfprom_data["serial_number"] = serial_file
        
        report.add_qfprom_data(qfprom_data)
    
    # Generate report
    report.save_json()
    report.save_text()
    
    logger.info(f"SLA analysis complete. Results saved to {args.output_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
