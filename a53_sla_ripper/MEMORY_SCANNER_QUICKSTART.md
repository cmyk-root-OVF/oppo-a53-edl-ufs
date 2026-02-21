# Memory Scanner - Quick Start Guide

## What is the Memory Scanner?

The Memory Scanner is an aggressive tool that finds actual QFPROM data on Snapdragon 460 (Oppo A53) by scanning memory ranges and **only reporting non-zero values** (filtering out honeypots).

**Problem it solves**: Address 0x00780200 returns all zeros (honeypot). The scanner finds where the real data actually is.

## Quick Commands

### 1. Default Full Scan (512 KB)
```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory
```
- Scans: 0x00700000 to 0x00800000
- Time: ~43 minutes
- Results: memory_scan.log

### 2. Fast Focused Scan (64 KB QFPROM region)
```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
  --start-addr 0x00780000 \
  --end-addr 0x007A0000 \
  --log-file qfprom_primary.log
```
- Time: ~64 seconds
- Focus: Primary QFPROM region

### 3. Even Faster (Skip every other address)
```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory --step 8 --log-file fast.log
```
- Time: ~22 minutes
- Trade-off: Less coverage, but faster

### 4. Secondary QFPROM Region
```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
  --start-addr 0x007B0000 \
  --end-addr 0x007C0000
```
- Secondary fuses area
- Time: ~64 seconds

## Understanding the Output

### What You'll See on Console
```
[*] Starting memory scan: 0x00700000 → 0x00800000
[+] 0x00701234: a5 b3 c2 d1        ← Real data found!
[*] Progress: 256/262144 (0.1%) - Elapsed: 2.5s - Non-zero: 1
...
[*] Scan complete!
[*] Total reads: 262,144
[*] Non-zero addresses found: 42
```

### What Gets Saved to Log File
```
0x00701234: a5 b3 c2 d1
0x00702456: 42 00 00 01
0x00703789: ff ff ff ff
```

## Why 10ms Delays?

The scanner adds a **10ms delay between each read**. This is mandatory for Snapdragon 460 to prevent:
- SLA (Secure Level Authentication) timeouts
- Device disconnection
- Scan failures

**DO NOT remove or reduce this delay** - it's why full scans take ~43 minutes.

## Key Features

| Feature | Details |
|---------|---------|
| **Honeypot Filtering** | Automatically skips 0x00000000 (all zeros) values |
| **Real-time Logging** | Non-zero data printed immediately + saved to file |
| **Flexible Range** | Scan any address range, any step size |
| **Progress Tracking** | Shows progress every 256 reads |
| **Interrupt Safe** | Partial results preserved if you Ctrl+C |

## CLI Options Reference

```
--start-addr HEX      Starting address (default: 0x00700000)
--end-addr HEX        Ending address (default: 0x00800000)
--step N              Bytes between reads (default: 4)
--log-file PATH       Output file (default: memory_scan.log)
--edl-binary PATH     EDL binary (default: edl/edl)
--loader PATH         Firehose loader
```

## Common Memory Ranges

```
0x00700000-0x00780000   Shared RAM area (~512 KB)
0x00780000-0x00790000   Primary QFPROM (~64 KB)
0x00790000-0x007A0000   Shadow QFPROM (~64 KB)
0x007B0000-0x007C0000   Secondary fuses (~64 KB)
```

## Troubleshooting

### Device Not Found
```bash
# Check if device is in EDL mode
lsusb | grep 05c6:9008
```
Should show: `Qualcomm Inc. Qualcomm CDMA modem`

### Scan Too Slow?
1. Use smaller range: `--end-addr 0x00790000`
2. Increase step: `--step 8`
3. Run in background: `nohup python3 ... scan-memory &`

### Want to Resume Partial Scan?
```bash
# If scan stopped at 0x00710000, resume from there
python3 a53_sla_ripper/sla_ripper.py scan-memory \
  --start-addr 0x00710000 \
  --end-addr 0x00800000 \
  --log-file qfprom_full.log
```

## Python API Usage

```python
from a53_sla_ripper.sla_ripper import QFPROMExtractor

# Create scanner
scanner = QFPROMExtractor(log_file="results.log")

# Run scan
results = scanner.scan_memory(
    start_addr=0x00700000,
    end_addr=0x00800000,
    step=4
)

# Process results
for address, hex_value in sorted(results.items()):
    print(f"Found at 0x{address:08x}: {hex_value}")
```

## Performance Benchmarks

| Scan Type | Time | Reads |
|-----------|------|-------|
| Full (512 KB, step=4) | ~43 min | 262,144 |
| QFPROM only (64 KB, step=4) | ~64 sec | 16,384 |
| Fast (512 KB, step=8) | ~22 min | 131,072 |
| Quick test (8 KB, step=4) | ~8 sec | 2,048 |

## Example Workflow

1. **Quick test** - Verify scanner works
   ```bash
   python3 a53_sla_ripper/sla_ripper.py scan-memory \
     --start-addr 0x00700000 --end-addr 0x00710000
   ```

2. **QFPROM scan** - Check primary fuse region
   ```bash
   python3 a53_sla_ripper/sla_ripper.py scan-memory \
     --start-addr 0x00780000 --end-addr 0x007A0000
   ```

3. **Full scan** - Comprehensive search
   ```bash
   python3 a53_sla_ripper/sla_ripper.py scan-memory
   ```

4. **Analyze results**
   ```bash
   cat memory_scan.log | head -20
   wc -l memory_scan.log
   ```

## Critical Reminders

⚠️ **DO NOT reduce 10ms delay** - causes device failure  
⚠️ **Keep device in EDL mode** - don't disconnect USB  
⚠️ **Full scan takes ~43 minutes** - use `nohup` for long runs  
⚠️ **Honeypots are automatic** - no need to filter results manually  

## Next Steps

1. Connect Oppo A53 in EDL mode
2. Run: `python3 a53_sla_ripper/sla_ripper.py scan-memory`
3. Monitor progress
4. Check `memory_scan.log` for results
5. Analyze non-zero values for actual QFPROM data

## For More Details

Read the full documentation:
```bash
cat a53_sla_ripper/MEMORY_SCANNER.md
```

---

**Memory Scanner v1.2** | Oppo A53 (CPH2127) | Snapdragon 460  
Aggressive QFPROM discovery tool with honeypot filtering
