#!/bin/bash
# A53 SLA Ripper - Device Recovery Script
# Recovers device from stuck EDL state

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDL_BINARY="${SCRIPT_DIR}/../edl/edl"
LOADER_DIR="${SCRIPT_DIR}/../Loaders"

echo "========================================"
echo "A53 Device Recovery Tool"
echo "========================================"
echo ""
echo "This script will attempt to recover your device"
echo "from a stuck EDL state."
echo ""
echo "Steps:"
echo "1. Device will be rebooted to normal mode"
echo "2. Device will restart"
echo "3. Wait for normal boot (2-3 minutes)"
echo ""

# Check device detection
echo "[*] Detecting device..."
if ! lsusb -d "05c6:9008" &> /dev/null; then
    echo "[!] Device not detected in EDL mode"
    echo "    Make sure device is connected and in EDL mode"
    echo "    Run: ./a53_sla_ripper.sh detect"
    exit 1
fi

echo "[+] Device detected!"
echo ""

# Find loader
echo "[*] Finding Firehose loader..."
LOADER=""
if [[ -f "$LOADER_DIR/qualcomm/patched/prog_firehose_ddr_fwupdate.elf" ]]; then
    LOADER="$LOADER_DIR/qualcomm/patched/prog_firehose_ddr_fwupdate.elf"
elif [[ -f "$LOADER_DIR/qualcomm/prog_firehose_ddr_fwupdate.elf" ]]; then
    LOADER="$LOADER_DIR/qualcomm/prog_firehose_ddr_fwupdate.elf"
fi

if [[ -z "$LOADER" ]]; then
    echo "[!] Loader not found!"
    exit 1
fi

echo "[+] Loader found: $LOADER"
echo ""

# Attempt reset/reboot
echo "[*] Attempting device reboot..."
python3 "$EDL_BINARY" reset --loader="$LOADER" 2>&1 || true

echo ""
echo "[*] Device should now be rebooting..."
echo ""
echo "Waiting for device to restart (120 seconds)..."
sleep 120

echo ""
echo "Device recovery complete!"
echo "If device does not boot, try:"
echo "1. Long-press Power button (30 seconds) to force off"
echo "2. Remove battery for 10 seconds (if possible)"
echo "3. Reconnect and power on normally"
