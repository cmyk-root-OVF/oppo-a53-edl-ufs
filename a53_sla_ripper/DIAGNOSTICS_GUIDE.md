# Enhanced Diagnostics & Stability Guide

## Version 1.3 - Stability & Diagnostic Improvements

This document describes the new diagnostic and stability features added to the A53 SLA Ripper for authorized device recovery and troubleshooting.

## Overview

The v1.3 upgrade adds three major components:

1. **Firehose XML Handler** - Robust protocol support for standard <read>, <configure>, and <nop> commands
2. **USB Error Recovery** - Graceful degradation when device returns non-standard responses (0x04, 0xff)
3. **SLA Response Logger** - Comprehensive diagnostic logging for debugging connection issues

## Features

### 1. Firehose XML Handler

The `FirehoseXMLHandler` class provides standard Firehose protocol support with built-in XML parsing.

#### Supported Commands

| Command | Purpose | Parameters |
|---------|---------|------------|
| `<read>` | Read memory or UFS sectors | `physical_address`, `num_partition_sectors` |
| `<configure>` | Configure device settings | `target_type`, `sector_size` |
| `<nop>` | Keep-alive heartbeat | None |

#### UFS Support

- **Sector Size**: 4096 bytes (standard for UFS)
- **Max Transfer**: 512 sectors per request (2MB)
- **LUN Support**: Configurable via read commands

#### Usage Example

```python
from a53_sla_ripper.sla_ripper import FirehoseXMLHandler

handler = FirehoseXMLHandler(usb_device=device)

# Build a read command
read_cmd = handler.build_read_command(
    address=0x00700000,
    size=4096,
    physical=True
)

# Send and parse response
response = handler.send_command(read_cmd)
parsed = handler.parse_response(response)

print(f"Status: {parsed['status']}")
print(f"Error: {parsed['error']}")
```

### 2. USB Error Recovery

The `USBErrorRecovery` class handles device errors gracefully without losing the entire scan.

#### Error Handling Strategy

**Error Code 0x04** (Non-standard response):
- Skip to next 4KB boundary after 5 consecutive errors
- Automatically documented in skip report
- Prevents repeated failures in same region

**Error Code 0xff** (Timeout/Disconnect):
- Wait 2 seconds before retry
- Automatic recovery up to 3 times
- Logs timeout for diagnostics

**Other Errors**:
- Skip current address and continue
- Reset error counter on success
- Graceful degradation throughout scan

#### Usage Example

```python
from a53_sla_ripper.sla_ripper import USBErrorRecovery

recovery = USBErrorRecovery()

# Handle an error
action = recovery.handle_error(
    address=0x00701000,
    error_code=0x04,
    response_data=response_bytes
)

# action = {
#     "action": "skip_to_next_block",
#     "next_address": 0x00702000,
#     "skip_size": 0x1000,
#     "reason": "error_code_0x04"
# }

# Get summary report
print(recovery.get_skip_report())
```

### 3. SLA Response Logger

The `SLAResponseLogger` class provides comprehensive diagnostic logging for troubleshooting connection issues.

#### Logged Information

- **Device Responses**: All USB responses with timestamps and hex data
- **Error Details**: Error codes, messages, and context
- **SLA Challenges**: When device sends `SLA_Required` message
- **Loader Responses**: Firehose loader acceptance/rejection
- **Connection Summary**: Success rates and error statistics

#### Output Files

1. **sla_response_log.json** - Complete diagnostic dump (JSON format)
2. **sla_challenge_vault.hex** - SLA challenge data (hex format, appended)

#### Usage Example

```python
from a53_sla_ripper.sla_ripper import SLAResponseLogger
from datetime import datetime

logger = SLAResponseLogger("my_diagnostics.json")

# Log a device response
logger.log_response(
    timestamp=datetime.now().isoformat(),
    source="pyusb",
    response_type="peek_response",
    data=response_bytes,
    status="OK"
)

# Log an error
logger.log_error(
    timestamp=datetime.now().isoformat(),
    error_type="usb_error_0x04",
    error_msg="Non-standard response at address",
    context={"address": "0x00701000"}
)

# Log SLA challenge for offline analysis
logger.log_sla_challenge(
    timestamp=datetime.now().isoformat(),
    challenge_data=challenge_hex_bytes
)

# Save and print summary
logger.save_diagnostics()
print(logger.get_connection_summary())
```

## New CLI Actions

### 1. scan-memory with Diagnostics

Enhanced version of the memory scanner with integrated diagnostics.

```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --start-addr 0x00700000 \
    --end-addr 0x00800000 \
    --step 4 \
    --enable-diagnostics \
    --diagnostic-log my_diags.json
```

**Output Files**:
- `memory_scan.log` - Non-zero memory values found
- `my_diags.json` - Complete diagnostic dump (responses, errors, challenges)
- Console output - Progress and summary

**Features**:
- Real-time error recovery during scan
- Automatic skip region tracking
- USB error logging
- Connection stability monitoring

### 2. diagnose-firehose

Test Firehose protocol implementation and device responsiveness.

```bash
python3 a53_sla_ripper/sla_ripper.py diagnose-firehose \
    --loader prog_firehose_ddr_fwupdate.elf
```

**Tests Performed**:
1. NOP heartbeat - Verify keep-alive works
2. Configure command - Test device configuration response
3. Response parsing - Validate XML response handling

**Output**:
- Log file with all responses
- Console summary with status for each test
- `sla_response_log.json` with detailed debug info

**Example Output**:
```
Test 1: Sending NOP heartbeat...
NOP Response: 01020304...
Test 2: Sending configure command...
Configure Response Status: ack
```

### 3. diagnose-usb

Simulate USB error scenarios and test error recovery logic.

```bash
python3 a53_sla_ripper/sla_ripper.py diagnose-usb
```

**Simulations**:
- 5x consecutive 0x04 errors (non-standard response)
- Recovery action evaluation
- Skip region tracking

**Output**:
```
Simulating USB error scenarios...
Test 1: 0x04 error code handling...
  Attempt 1: skip_address
  Attempt 2: skip_address
  ...
  
Recovery Actions Summary:
Skipped Regions:
  0x00701000 - 0x00702000 (0x04_errors)
```

## Diagnostic Output Files

### sla_response_log.json

Complete diagnostic dump in JSON format.

```json
{
  "timestamp": "2026-02-19T19:21:06.273456",
  "total_responses": 1024,
  "sla_challenges_count": 2,
  "loader_responses": 1,
  "errors_count": 5,
  "responses": [
    {
      "timestamp": "2026-02-19T19:21:05.100000",
      "source": "pyusb",
      "type": "peek_response",
      "status": "OK",
      "data_hex": "a5b3c2d1",
      "data_size": 4,
      "data_ascii": "¥³Â±"
    },
    ...
  ],
  "errors": [
    {
      "timestamp": "2026-02-19T19:21:06.200000",
      "type": "usb_error_0x04",
      "message": "Non-standard response at 0x00701000",
      "context": {
        "action": "skip_address",
        "next_address": "0x00701004"
      }
    }
  ]
}
```

### sla_challenge_vault.hex

Raw hex dump of SLA challenges received during scan.

```
# 2026-02-19T19:21:05.500000
0401020304050607080910111213141516171819202122232425262728293031
...
```

## Integration with Existing Features

### Memory Scanner Enhanced

The memory scanner (`scan-memory`) now includes:

```python
scanner = QFPROMExtractor(
    edl_binary="edl/edl",
    loader="prog_firehose_ddr_fwupdate.elf",
    log_file="memory_scan.log",
    enable_diagnostics=True,  # NEW
    diagnostic_log="sla_response_log.json"  # NEW
)

# Access diagnostic tools
scanner.sla_logger  # SLAResponseLogger instance
scanner.error_recovery  # USBErrorRecovery instance
scanner.firehose_handler  # FirehoseXMLHandler instance
```

### Graceful Degradation

If device returns 0x04 errors:
1. First 3 errors: Skip address and continue
2. 4-5 errors in sequence: Skip to next 4KB boundary
3. All errors logged for diagnostics

Example flow:
```
Address 0x00701000: 0x04 error → Skip to 0x00701004
Address 0x00701004: 0x04 error → Skip to 0x00701008
Address 0x00701008: 0x04 error → Reset counter
...
[5 errors in region] → Skip to 0x00702000 (next 4KB boundary)
```

## Use Cases

### 1. Troubleshooting Connection Issues

If your Firehose loader isn't being accepted:

```bash
# Run diagnostics
python3 a53_sla_ripper/sla_ripper.py diagnose-firehose \
    --loader my_loader.elf

# Check output
cat sla_response_log.json
```

This logs:
- All device responses
- Loader acceptance/rejection
- Error codes and messages
- Connection timestamps

### 2. Debugging Unstable Scans

If memory scans are failing or disconnecting:

```bash
# Run with diagnostics enabled
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --enable-diagnostics

# Analyze results
cat sla_response_log.json | jq '.errors'
```

Shows:
- Where errors occurred
- Error codes and patterns
- Automatic recovery actions taken
- Success/failure statistics

### 3. Testing UFS Partition Access

To verify UFS storage is accessible:

```python
from a53_sla_ripper.sla_ripper import FirehoseXMLHandler

handler = FirehoseXMLHandler()

# Test UFS configuration
config = handler.build_configure_command(
    target_type="UFS",
    sector_size="4096"
)

response = handler.send_command(config)
parsed = handler.parse_response(response)
```

### 4. Monitoring Device Stability

Enable diagnostics during long scans to monitor:
- Response latency
- Error frequency
- Connection stability
- Device timeouts

## Performance Considerations

### 10ms Timing Precision

The error recovery system preserves the critical 10ms PEEK_COMMAND_DELAY:

```python
# Delay applied before device read
time.sleep(self.PEEK_COMMAND_DELAY)  # 0.01 seconds = 10ms

# Delay applied after EDL commands
time.sleep(self.PEEK_COMMAND_DELAY)
```

This ensures Snapdragon 460 SLA safety is maintained even with error recovery active.

### Minimal Overhead

Diagnostic logging adds minimal overhead:
- JSON responses appended asynchronously
- No blocking I/O during reads
- Graceful degradation if file I/O slow
- In-memory buffering for efficiency

### Error Recovery Speed

When errors occur:
- 0x04 errors: Immediate skip (< 1ms overhead)
- 0xff timeouts: 2 second delay + retry
- Retry up to 3 times before skip
- Scanning continues automatically

## Troubleshooting Diagnostics

### Issue: No responses in log file

**Cause**: Device not connected or pyusb not available

**Solution**:
```bash
# Check device detected
lsusb | grep 05c6:9008

# Install pyusb
pip install pyusb

# Run again with verbose
python3 a53_sla_ripper/sla_ripper.py scan-memory -v
```

### Issue: All errors, no successful reads

**Cause**: Device returning 0x04 for all addresses

**Solution**:
1. Check device is in EDL mode
2. Try different loader
3. Run `diagnose-firehose` to verify protocol
4. Check device temperature (thermal throttling)

### Issue: JSON log file is empty

**Cause**: Diagnostics not enabled

**Solution**:
```bash
# Make sure to use --enable-diagnostics flag
python3 a53_sla_ripper/sla_ripper.py scan-memory --enable-diagnostics
```

## API Reference

### FirehoseXMLHandler

```python
class FirehoseXMLHandler:
    def __init__(self, usb_device=None, logger_instance=None)
    def build_read_command(address, size, physical=True) -> str
    def build_configure_command(**kwargs) -> str
    def build_nop_command() -> str
    def send_command(xml_command) -> Optional[bytes]
    def parse_response(response) -> Dict
```

### USBErrorRecovery

```python
class USBErrorRecovery:
    def __init__(self, logger_instance=None)
    def handle_error(address, error_code, response_data=None) -> Dict
    def reset_error_count()
    def get_skip_report() -> str
```

### SLAResponseLogger

```python
class SLAResponseLogger:
    def __init__(self, log_file=None)
    def log_response(timestamp, source, response_type, data, status="OK")
    def log_sla_challenge(timestamp, challenge_data)
    def log_loader_response(timestamp, loader_name, response, success)
    def log_error(timestamp, error_type, error_msg, context=None)
    def save_diagnostics() -> str
    def get_connection_summary() -> str
```

## Next Steps

1. **Enable Diagnostics**: Run scans with `--enable-diagnostics` flag
2. **Monitor Logs**: Check `sla_response_log.json` for patterns
3. **Test Protocol**: Use `diagnose-firehose` to verify device communication
4. **Debug Errors**: Use `diagnose-usb` to validate error recovery logic
5. **Optimize**: Adjust retry counts and timeouts based on device behavior

## Technical Details

### Response Parsing

The `FirehoseXMLHandler` detects response types:

- **ACK**: Successful command execution
- **NAK**: Command rejected by device
- **ERROR**: Protocol or device error
- **LOG**: Device informational message
- **0x04**: Non-standard response code
- **TIMEOUT**: No response received

### Error Classification

| Code | Meaning | Recovery |
|------|---------|----------|
| 0x04 | Non-standard response | Skip address/region |
| 0xff | Timeout/Disconnect | Wait and retry |
| Other | Generic error | Skip and continue |

### Stability Guarantees

- ✓ 10ms timing always preserved
- ✓ No connection loss due to logging
- ✓ Automatic skip regions tracked
- ✓ Partial results preserved on interrupt
- ✓ Full diagnostics before failure

## Version History

- **v1.3** (Current): Enhanced diagnostics and stability
- **v1.2**: Memory Scanner with honeypot filtering
- **v1.1**: QFPROM optimization with pyusb
- **v1.0**: Initial SLA extraction toolkit

---

**A53 SLA Ripper v1.3** | Oppo A53 (CPH2127) | Snapdragon 460  
Enhanced stability, diagnostics, and error recovery for authorized device recovery
