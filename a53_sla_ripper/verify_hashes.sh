#!/bin/bash
# A53 SLA Ripper - Hash Verification Utility
# Verify integrity of extracted files using checksums

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

if [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "[!] Output directory not found: $OUTPUT_DIR"
    echo "Run extraction first: ./sla_ripper.sh extract-boot"
    exit 1
fi

echo "========================================"
echo "A53 SLA Ripper - Hash Verification"
echo "========================================"
echo ""

verified=0
failed=0

# Check boot.img
if [[ -f "${OUTPUT_DIR}/boot.img" ]]; then
    echo "[*] Verifying boot.img..."
    if [[ -f "${OUTPUT_DIR}/boot.img.sha256" ]]; then
        stored_hash=$(cat "${OUTPUT_DIR}/boot.img.sha256")
        actual_hash=$(sha256sum "${OUTPUT_DIR}/boot.img" | awk '{print $1}')
        
        if [[ "$stored_hash" == "$actual_hash" ]]; then
            echo "[+] boot.img: OK (SHA256: ${actual_hash:0:16}...)"
            verified=$((verified + 1))
        else
            echo "[-] boot.img: FAILED - Hash mismatch!"
            echo "    Stored: $stored_hash"
            echo "    Actual: $actual_hash"
            failed=$((failed + 1))
        fi
    else
        # Calculate and store
        hash=$(sha256sum "${OUTPUT_DIR}/boot.img" | awk '{print $1}')
        echo "$hash" > "${OUTPUT_DIR}/boot.img.sha256"
        echo "[*] boot.img: Hash calculated and stored"
        echo "    SHA256: ${hash:0:16}..."
    fi
    echo ""
fi

# Check kernel
if [[ -f "${OUTPUT_DIR}/kernel" ]]; then
    echo "[*] Verifying kernel..."
    hash=$(sha256sum "${OUTPUT_DIR}/kernel" | awk '{print $1}')
    echo "[+] kernel: SHA256 ${hash:0:16}..."
    verified=$((verified + 1))
    echo ""
fi

# Check ramdisk
if [[ -f "${OUTPUT_DIR}/ramdisk.gz" ]]; then
    echo "[*] Verifying ramdisk.gz..."
    hash=$(sha256sum "${OUTPUT_DIR}/ramdisk.gz" | awk '{print $1}')
    echo "[+] ramdisk.gz: SHA256 ${hash:0:16}..."
    verified=$((verified + 1))
    echo ""
fi

# Check SLA files
sla_count=0
for sla_file in "${OUTPUT_DIR}"/sla_*.bin; do
    if [[ -f "$sla_file" ]]; then
        hash=$(sha256sum "$sla_file" | awk '{print $1}')
        filename=$(basename "$sla_file")
        echo "[+] $filename: SHA256 ${hash:0:16}..."
        sla_count=$((sla_count + 1))
    fi
done

if [[ $sla_count -gt 0 ]]; then
    echo "    Found $sla_count SLA certificates"
    echo ""
fi

# Check QFPROM files
qfprom_count=0
for qfprom_file in "${OUTPUT_DIR}"/qfprom_*.bin; do
    if [[ -f "$qfprom_file" ]]; then
        hash=$(sha256sum "$qfprom_file" | awk '{print $1}')
        filename=$(basename "$qfprom_file")
        echo "[+] $filename: SHA256 ${hash:0:16}..."
        qfprom_count=$((qfprom_count + 1))
    fi
done

if [[ $qfprom_count -gt 0 ]]; then
    echo "    Found $qfprom_count QFPROM files"
    echo ""
fi

# Summary
echo "========================================"
echo "Verification Summary"
echo "========================================"
echo "Verified: $verified files"
echo "Failed:   $failed files"
echo "SLA:      $sla_count certificates"
echo "QFPROM:   $qfprom_count files"
echo ""

if [[ $failed -eq 0 ]]; then
    echo "[+] All verifications passed!"
    exit 0
else
    echo "[-] Some verifications failed!"
    exit 1
fi
