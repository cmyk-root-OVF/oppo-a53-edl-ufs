#!/bin/bash

################################################################################
# EDL Control Framework - Oppo A53 UFS Device Management
# Version: 1.0
# Purpose: Automated control and management of EDL (Emergency Download) operations
# Author: Anonymous
# License: GPLv3
################################################################################

set -euo pipefail

# ============================================================================
# CONFIGURATION VARIABLES
# ============================================================================

# Device Configuration
DEVICE_VID="05C6"
DEVICE_PID="9008"
DEVICE_MODEL="Oppo A53 (CPH2127)"
DEVICE_STORAGE="UFS"
DEVICE_SECTOR_SIZE=4096

# EDL Tool Paths
EDL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/edl"
EDL_BINARY="${EDL_ROOT}/edl"
EDL_LOADER="prog_firehose_ddr_fwupdate.elf"
EDL_LOADER_PATH="${EDL_ROOT}/../${EDL_LOADER}"

# Device Parameters
DEVICE_LUN=4
BOOT_SECTOR=79366
BOOT_SECTORS=24576
BOOT_SIZE=$((BOOT_SECTORS * DEVICE_SECTOR_SIZE))

# Output Paths
OUTPUT_DIR="${HOME}/edl_dumps"
LOG_DIR="${OUTPUT_DIR}/logs"
BACKUP_DIR="${OUTPUT_DIR}/backups"

# Timeouts (seconds)
DEVICE_TIMEOUT=30
USB_TIMEOUT=60
FIREHOSE_TIMEOUT=120

# Logging
LOG_FILE="${LOG_DIR}/edl-control.log"
DEBUG_MODE=0
VERBOSE_MODE=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[${timestamp}] [${level}] ${message}" >> "${LOG_FILE}"
    
    case "${level}" in
        INFO)
            echo -e "${BLUE}[INFO]${NC} ${message}"
            ;;
        WARN)
            echo -e "${YELLOW}[WARN]${NC} ${message}"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} ${message}"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} ${message}"
            ;;
        DEBUG)
            if [ "${DEBUG_MODE}" -eq 1 ]; then
                echo -e "${BLUE}[DEBUG]${NC} ${message}"
            fi
            ;;
        *)
            echo -e "${message}"
            ;;
    esac
}

debug() {
    if [ "${DEBUG_MODE}" -eq 1 ] || [ "${VERBOSE_MODE}" -eq 1 ]; then
        log DEBUG "$@"
    fi
}

# ============================================================================
# INITIALIZATION FUNCTIONS
# ============================================================================

init_directories() {
    log INFO "Initializing directories..."
    mkdir -p "${OUTPUT_DIR}" "${LOG_DIR}" "${BACKUP_DIR}"
    
    if [ ! -d "${OUTPUT_DIR}" ]; then
        log ERROR "Failed to create output directory: ${OUTPUT_DIR}"
        return 1
    fi
    
    log SUCCESS "Directories initialized"
    return 0
}

check_prerequisites() {
    log INFO "Checking prerequisites..."
    
    # Check Python3
    if ! command -v python3 &> /dev/null; then
        log ERROR "Python3 is not installed"
        return 1
    fi
    debug "Python3 found: $(python3 --version)"
    
    # Check EDL tool
    if [ ! -f "${EDL_BINARY}" ]; then
        log ERROR "EDL binary not found: ${EDL_BINARY}"
        return 1
    fi
    debug "EDL tool found: ${EDL_BINARY}"
    
    # Check loader
    if [ ! -f "${EDL_LOADER_PATH}" ]; then
        log WARN "Loader not found at ${EDL_LOADER_PATH}"
        log INFO "Will attempt to use system loader or --loader parameter"
    else
        debug "Loader found: ${EDL_LOADER_PATH}"
    fi
    
    # Check USB tools
    if ! command -v lsusb &> /dev/null; then
        log WARN "lsusb not found - USB device detection may not work"
    fi
    
    log SUCCESS "Prerequisites check passed"
    return 0
}

# ============================================================================
# DEVICE DETECTION AND STATUS
# ============================================================================

detect_device() {
    log INFO "Detecting EDL device (VID: ${DEVICE_VID}, PID: ${DEVICE_PID})..."
    
    if ! command -v lsusb &> /dev/null; then
        log WARN "lsusb not available, skipping USB detection"
        return 0
    fi
    
    local device_found=$(lsusb | grep -i "${DEVICE_VID}:${DEVICE_PID}" || true)
    
    if [ -n "${device_found}" ]; then
        log SUCCESS "Device detected!"
        log INFO "Device info: ${device_found}"
        return 0
    else
        log ERROR "Device not found in USB bus"
        log INFO "Available USB devices:"
        lsusb | grep -i qualcomm || lsusb
        return 1
    fi
}

get_device_status() {
    log INFO "Getting device status..."
    
    if ! timeout "${DEVICE_TIMEOUT}" python3 "${EDL_BINARY}" \
        --loader="${EDL_LOADER_PATH}" \
        --memory=ufs nop 2>&1 | tee -a "${LOG_FILE}"; then
        log ERROR "Failed to communicate with device"
        return 1
    fi
    
    log SUCCESS "Device status retrieved"
    return 0
}

# ============================================================================
# EDL OPERATIONS
# ============================================================================

run_nop() {
    log INFO "Running NOP command on device..."
    
    if ! timeout "${DEVICE_TIMEOUT}" python3 "${EDL_BINARY}" \
        --loader="${EDL_LOADER_PATH}" \
        --memory=ufs \
        nop 2>&1 | tee -a "${LOG_FILE}"; then
        log ERROR "NOP command failed"
        return 1
    fi
    
    log SUCCESS "NOP command succeeded"
    return 0
}

read_sectors() {
    local start_sector="$1"
    local num_sectors="$2"
    local output_file="$3"
    local lun="${4:-${DEVICE_LUN}}"
    
    log INFO "Reading sectors ${start_sector}-$((start_sector + num_sectors - 1)) (${num_sectors} sectors)"
    log INFO "Output file: ${output_file}"
    log INFO "Sector size: ${DEVICE_SECTOR_SIZE} bytes"
    
    local total_size=$((num_sectors * DEVICE_SECTOR_SIZE))
    log INFO "Total data to read: $((total_size / 1024 / 1024)) MB"
    
    # Create backup of previous file if exists
    if [ -f "${output_file}" ]; then
        local backup_file="${BACKUP_DIR}/$(basename "${output_file}").backup.$(date +%s)"
        log INFO "Backing up existing file to: ${backup_file}"
        cp "${output_file}" "${backup_file}"
    fi
    
    log INFO "Starting read operation (timeout: ${FIREHOSE_TIMEOUT}s)..."
    
    if timeout "${FIREHOSE_TIMEOUT}" python3 "${EDL_BINARY}" \
        rs "${start_sector}" "${num_sectors}" "${output_file}" \
        --loader="${EDL_LOADER_PATH}" \
        --memory=ufs \
        --lun="${lun}" \
        --sectorsize="${DEVICE_SECTOR_SIZE}" 2>&1 | tee -a "${LOG_FILE}"; then
        
        if [ -f "${output_file}" ]; then
            local file_size=$(stat -f%z "${output_file}" 2>/dev/null || stat -c%s "${output_file}")
            
            if [ "${file_size}" -eq 0 ]; then
                log ERROR "Output file is empty (0 bytes) - read operation failed"
                return 1
            fi
            
            log SUCCESS "Read operation completed"
            log INFO "Output file size: $((file_size / 1024 / 1024)) MB"
            return 0
        else
            log ERROR "Output file was not created"
            return 1
        fi
    else
        local exit_code=$?
        if [ ${exit_code} -eq 124 ]; then
            log ERROR "Read operation timed out (${FIREHOSE_TIMEOUT}s)"
        else
            log ERROR "Read operation failed with exit code: ${exit_code}"
        fi
        return 1
    fi
}

read_boot_partition() {
    local output_file="${OUTPUT_DIR}/boot_${DEVICE_LUN}.img"
    
    log INFO "Reading boot partition from LUN ${DEVICE_LUN}"
    log INFO "Boot sector: ${BOOT_SECTOR}, Sectors: ${BOOT_SECTORS}"
    
    read_sectors "${BOOT_SECTOR}" "${BOOT_SECTORS}" "${output_file}" "${DEVICE_LUN}"
}

read_full_partition() {
    local lun="$1"
    local output_file="${OUTPUT_DIR}/partition_${lun}_full.img"
    
    log INFO "Reading full partition from LUN ${lun}"
    log WARN "This operation may take a long time and require significant disk space"
    
    # Note: Would need to query device for actual partition size
    # Using safe estimate for now
    local max_sectors=2097152  # ~4GB at 4096 byte sectors
    
    read_sectors 0 "${max_sectors}" "${output_file}" "${lun}"
}

write_sectors() {
    local input_file="$1"
    local start_sector="$2"
    local lun="${3:-${DEVICE_LUN}}"
    
    log WARN "WRITE OPERATION - This will modify device storage!"
    log WARN "Input file: ${input_file}"
    log WARN "Start sector: ${start_sector}"
    log WARN "LUN: ${lun}"
    log WARN "Press Ctrl+C to cancel, continue in 5 seconds..."
    
    sleep 5
    
    log INFO "Starting write operation..."
    
    if ! timeout "${FIREHOSE_TIMEOUT}" python3 "${EDL_BINARY}" \
        ws "${start_sector}" "${input_file}" \
        --loader="${EDL_LOADER_PATH}" \
        --memory=ufs \
        --lun="${lun}" \
        --sectorsize="${DEVICE_SECTOR_SIZE}" 2>&1 | tee -a "${LOG_FILE}"; then
        log ERROR "Write operation failed"
        return 1
    fi
    
    log SUCCESS "Write operation completed"
    return 0
}

erase_sectors() {
    local start_sector="$1"
    local num_sectors="$2"
    local lun="${3:-${DEVICE_LUN}}"
    
    log WARN "ERASE OPERATION - This will erase device storage!"
    log WARN "Sectors: ${start_sector}-$((start_sector + num_sectors - 1))"
    log WARN "LUN: ${lun}"
    log WARN "Press Ctrl+C to cancel, continue in 5 seconds..."
    
    sleep 5
    
    log INFO "Starting erase operation..."
    
    if ! timeout "${FIREHOSE_TIMEOUT}" python3 "${EDL_BINARY}" \
        es "${start_sector}" "${num_sectors}" \
        --loader="${EDL_LOADER_PATH}" \
        --memory=ufs \
        --lun="${lun}" \
        --sectorsize="${DEVICE_SECTOR_SIZE}" 2>&1 | tee -a "${LOG_FILE}"; then
        log ERROR "Erase operation failed"
        return 1
    fi
    
    log SUCCESS "Erase operation completed"
    return 0
}

# ============================================================================
# BACKUP AND RESTORE
# ============================================================================

backup_boot() {
    local backup_name="${1:-boot_backup_$(date +%Y%m%d_%H%M%S)}"
    local backup_path="${BACKUP_DIR}/${backup_name}.img"
    
    log INFO "Creating boot partition backup..."
    log INFO "Backup path: ${backup_path}"
    
    read_sectors "${BOOT_SECTOR}" "${BOOT_SECTORS}" "${backup_path}" "${DEVICE_LUN}"
    
    if [ $? -eq 0 ]; then
        log SUCCESS "Boot backup completed: ${backup_path}"
        return 0
    else
        log ERROR "Boot backup failed"
        return 1
    fi
}

backup_full() {
    local backup_name="${1:-full_backup_$(date +%Y%m%d_%H%M%S)}"
    
    log INFO "Creating full device backup..."
    log WARN "This operation may take several hours and require significant disk space"
    
    read_full_partition "${DEVICE_LUN}"
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

analyze_image() {
    local image_file="$1"
    
    if [ ! -f "${image_file}" ]; then
        log ERROR "File not found: ${image_file}"
        return 1
    fi
    
    log INFO "Analyzing image: ${image_file}"
    
    local file_size=$(stat -f%z "${image_file}" 2>/dev/null || stat -c%s "${image_file}")
    local file_type=$(file "${image_file}")
    
    log INFO "File size: ${file_size} bytes ($((file_size / 1024 / 1024)) MB)"
    log INFO "File type: ${file_type}"
    
    # Check for Android boot image magic
    if xxd -l 16 "${image_file}" | grep -q "4142 4f4f" 2>/dev/null; then
        log SUCCESS "Android BOOT image detected (magic: BOOT)"
        return 0
    fi
    
    # Check for ELF magic
    if xxd -l 4 "${image_file}" | grep -q "7f45 4c46" 2>/dev/null; then
        log SUCCESS "ELF binary detected"
        return 0
    fi
    
    log WARN "Unknown image format - not recognized as standard Android/ELF"
    return 0
}

list_backups() {
    log INFO "Available backups:"
    
    if [ ! -d "${BACKUP_DIR}" ] || [ -z "$(ls -A "${BACKUP_DIR}" 2>/dev/null)" ]; then
        log INFO "No backups found"
        return 0
    fi
    
    ls -lh "${BACKUP_DIR}" | tail -n +2 | while read -r line; do
        echo "  ${line}"
    done
    
    return 0
}

show_info() {
    log INFO "=== EDL Control Framework Info ==="
    log INFO "Device Model: ${DEVICE_MODEL}"
    log INFO "Device Storage: ${DEVICE_STORAGE}"
    log INFO "Sector Size: ${DEVICE_SECTOR_SIZE} bytes"
    log INFO "Boot Partition: LUN ${DEVICE_LUN}, Sectors ${BOOT_SECTOR}-$((BOOT_SECTOR + BOOT_SECTORS - 1))"
    log INFO "Boot Size: $((BOOT_SIZE / 1024 / 1024)) MB"
    log INFO "EDL Tool: ${EDL_BINARY}"
    log INFO "Loader: ${EDL_LOADER}"
    log INFO "Output Directory: ${OUTPUT_DIR}"
    log INFO "Log File: ${LOG_FILE}"
    log INFO "===================================="
}

# ============================================================================
# HELP AND USAGE
# ============================================================================

show_usage() {
    cat << 'EOF'
EDL Control Framework - Usage

SYNTAX:
    ./edl-control.sh [COMMAND] [OPTIONS]

COMMANDS:
    detect              Detect EDL device on USB
    status              Get device status
    nop                 Send NOP command to device
    read-boot           Read boot partition to file
    read-sectors S N F  Read N sectors starting at S to file F
    backup-boot [N]     Backup boot partition (optional name N)
    analyze F           Analyze image file F
    list-backups        List available backups
    info                Show device and configuration info
    help                Show this help message
    
OPTIONS:
    -d, --debug         Enable debug output
    -v, --verbose       Enable verbose output
    -t, --timeout N     Set operation timeout in seconds
    -l, --lun N         Set LUN number (default: 4)

EXAMPLES:
    # Detect device
    ./edl-control.sh detect
    
    # Read boot partition
    ./edl-control.sh read-boot
    
    # Read custom sector range
    ./edl-control.sh read-sectors 79366 24576 boot.img
    
    # Backup boot partition
    ./edl-control.sh backup-boot my_backup
    
    # Analyze image
    ./edl-control.sh analyze boot.img
    
    # Enable debug mode
    ./edl-control.sh --debug status
    
NOTES:
    - Device must be in EDL mode before operations
    - All backups are stored in: ~/edl_dumps/backups/
    - Logs are saved to: ~/edl_dumps/logs/edl-control.log
    - Write and erase operations require manual confirmation
    
HARDWARE LIMITATIONS:
    - Firehose configure command may timeout on some devices
    - This is a device firmware limitation, not a software bug
    - If read fails, try alternative loaders or tools
    
See README.md for more information.
EOF
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    local command="${1:-help}"
    
    # Parse global options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -d|--debug)
                DEBUG_MODE=1
                VERBOSE_MODE=1
                shift
                ;;
            -v|--verbose)
                VERBOSE_MODE=1
                shift
                ;;
            -t|--timeout)
                FIREHOSE_TIMEOUT="$2"
                shift 2
                ;;
            -l|--lun)
                DEVICE_LUN="$2"
                shift 2
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Initialize
    init_directories || exit 1
    
    log INFO "========================================="
    log INFO "EDL Control Framework Started"
    log INFO "========================================="
    
    # Execute command
    case "${command}" in
        detect)
            check_prerequisites || exit 1
            detect_device
            ;;
        status)
            check_prerequisites || exit 1
            get_device_status
            ;;
        nop)
            check_prerequisites || exit 1
            run_nop
            ;;
        read-boot)
            check_prerequisites || exit 1
            detect_device || exit 1
            read_boot_partition
            ;;
        read-sectors)
            check_prerequisites || exit 1
            detect_device || exit 1
            read_sectors "$2" "$3" "$4" "${DEVICE_LUN}"
            ;;
        backup-boot)
            check_prerequisites || exit 1
            detect_device || exit 1
            backup_boot "${2:-}"
            ;;
        backup-full)
            check_prerequisites || exit 1
            detect_device || exit 1
            backup_full "${2:-}"
            ;;
        analyze)
            analyze_image "$2"
            ;;
        list-backups)
            list_backups
            ;;
        info)
            show_info
            ;;
        help)
            show_usage
            ;;
        *)
            log ERROR "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
    
    local exit_code=$?
    
    log INFO "========================================="
    if [ ${exit_code} -eq 0 ]; then
        log SUCCESS "EDL Control Framework Completed Successfully"
    else
        log ERROR "EDL Control Framework Failed (exit code: ${exit_code})"
    fi
    log INFO "========================================="
    
    exit ${exit_code}
}

# Execute main function
main "$@"
