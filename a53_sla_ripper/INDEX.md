# A53 SLA Ripper - Component Index

## Overview

A53 SLA Ripper is a complete toolkit for extracting and analyzing Secure Level Authentication (SLA) certificates and security data from Oppo A53 devices via EDL mode.

**Total Components:** 10 files  
**Total Lines of Code:** 2000+  
**Supported Device:** Oppo A53 (CPH2127)  
**License:** GPLv3

## Directory Structure

```
a53_sla_ripper/
├── README.md                   (14 KB) - Complete documentation
├── SETUP.md                    (5 KB)  - Quick setup guide
├── INDEX.md                    (this file)
├── __init__.py                 (601 B) - Python package initializer
├── requirements.txt            (216 B) - Python dependencies
│
├── sla_ripper.py              (19 KB) - Main Python extraction tool
│   ├── SLACertificate         - Parse SLA certificates
│   ├── QFPROMExtractor        - Extract QFPROM fuses
│   ├── BootPartitionAnalyzer  - Analyze boot images
│   └── SLAReport              - Generate reports
│
├── sla_ripper.sh              (14 KB) - Main Bash control script
│   ├── detect                 - Detect device in EDL mode
│   ├── extract-boot           - Extract boot image
│   ├── analyze-boot           - Analyze boot for SLA
│   ├── extract-sla            - Extract SLA/QFPROM data
│   ├── analyze-sigs           - Find SLA signatures
│   ├── dump-security          - Generate security report
│   └── full-analysis          - Complete workflow
│
├── device_recovery.sh         (2 KB)  - Device recovery tool
├── verify_hashes.sh           (3 KB)  - Hash verification utility
└── generate_report.sh         (12 KB) - Report generation tool
```

## Component Descriptions

### Documentation Files

#### README.md (14 KB)
**Purpose:** Comprehensive project documentation

**Contents:**
- Feature overview
- Device specifications
- Installation instructions
- Usage examples (CLI and Python API)
- Output file documentation
- Understanding SLA certificates
- Understanding QFPROM fuses
- Boot image components
- Security analysis examples
- Troubleshooting guide
- Technical details
- Performance metrics
- Legal and ethical considerations
- Contributing guidelines
- References

**When to Use:** First-time setup, learning about SLA/QFPROM, troubleshooting

**Commands:**
```bash
less README.md                    # Read interactively
grep "keyword" README.md          # Search for topic
head -100 README.md              # View first 100 lines
```

#### SETUP.md (5 KB)
**Purpose:** Quick start guide for setup and first-time use

**Contents:**
- Dependency installation (Ubuntu, CentOS, macOS)
- Python requirements installation
- Script executable setup
- Installation verification
- Device EDL mode entry
- Quick test
- Full workflow steps
- File locations
- Troubleshooting quick reference
- Next steps

**When to Use:** Initial setup, first extraction attempt, quick reference

**Commands:**
```bash
cat SETUP.md                      # View entire guide
less SETUP.md                     # Interactive viewing
grep "USB" SETUP.md              # Find USB-related info
```

#### INDEX.md (this file)
**Purpose:** Component index and quick reference

**Contents:**
- Component overview
- File locations and sizes
- Component descriptions
- Function specifications
- Usage examples
- Integration guide
- Workflow examples

**When to Use:** Finding specific tools, understanding architecture, integration planning

### Python Components

#### sla_ripper.py (19 KB, ~500 lines)
**Purpose:** Main Python extraction and analysis engine

**Classes:**

1. **SLACertificate**
   ```python
   sla = SLACertificate(sla_data: bytes)
   sla.parse() -> bool
   sla.to_dict() -> Dict
   ```
   - Parses SLA certificate binary data
   - Extracts magic, version, serial, signature
   - Exports to JSON-compatible dictionary

2. **QFPROMExtractor**
   ```python
   extractor = QFPROMExtractor(edl_binary: str, loader: str)
   extractor.read_memory(address: int, size: int) -> bytes
   extractor.extract_oem_config() -> bytes
   extractor.extract_anti_rollback() -> bytes
   extractor.extract_serial_number() -> bytes
   ```
   - Reads QFPROM memory from device
   - Extracts OEM config, anti-rollback, serial fuses
   - Uses EDL peek command for memory access

3. **BootPartitionAnalyzer**
   ```python
   analyzer = BootPartitionAnalyzer(boot_image: bytes)
   analyzer.analyze_boot_header() -> Dict
   analyzer.find_sla_signatures() -> List[Tuple[int, bytes]]
   analyzer.extract_kernel(output_file: str) -> bool
   analyzer.extract_ramdisk(output_file: str) -> bool
   ```
   - Parses Android boot image headers
   - Finds SLA signatures in boot data
   - Extracts kernel and ramdisk components

4. **SLAReport**
   ```python
   report = SLAReport(output_dir: str)
   report.add_sla_data(sla_cert: SLACertificate)
   report.add_boot_analysis(analysis: Dict)
   report.add_qfprom_data(qfprom_data: Dict)
   report.save_json(filename: str)
   report.save_text(filename: str)
   ```
   - Generates comprehensive analysis reports
   - Exports to JSON and human-readable text
   - Combines all extraction data

**Functions:**

- `setup_logging(verbose, logfile)` - Configure logging
- `main()` - CLI entry point

**Usage:**
```bash
# Command-line interface
python3 sla_ripper.py analyze --boot-image=boot.img --output-dir=output
python3 sla_ripper.py extract --edl-binary=edl/edl --loader=loader.elf
python3 sla_ripper.py report

# Python API
from a53_sla_ripper import SLACertificate, BootPartitionAnalyzer
sla = SLACertificate(data)
sla.parse()
print(sla.to_dict())
```

### Bash Components

#### sla_ripper.sh (14 KB, ~350 lines)
**Purpose:** Main bash control script and workflow manager

**Commands:**

| Command | Purpose | Time | Notes |
|---------|---------|------|-------|
| `detect` | Detect device in EDL mode | <1s | Requires USB connection |
| `extract-boot` | Extract 98 MB boot image | 10-20 min | Long operation |
| `analyze-boot` | Parse boot and find SLA | <1 min | After extract-boot |
| `extract-sla` | Extract SLA/QFPROM data | 2-5 min | Requires Firehose |
| `analyze-sigs` | Find SLA signatures | <1 min | Scans all images |
| `dump-security` | Generate security report | <1 min | Summary output |
| `full-analysis` | Complete workflow | 20-30 min | All operations |
| `help` | Show help message | <1s | Usage guide |

**Functions:**

- `check_dependencies()` - Verify Python, lsusb, EDL
- `detect_device()` - Detect 05C6:9008 device
- `find_loader()` - Locate Firehose loader
- `calculate_file_hash(file, algo)` - MD5/SHA1/SHA256
- `extract_boot_image(output_file)` - Boot partition read
- `analyze_boot_image(boot_image)` - Parse and extract
- `extract_sla_from_device()` - QFPROM extraction
- `generate_report()` - Report generation
- `analyze_sla_signatures()` - Signature scanning
- `dump_security_info()` - Security summary

**Usage:**
```bash
# Basic commands
./sla_ripper.sh detect
./sla_ripper.sh extract-boot
./sla_ripper.sh analyze-boot

# With options
./sla_ripper.sh extract-boot --output-dir=~/backups
./sla_ripper.sh analyze-boot --boot-image=boot.img

# Complete workflow
./sla_ripper.sh full-analysis
```

#### device_recovery.sh (2 KB, ~60 lines)
**Purpose:** Device recovery from stuck EDL state

**Functionality:**
- Device detection check
- Loader verification
- Device reboot via reset command
- Status monitoring
- Recovery instructions

**Usage:**
```bash
./device_recovery.sh
# Device will reboot and return to normal mode
```

**When to Use:**
- Device stuck in EDL mode
- Need to restart device cleanly
- Exiting EDL without risking corruption

#### verify_hashes.sh (3 KB, ~100 lines)
**Purpose:** Verify integrity of extracted files

**Functionality:**
- Boot image SHA256 verification
- Kernel hash calculation
- Ramdisk hash calculation
- SLA certificate hashing
- QFPROM file hashing
- Summary report generation

**Usage:**
```bash
./verify_hashes.sh
# Outputs: Verified count, Failed count, Hash details
```

**Output:**
```
Verified: 4 files
Failed:   0 files
SLA:      1 certificate
QFPROM:   3 files
[+] All verifications passed!
```

#### generate_report.sh (12 KB, ~350 lines)
**Purpose:** Generate detailed technical analysis report

**Report Sections:**
- Device Information
- Boot Image Analysis
- SLA Certificate Analysis
- QFPROM Fuse Analysis
- File Inventory
- File Integrity Hashes
- Security Assessment
- Recommendations
- Technical Notes

**Usage:**
```bash
./generate_report.sh
# Creates: detailed_analysis_report.txt
```

**Output File:**
- Location: `output/detailed_analysis_report.txt`
- Size: ~2-5 KB
- Format: Plain text with ASCII art

### Configuration Files

#### __init__.py (601 B)
**Purpose:** Python package initialization

**Exports:**
```python
from a53_sla_ripper import (
    SLACertificate,
    QFPROMExtractor,
    BootPartitionAnalyzer,
    SLAReport,
    setup_logging
)
```

**Usage:**
```bash
# As a package
pip install -e a53_sla_ripper/

# Import in Python
from a53_sla_ripper import SLACertificate
```

#### requirements.txt (216 B)
**Purpose:** Python package dependencies

**Dependencies:**
```
pyusb>=1.2.1              # USB communication
pycryptodome>=3.15.0      # RSA signature verification (optional)
construct>=2.10.67        # Binary parsing (optional)
```

**Installation:**
```bash
pip3 install -r requirements.txt
```

## Integration Examples

### Using as Standalone Tools

```bash
# Device detection
./sla_ripper.sh detect

# Boot extraction
./sla_ripper.sh extract-boot

# Analysis
./sla_ripper.sh analyze-boot
./sla_ripper.sh generate_report.sh

# Verification
./verify_hashes.sh

# Recovery
./device_recovery.sh
```

### Using Python API

```python
#!/usr/bin/env python3
from a53_sla_ripper import (
    SLACertificate, BootPartitionAnalyzer, SLAReport
)

# Load boot image
with open('boot.img', 'rb') as f:
    boot_data = f.read()

# Analyze
analyzer = BootPartitionAnalyzer(boot_data)
header = analyzer.analyze_boot_header()
sla_sigs = analyzer.find_sla_signatures()

# Extract components
analyzer.extract_kernel('kernel')
analyzer.extract_ramdisk('ramdisk.gz')

# Generate report
report = SLAReport('output')
for offset, sla_data in sla_sigs:
    sla = SLACertificate(sla_data)
    sla.parse()
    report.add_sla_data(sla)

report.add_boot_analysis(header)
report.save_json()
report.save_text()
```

### Complete Workflow

```bash
#!/bin/bash
set -e

cd a53_sla_ripper

echo "[1/5] Detecting device..."
./sla_ripper.sh detect

echo "[2/5] Extracting boot image (10-20 min)..."
./sla_ripper.sh extract-boot

echo "[3/5] Analyzing boot image..."
./sla_ripper.sh analyze-boot

echo "[4/5] Generating reports..."
./generate_report.sh
./verify_hashes.sh

echo "[5/5] Extracting SLA/QFPROM (if supported)..."
./sla_ripper.sh extract-sla || echo "Note: QFPROM extraction may timeout"

echo "Complete!"
cat output/sla_report.txt
```

## File I/O Summary

### Input Files
- Boot image binary (98 MB)
- Loader .elf files
- EDL binary

### Output Files (in `output/` directory)
- `sla_report.json` - Analysis results
- `sla_report.txt` - Readable report
- `security_info.txt` - Security summary
- `detailed_analysis_report.txt` - Detailed analysis
- `boot.img` - Extracted boot partition
- `kernel` - Extracted kernel
- `ramdisk.gz` - Extracted ramdisk
- `sla_*.bin` - SLA certificates
- `qfprom_*.bin` - QFPROM data
- `sla_ripper.log` - Operation log

### Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Device detection | <1 sec | USB only |
| Boot extraction | 10-20 min | Depends on USB speed |
| Boot analysis | <1 sec | CPU intensive |
| SLA search | <1 sec | Pattern matching |
| Hash calculation | 5-10 sec | All algorithms |
| QFPROM read | 30-60 sec | May timeout |
| Report generation | <1 sec | File I/O |

## Troubleshooting Matrix

| Problem | Tool | Solution |
|---------|------|----------|
| Device not detected | `detect` | Check EDL mode, USB port |
| Timeout during boot extract | `extract-boot` | Use USB 3.0, shorter cable |
| Missing SLA signatures | `analyze-sigs` | Check boot image validity |
| Hash mismatch | `verify_hashes.sh` | Re-extract boot |
| Stuck in EDL mode | `device_recovery.sh` | Run recovery script |

## Development Notes

### Code Quality
- **Python:** Type hints, docstrings, error handling
- **Bash:** POSIX compliant, error handling, logging
- **Comments:** Inline documentation and examples
- **Modularity:** Reusable components, clear separation

### Testing Recommendations
1. Device detection: `./sla_ripper.sh detect`
2. Dependency check: Check in help output
3. Boot extraction: First-time extraction
4. Analysis: Process extracted files
5. Hash verification: Integrity checking
6. Report generation: Output validation

### Known Limitations
- Firehose configure timeout (hardware)
- Full device backup impossible
- QFPROM reads may fail
- Requires Linux/macOS (not Windows)

## Version Information

**Current Version:** 1.0  
**Release Date:** 2026-02-19  
**Status:** Stable  
**Python Version:** 3.7+  
**Bash Version:** 4.0+

## Support Resources

1. **Documentation:** README.md (comprehensive)
2. **Setup Guide:** SETUP.md (quick reference)
3. **This Index:** INDEX.md (component reference)
4. **Code Comments:** Inline documentation
5. **Logs:** output/sla_ripper.log (operation details)

## License

All components licensed under **GNU General Public License v3.0**

---

**Last Updated:** 2026-02-19  
**Maintainer:** Anonymous Security Researcher
