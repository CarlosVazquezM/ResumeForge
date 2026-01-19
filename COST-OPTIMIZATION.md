# Cost Optimization & Testing Improvements

## Problem
- Multiple failed API calls due to timeouts (6 attempts before success)
- Wasted tokens and cost (~$0.57 USD)
- No way to estimate costs before running
- No dry-run mode for testing

## Solutions Implemented

### 1. ✅ Cost Estimation (`--dry-run` / `--estimate-only`)
Estimate costs **before** making API calls:

```bash
# Estimate cost without calling API
resumeforge parse --fact-resume resume.md --dry-run

# Or use --estimate-only (same thing)
resumeforge parse --fact-resume resume.md --estimate-only
```

**Output:**
```
📊 Cost Estimation:
   Resume size: 38,573 characters
   Input tokens: ~10,413
   Output tokens (est): ~8,192
   Provider: anthropic (claude-sonnet-4-20250514)

💵 Estimated Cost:
   Input:  $0.0312
   Output: $0.1229
   Total:  $0.1541

✅ Dry run complete - no API charges incurred
```

### 2. ✅ Cost Warning Before Execution
When running normally, the CLI now:
- Shows cost estimation first
- Warns if cost > $0.10
- Asks for confirmation before proceeding

### 3. ✅ Improved Timeout Handling
- **Reduced retries**: Timeout errors no longer retry (they're likely to fail again)
- **Better error messages**: Clear guidance when timeouts occur
- **Only retry rate limits**: Retries only on rate limit errors, not timeouts

### 4. ✅ Cost Estimator Module
New `utils/cost_estimator.py` with:
- Pricing for all supported providers/models
- Accurate token counting
- Cost breakdown (input vs output)

## Usage Examples

### Test Without Spending Money
```bash
# See cost estimate only
resumeforge parse -f resume.md --dry-run
```

### Run with Cost Confirmation
```bash
# Shows estimate, asks for confirmation if > $0.10
resumeforge parse -f resume.md -o output.json
```

### Development Testing
For testing during development:
1. Use `--dry-run` to test prompts and configuration
2. Use smaller sample resumes for initial testing
3. Only run full parsing when ready

## Cost Savings

**Before:**
- 6 failed attempts × ~$0.10 each = ~$0.60 wasted
- No visibility into costs

**After:**
- `--dry-run` shows cost upfront (free)
- Cost warning prevents accidental expensive runs
- Better timeout handling reduces wasted retries

## Best Practices

1. **Always use `--dry-run` first** when testing new resumes
2. **Check cost estimation** before running on large documents
3. **Use smaller test files** during development
4. **Monitor Anthropic dashboard** for actual usage

## Future Improvements

- [ ] Resume chunking for very large documents (>50K chars)
- [ ] Sample data mode for testing without real resumes
- [ ] Cost tracking/logging per run
- [ ] Automatic fallback to cheaper models for large documents
