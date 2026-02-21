# A53 SLA Ripper - Quick Setup Guide

## Installation Steps

### 1. Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    usbutils
```

**CentOS/RedHat:**
```bash
sudo yum install -y \
    python3 \
    python3-pip \
    libusb-devel \
    usbutils
```

**macOS:**
```bash
brew install python3 libusb
```

### 2. Install Python Requirements

```bash
cd a53_sla_ripper
pip3 install -r requirements.txt
```

### 3. Make Scripts Executable

```bash
chmod +x a53_sla_ripper/sla_ripper.sh
```

### 4. Verify Installation

```bash
./a53_sla_ripper/sla_ripper.sh help
python3 a53_sla_ripper/sla_ripper.py --help
```

## Device Setup

### Enter EDL Mode on Oppo A53

1. **Power off the device completely**
   ```
   Press and hold Power button until device shuts down
   ```

2. **Connect USB cable to PC**
   ```
   Use a good quality USB cable (important!)
   Preferably USB 3.0 port on PC
   ```

3. **Enter Sahara/EDL mode**
   ```
   Hold Vol Down button
   Press Power + Power (tap twice quickly)
   Keep Vol Down pressed for 5-10 seconds
   Device will vibrate once and enter EDL mode
   Do NOT release Vol Down until you see device in lsusb
   ```

4. **Verify device detection**
   ```bash
   lsusb | grep "05c6:9008"
   # Should output: Bus 001 Device 009: ID 05c6:9008 Qualcomm, Inc. ...
   ```

## Quick Test

```bash
# Detect device
./a53_sla_ripper/sla_ripper.sh detect

# Should output:
# [SUCCESS] Device detected: Oppo A53 (CPH2127) (VID:05C6 PID:9008)
```

## Full Workflow

```bash
# Extract boot image (takes 10-20 minutes)
./a53_sla_ripper/sla_ripper.sh extract-boot

# Analyze boot image
./a53_sla_ripper/sla_ripper.sh analyze-boot

# Extract SLA certificates
./a53_sla_ripper/sla_ripper.sh extract-sla

# View security report
./a53_sla_ripper/sla_ripper.sh dump-security

# Check output files
ls -lah a53_sla_ripper/output/
```

## File Locations

After successful extraction:

```
a53_sla_ripper/
├── output/
│   ├── boot.img                    # Full boot partition (98 MB)
│   ├── sla_report.json             # SLA analysis (JSON)
│   ├── sla_report.txt              # SLA analysis (readable)
│   ├── security_info.txt           # Security summary
│   ├── kernel                      # Extracted kernel binary
│   ├── ramdisk.gz                  # Extracted ramdisk
│   ├── sla_0.bin                   # SLA certificate (if found)
│   ├── qfprom_oem_config.bin       # OEM config fuses
│   ├── qfprom_anti_rollback.bin    # Anti-rollback version
│   ├── qfprom_serial.bin           # Device serial number
│   └── sla_ripper.log              # Operation log
```

## Troubleshooting

### Device Not Detected

```bash
# Check USB connection
lsusb | grep -i "qualcomm\|05c6"

# If nothing appears:
# 1. Try different USB port
# 2. Try different USB cable
# 3. Ensure you're holding Vol Down during boot sequence
# 4. Try longer power press (2-3 seconds before release)
```

### Permission Denied on USB

```bash
# Grant USB permissions to user
sudo usermod -a -G plugdev $(whoami)
sudo udevadm control --reload-rules

# Logout and login for changes to take effect
# Or run with sudo: sudo ./a53_sla_ripper/sla_ripper.sh detect
```

### Extraction Timeouts

```bash
# If boot extraction times out:
# 1. Use USB 3.0 port (faster)
# 2. Use shorter USB cable
# 3. Close other USB-using applications
# 4. Try again - sometimes device needs reconnection

# Run with verbose output for debugging
./a53_sla_ripper/sla_ripper.sh extract-boot --verbose
```

### Python Import Errors

```bash
# Reinstall requirements
pip3 install --upgrade -r a53_sla_ripper/requirements.txt

# Verify Python version (should be 3.7+)
python3 --version

# Check installed packages
pip3 list | grep -i usb
```

## Next Steps

1. **Read the full README:**
   ```bash
   cat a53_sla_ripper/README.md
   ```

2. **Analyze the output:**
   ```bash
   # View JSON report
   python3 -m json.tool a53_sla_ripper/output/sla_report.json | less
   
   # View text report
   cat a53_sla_ripper/output/sla_report.txt
   
   # View security info
   cat a53_sla_ripper/output/security_info.txt
   ```

3. **Extract boot components:**
   ```bash
   # Kernel is already extracted as 'kernel'
   file a53_sla_ripper/output/kernel
   
   # Extract ramdisk contents
   mkdir -p /tmp/ramdisk_extracted
   cd /tmp/ramdisk_extracted
   gunzip -c a53_sla_ripper/output/ramdisk.gz | cpio -i
   ls -la
   ```

4. **Verify extracted files:**
   ```bash
   # Calculate hashes
   sha256sum a53_sla_ripper/output/boot.img
   sha256sum a53_sla_ripper/output/kernel
   sha256sum a53_sla_ripper/output/ramdisk.gz
   
   # Compare with stored hashes
   cat a53_sla_ripper/output/boot.img.sha256
   ```

## Support

For issues or questions:

1. Check `a53_sla_ripper/output/sla_ripper.log` for detailed error messages
2. Run with `--verbose` flag for more debugging information
3. Verify device is in EDL mode: `lsusb | grep 05c6:9008`
4. Try with different USB port or cable

## Safety Notes

⚠️ **Important:**
- **Backup important data** before any device operations
- **Do not disconnect** during extraction (can corrupt device state)
- **Use quality USB cable** - flaky connections cause timeouts
- **Ensure good USB connection** - extraction takes 10-20 minutes
- **Device may get warm** during extended operations - normal
- **Read-only operations** - this tool does not write to device

---

For more information, see `README.md` in the a53_sla_ripper directory.
