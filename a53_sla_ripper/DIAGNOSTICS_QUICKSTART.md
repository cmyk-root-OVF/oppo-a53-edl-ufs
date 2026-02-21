# Diagnostics Quick Reference

## New Commands (v1.3)

### 1. Memory Scan with Full Diagnostics

```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --enable-diagnostics \
    --diagnostic-log my_diagnostics.json
```

**Output Files**:
- `memory_scan.log` - Non-zero values found
- `my_diagnostics.json` - Complete response/error log
- `sla_challenge_vault.hex` - SLA challenges (if received)

**Features**:
- Integrated error recovery
- Automatic skip region tracking
- Connection stability monitoring
- Real-time logging

---

### 2. Firehose Protocol Diagnostics

```bash
python3 a53_sla_ripper/sla_ripper.py diagnose-firehose
```

**Tests**:
- NOP heartbeat (keep-alive)
- Configure command (device setup)
- Response parsing (XML validation)

**Use When**:
- Firehose loader not being accepted
- Device rejecting commands
- Protocol communication issues

**Output Example**:
```
Test 1: Sending NOP heartbeat...
NOP Response: 01020304...
Test 2: Sending configure command...
Configure Response Status: ack
```

---

### 3. USB Error Recovery Diagnostics

```bash
python3 a53_sla_ripper/sla_ripper.py diagnose-usb
```

**Simulates**:
- 5x consecutive 0x04 errors
- Recovery action evaluation
- Skip region tracking

**Output Example**:
```
Test 1: 0x04 error code handling...
  Attempt 1: skip_address
  Attempt 2: skip_address
  ...
  
Recovery Actions Summary:
Skipped Regions:
  0x00701000 - 0x00702000 (0x04_errors)
```

**Use When**:
- Scan fails with repeated errors
- Device returning non-standard responses
- Need to validate error handling

---

## Common Scenarios

### Scenario 1: Connection Troubleshooting

```bash
# Step 1: Test Firehose protocol
python3 a53_sla_ripper/sla_ripper.py diagnose-firehose

# Step 2: Check logs for errors
cat sla_response_log.json | jq '.errors'

# Step 3: Verify device responses
cat sla_response_log.json | jq '.loader_responses'
```

---

### Scenario 2: Unstable Scan Recovery

```bash
# Run scan with diagnostics
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --enable-diagnostics

# After failure, analyze:
cat sla_response_log.json | jq '.errors[-5:]'  # Last 5 errors
cat memory_scan.log | tail -20  # Last results found

# Check skip regions:
python3 -c "
import json
with open('sla_response_log.json') as f:
    log = json.load(f)
    for error in log['errors']:
        print(f\"{error['type']}: {error['message']}\")
"
```

---

### Scenario 3: Long Duration Scan Monitoring

```bash
# Start scan in background
nohup python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --enable-diagnostics &

# Monitor real-time progress
watch -n 5 'tail memory_scan.log'

# Check error frequency
watch -n 10 'jq ".errors_count" sla_response_log.json'

# When done, analyze complete diagnostics
cat sla_response_log.json | jq '.'
```

---

## Log File Analysis

### Extract Error Summary

```bash
python3 << 'EOF'
import json

with open('sla_response_log.json') as f:
    log = json.load(f)

print(f"Total Responses: {log['total_responses']}")
print(f"Errors: {log['errors_count']}")
print(f"SLA Challenges: {log['sla_challenges_count']}")
print(f"Loader Responses: {log['loader_responses']}\n")

# Error breakdown
error_types = {}
for err in log['errors']:
    error_types[err['type']] = error_types.get(err['type'], 0) + 1

print("Error Types:")
for err_type, count in sorted(error_types.items()):
    print(f"  {err_type}: {count}")
EOF
```

---

### Extract Non-Zero Memory Values

```bash
# From memory_scan.log
head -50 memory_scan.log

# With grep
grep "0x" memory_scan.log | head -20

# Count total findings
wc -l memory_scan.log
```

---

### Check Device Response Times

```bash
python3 << 'EOF'
import json
from datetime import datetime

with open('sla_response_log.json') as f:
    log = json.load(f)

if log['responses']:
    responses = log['responses']
    times = []
    
    for i in range(1, len(responses)):
        t1 = datetime.fromisoformat(responses[i-1]['timestamp'])
        t2 = datetime.fromisoformat(responses[i]['timestamp'])
        elapsed = (t2 - t1).total_seconds() * 1000
        times.append(elapsed)
    
    if times:
        print(f"Average Response Time: {sum(times)/len(times):.2f}ms")
        print(f"Min: {min(times):.2f}ms")
        print(f"Max: {max(times):.2f}ms")
EOF
```

---

## Diagnostic Options

### Enable All Diagnostics

```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --enable-diagnostics \
    --diagnostic-log full_diags.json \
    --log-file memory_results.log \
    --verbose
```

### Custom Diagnostic Log Location

```bash
python3 a53_sla_ripper/sla_ripper.py scan-memory \
    --diagnostic-log /tmp/my_diagnostics.json
```

### Disable Diagnostics (if not needed)

```bash
# Note: Diagnostics are enabled by default
# To disable, would require code modification or use without --enable-diagnostics
```

---

## Interpreting Results

### Good Sign Indicators

✓ `status: "ack"` - Device accepted command  
✓ `errors_count: 0` - No protocol errors  
✓ `loader_responses: success: true` - Loader loaded  
✓ Consistent response times  
✓ Few skipped regions  

### Warning Indicators

⚠ Multiple 0x04 errors - Device returning non-standard responses  
⚠ High timeout count - Connection instability  
⚠ Many skipped regions - Honey pot or protected area  
⚠ Sporadic NAK responses - Device communication issues  

### Error Scenarios

✗ All 0x04 errors - Loader not compatible or device issue  
✗ Immediate disconnection - Device watchdog timeout  
✗ NAK for all commands - Authentication required  
✗ Empty response data - USB communication failure  

---

## Performance Metrics

### Expected Timing

| Operation | Duration | Notes |
|-----------|----------|-------|
| NOP heartbeat | <100ms | Keep-alive test |
| Configure cmd | 100-500ms | Device initialization |
| Single peek (4 bytes) | 10-50ms | With 10ms safety delay |
| Full 512KB scan | ~43 min | At 10ms per 4-byte read |

### Optimization Tips

1. **Error Rate High?** Check device temperature, USB cable
2. **Scan Too Slow?** Consider larger step size (--step 8)
3. **Many Skips?** Focus on specific address range
4. **Repeated Errors?** Try different loader or reset device

---

## Integration Examples

### Python Integration

```python
from a53_sla_ripper.sla_ripper import QFPROMExtractor

scanner = QFPROMExtractor(
    enable_diagnostics=True,
    diagnostic_log="my_scan.json"
)

# Scanner automatically logs:
# - USB errors with error codes
# - Device responses
# - SLA challenges (if received)
# - Connection summary

results = scanner.scan_memory(0x00700000, 0x00800000)

# Access diagnostic data
print(scanner.sla_logger.get_connection_summary())
```

---

## Support Commands

### View Latest Errors

```bash
tail -f sla_response_log.json | python3 -m json.tool
```

### Count Error Types

```bash
grep '"type"' sla_response_log.json | sort | uniq -c
```

### Extract Timestamps

```bash
python3 -c "
import json
with open('sla_response_log.json') as f:
    log = json.load(f)
    for err in log['errors'][:5]:
        print(f\"{err['timestamp']}: {err['type']}\")
"
```

### Real-time Monitoring

```bash
# Watch scan progress
watch -n 2 'echo \"Results: $(wc -l < memory_scan.log)\"; echo \"Errors: $(jq .errors_count sla_response_log.json)\"; echo \"Last update: $(date)\"'
```

---

## File Locations

| File | Purpose | Format |
|------|---------|--------|
| `memory_scan.log` | Non-zero memory values | Text (one per line) |
| `sla_response_log.json` | Complete diagnostics | JSON |
| `sla_challenge_vault.hex` | SLA challenges | Hex (appended) |

---

**Diagnostics v1.3** | Oppo A53 Device Recovery Tool  
Comprehensive logging and error recovery for authorized device analysis
