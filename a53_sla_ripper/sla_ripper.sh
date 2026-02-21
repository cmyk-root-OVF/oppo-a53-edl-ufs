#!/bin/bash
################################################################################
# A53 SLA Ripper - Bash Control Script
# Version: 1.0
# Purpose: Automated SLA extraction and analysis for Oppo A53
# License: GPLv3
################################################################################

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="${SCRIPT_DIR}/sla_ripper.py"

OUTPUT_DIR="${SCRIPT_DIR}/output"
LOG_FILE="${OUTPUT_DIR}/sla_ripper.log"

EDL_BINARY="${PROJECT_ROOT}/edl/edl"
LOADER_DIR="${PROJECT_ROOT}/Loaders"
DEFAULT_LOADER="prog_firehose_ddr_fwupdate.elf"

# Device constants
DEVICE_VID="05C6"
DEVICE_PID="9008"
DEVICE_MODEL="Oppo A53 (CPH2127)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING
# ============================================================================

mkdir -p "$OUTPUT_DIR"

log() {
    local level="$1"
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "$@"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $@" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $@" | tee -a "$LOG_FILE"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $@" | tee -a "$LOG_FILE"; }
log_debug() { [[ "${VERBOSE:-0}" == "1" ]] && log "DEBUG" "$@"; }

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

check_dependencies() {
    log_info "Checking dependencies..."
    
    local missing=0
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found"
        missing=1
    fi
    
    if ! command -v lsusb &> /dev/null; then
        log_warn "lsusb not found - USB detection may fail"
    fi
    
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        log_error "Python script not found: $PYTHON_SCRIPT"
        missing=1
    fi
    
    if [[ ! -f "$EDL_BINARY" ]]; then
        log_error "EDL binary not found: $EDL_BINARY"
        missing=1
    fi
    
    if [[ $missing -eq 1 ]]; then
        return 1
    fi
    
    log_success "All dependencies found"
    return 0
}

detect_device() {
    log_info "Detecting Oppo A53 device..."
    
    if lsusb -d "$DEVICE_VID:$DEVICE_PID" &> /dev/null; then
        log_success "Device detected: $DEVICE_MODEL (VID:$DEVICE_VID PID:$DEVICE_PID)"
        return 0
    else
        log_error "Device not detected in EDL mode"
        log_info "Ensure device is connected in EDL mode (Sahara protocol)"
        return 1
    fi
}

find_loader() {
    log_info "Finding Firehose loader..."
    
    if [[ -f "$1" ]]; then
        log_success "Loader found: $1"
        echo "$1"
        return 0
    fi
    
    # Search in Loaders directory
    if [[ -d "$LOADER_DIR" ]]; then
        local loader_paths=(
            "$LOADER_DIR/qualcomm/patched/$DEFAULT_LOADER"
            "$LOADER_DIR/qualcomm/$DEFAULT_LOADER"
            "$(find "$LOADER_DIR" -name "$DEFAULT_LOADER" -type f | head -1)"
        )
        
        for loader in "${loader_paths[@]}"; do
            if [[ -f "$loader" ]]; then
                log_success "Loader found: $loader"
                echo "$loader"
                return 0
            fi
        done
    fi
    
    log_error "Loader not found: $DEFAULT_LOADER"
    return 1
}

calculate_file_hash() {
    local file="$1"
    local algo="${2:-sha256}"
    
    if [[ ! -f "$file" ]]; then
        log_error "File not found: $file"
        return 1
    fi
    
    case "$algo" in
        md5)
            md5sum "$file" | awk '{print $1}'
            ;;
        sha1)
            sha1sum "$file" | awk '{print $1}'
            ;;
        sha256)
            sha256sum "$file" | awk '{print $1}'
            ;;
        *)
            log_error "Unknown hash algorithm: $algo"
            return 1
            ;;
    esac
}

# ============================================================================
# SLA EXTRACTION FUNCTIONS
# ============================================================================

extract_boot_image() {
    local output_file="${1:-${OUTPUT_DIR}/boot.img}"
    
    log_info "Extracting boot image from device..."
    log_info "  Sector: 79366 (LUN 4)"
    log_info "  Size: 24576 sectors (98 MB @ 4096 bytes/sector)"
    log_info "  Output: $output_file"
    
    if ! detect_device; then
        return 1
    fi
    
    local loader
    loader=$(find_loader "$EDL_BINARY" "$LOADER_DIR/$DEFAULT_LOADER") || return 1
    
    python3 "$EDL_BINARY" \
        rs 79366 24576 "$output_file" \
        --loader="$loader" \
        --memory=ufs \
        --lun=4 \
        --sectorsize=4096 \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ -f "$output_file" ]]; then
        local size=$(stat -c%s "$output_file")
        log_success "Boot image extracted: $output_file ($size bytes)"
        
        # Calculate hash
        local hash=$(calculate_file_hash "$output_file" sha256)
        log_info "SHA256: $hash"
        echo "$hash" > "${output_file}.sha256"
        
        return 0
    else
        log_error "Failed to extract boot image"
        return 1
    fi
}

analyze_boot_image() {
    local boot_image="$1"
    
    if [[ ! -f "$boot_image" ]]; then
        log_error "Boot image not found: $boot_image"
        return 1
    fi
    
    log_info "Analyzing boot image: $boot_image"
    
    python3 "$PYTHON_SCRIPT" analyze \
        --boot-image="$boot_image" \
        --output-dir="$OUTPUT_DIR" \
        --verbose \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ $? -eq 0 ]]; then
        log_success "Boot image analysis complete"
        return 0
    else
        log_error "Boot image analysis failed"
        return 1
    fi
}

extract_sla_from_device() {
    log_info "Extracting SLA data from device..."
    log_info "Attempting QFPROM memory reads..."
    
    if ! detect_device; then
        return 1
    fi
    
    local loader
    loader=$(find_loader "$EDL_BINARY" "$LOADER_DIR/$DEFAULT_LOADER") || return 1
    
    python3 "$PYTHON_SCRIPT" extract \
        --edl-binary="$EDL_BINARY" \
        --loader="$loader" \
        --output-dir="$OUTPUT_DIR" \
        --verbose \
        2>&1 | tee -a "$LOG_FILE"
    
    if [[ $? -eq 0 ]]; then
        log_success "SLA extraction complete"
        return 0
    else
        log_error "SLA extraction failed"
        return 1
    fi
}

generate_report() {
    log_info "Generating SLA analysis report..."
    
    local json_report="${OUTPUT_DIR}/sla_report.json"
    local text_report="${OUTPUT_DIR}/sla_report.txt"
    
    if [[ -f "$json_report" ]]; then
        log_success "JSON report: $json_report"
    fi
    
    if [[ -f "$text_report" ]]; then
        log_success "Text report: $text_report"
        log_info "Report content:"
        echo "---" | tee -a "$LOG_FILE"
        head -100 "$text_report" | tee -a "$LOG_FILE"
        echo "---" | tee -a "$LOG_FILE"
    fi
}

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

analyze_sla_signatures() {
    log_info "Analyzing SLA signatures in all available images..."
    
    local found_sigs=0
    
    # Check extracted boot image
    if [[ -f "${OUTPUT_DIR}/boot.img" ]]; then
        log_info "Scanning boot.img for SLA signatures..."
        
        # Search for SLA magic (0x414c53 = "SLA")
        xxd -c 16 "${OUTPUT_DIR}/boot.img" | grep -i "534c 4100" || true
        
        found_sigs=$((found_sigs + $(xxd "${OUTPUT_DIR}/boot.img" | grep -c "534c 4100" || true)))
    fi
    
    # Check for extracted SLA files
    for sla_file in "${OUTPUT_DIR}"/sla_*.bin; do
        if [[ -f "$sla_file" ]]; then
            log_info "Analyzing $sla_file..."
            xxd -l 256 "$sla_file" | tee -a "$LOG_FILE"
            found_sigs=$((found_sigs + 1))
        fi
    done
    
    if [[ $found_sigs -gt 0 ]]; then
        log_success "Found $found_sigs SLA signature(s)"
    else
        log_warn "No SLA signatures found"
    fi
}

dump_security_info() {
    log_info "Dumping device security information..."
    
    local security_info="${OUTPUT_DIR}/security_info.txt"
    
    {
        echo "========================================"
        echo "OPPO A53 SECURITY INFORMATION"
        echo "========================================"
        echo "Generated: $(date)"
        echo ""
        echo "Device Model: $DEVICE_MODEL"
        echo "USB VID: 0x$DEVICE_VID"
        echo "USB PID: 0x$DEVICE_PID"
        echo ""
        echo "SLA Certificate:"
        if [[ -f "${OUTPUT_DIR}/sla_report.json" ]]; then
            python3 -m json.tool "${OUTPUT_DIR}/sla_report.json" | head -50
        else
            echo "  Not extracted yet"
        fi
        echo ""
        echo "QFPROM Fuses:"
        if [[ -f "${OUTPUT_DIR}/qfprom_oem_config.bin" ]]; then
            echo "  OEM Config: $(stat -c%s "${OUTPUT_DIR}/qfprom_oem_config.bin") bytes"
        fi
        if [[ -f "${OUTPUT_DIR}/qfprom_anti_rollback.bin" ]]; then
            echo "  Anti-Rollback: $(stat -c%s "${OUTPUT_DIR}/qfprom_anti_rollback.bin") bytes"
        fi
        if [[ -f "${OUTPUT_DIR}/qfprom_serial.bin" ]]; then
            echo "  Serial Number: $(stat -c%s "${OUTPUT_DIR}/qfprom_serial.bin") bytes"
        fi
        echo ""
        echo "Files in output directory:"
        ls -lah "$OUTPUT_DIR" | tail -20
    } | tee "$security_info"
    
    log_success "Security info saved to $security_info"
}

# ============================================================================
# HELP AND USAGE
# ============================================================================

show_usage() {
    cat << 'EOF'

           A53 SLA Ripper v1.0 - SLA Extraction & Analysis Tool
                    For Oppo A53 (CPH2127) Devices


USAGE:
  ./sla_ripper.sh [COMMAND] [OPTIONS]

COMMANDS:
  detect              Detect Oppo A53 in EDL mode
  extract-boot        Extract boot image from device (LUN 4, sector 79366)
  analyze-boot        Analyze extracted boot image for SLA signatures
  extract-sla         Extract SLA and QFPROM data from device
  analyze-sigs        Scan images for SLA magic signatures
  dump-security       Generate security information report
  full-analysis       Perform complete extraction and analysis workflow
  help                Show this help message

OPTIONS:
  --output-dir DIR    Set output directory (default: ./output)
  --loader LOADER     Specify Firehose loader path
  --boot-image FILE   Boot image file for analysis
  --verbose           Enable verbose output
  --log-file FILE     Log file path (default: ./output/sla_ripper.log)

EXAMPLES:
  # Detect device in EDL mode
  ./sla_ripper.sh detect

  # Extract boot image from device
  ./sla_ripper.sh extract-boot

  # Analyze boot image for SLA signatures
  ./sla_ripper.sh analyze-boot --boot-image boot.img

  # Extract SLA and QFPROM data
  ./sla_ripper.sh extract-sla

  # Perform complete analysis workflow
  ./sla_ripper.sh full-analysis

  # View security information
  ./sla_ripper.sh dump-security

OUTPUT FILES:
  sla_report.json          SLA analysis in JSON format
  sla_report.txt           Human-readable SLA analysis
  security_info.txt        Device security information
  boot.img                 Extracted boot partition (98MB)
  kernel                   Extracted kernel binary
  ramdisk.gz              Extracted ramdisk
  sla_*.bin               Individual SLA certificates found
  qfprom_*.bin            QFPROM fuse data
  sla_ripper.log          Detailed operation log

KNOWN LIMITATIONS:
  - Firehose configure command may timeout on some devices
  - Complete device backup impossible (configure timeout)
  - SLA extraction requires Firehose protocol support
  - QFPROM access may require device firmware updates

EOF
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    local command="${1:-help}"
    
    log_info "A53 SLA Ripper v1.0 started"
    
    # Check dependencies first
    if ! check_dependencies; then
        log_error "Dependency check failed"
        return 1
    fi
    
    case "$command" in
        detect)
            detect_device
            ;;
        extract-boot)
            extract_boot_image "${2:-${OUTPUT_DIR}/boot.img}"
            ;;
        analyze-boot)
            local boot_img="${2:-${OUTPUT_DIR}/boot.img}"
            analyze_boot_image "$boot_img"
            generate_report
            ;;
        extract-sla)
            extract_sla_from_device
            generate_report
            ;;
        analyze-sigs)
            analyze_sla_signatures
            ;;
        dump-security)
            dump_security_info
            ;;
        full-analysis)
            log_info "Starting full SLA analysis workflow..."
            detect_device && \
            extract_boot_image && \
            analyze_boot_image "${OUTPUT_DIR}/boot.img" && \
            extract_sla_from_device && \
            analyze_sla_signatures && \
            dump_security_info && \
            log_success "Full analysis complete!"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            return 1
            ;;
    esac
    
    log_info "A53 SLA Ripper finished"
}

# Run main function
main "$@"
