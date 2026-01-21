# Performance Optimization Guide

**Date:** January 2025  
**Status:** Phase 8 - Testing & Refinement

---

## Overview

This document outlines performance optimization opportunities and recommendations for ResumeForge. As the system grows and handles larger job descriptions and evidence card sets, performance becomes critical for user experience.

---

## Current Performance Characteristics

### Pipeline Execution Time

Based on typical usage patterns:

- **Small JD** (< 500 words, 5-10 evidence cards): ~2-3 minutes
- **Medium JD** (500-1000 words, 10-20 evidence cards): ~4-6 minutes
- **Large JD** (> 1000 words, 20+ evidence cards): ~8-12 minutes

### Cost per Resume Generation

- **Average cost**: $0.10 - $0.50 per resume (varies by JD complexity)
- **Provider breakdown**:
  - JD Analyst (Claude Sonnet 4): ~$0.02-0.05
  - Evidence Mapper (Claude Sonnet 4): ~$0.03-0.08
  - Resume Writer (GPT-4o): ~$0.05-0.30
  - Auditor (Claude Sonnet 4 + Gemini Flash): ~$0.01-0.05

---

## Optimization Opportunities

### 1. Parallel Agent Execution

**Current State:** Agents execute sequentially  
**Opportunity:** Some agents can run in parallel

**Recommendation:**
- **ATS Scoring** and **Truth Auditing** can run in parallel (they don't depend on each other)
- **Evidence Mapping** can start as soon as JD Analysis completes (no need to wait for full role_profile)

**Implementation:**
```python
# In orchestrator.py
async def _execute_parallel_auditing(self, blackboard: Blackboard) -> Blackboard:
    """Execute ATS scoring and truth auditing in parallel."""
    import asyncio
    
    async def ats_score():
        ats_agent = self.agents.get("ats_scorer")
        return await ats_agent.execute_async(blackboard)
    
    async def truth_audit():
        truth_agent = self.agents.get("truth_auditor")
        return await truth_agent.execute_async(blackboard)
    
    ats_result, truth_result = await asyncio.gather(ats_score(), truth_audit())
    # Merge results into blackboard
    return merged_blackboard
```

**Expected Impact:** 20-30% reduction in total pipeline time

---

### 2. Caching Strategy

**Current State:** No caching  
**Opportunity:** Cache expensive operations

**Recommendations:**

#### A. Evidence Card Caching
- Cache parsed evidence cards in memory (they don't change frequently)
- Use file modification time to invalidate cache

```python
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def load_evidence_cards_cached(evidence_path: str, mtime: float) -> list[EvidenceCard]:
    """Load evidence cards with caching based on file mtime."""
    return load_evidence_cards(evidence_path)
```

#### B. JD Analysis Caching
- Cache role profiles for identical job descriptions
- Use hash of JD text as cache key
- Store in local SQLite database or JSON file

```python
import hashlib
import json

def get_cached_role_profile(jd_text: str) -> RoleProfile | None:
    """Get cached role profile if JD was analyzed before."""
    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
    cache_file = Path(f".cache/jd_analysis/{jd_hash}.json")
    if cache_file.exists():
        return RoleProfile.model_validate_json(cache_file.read_text())
    return None
```

**Expected Impact:** 50-80% reduction for repeated JDs

---

### 3. Token Optimization

**Current State:** Full context sent to each agent  
**Opportunity:** Reduce token usage per agent

**Recommendations:**

#### A. Evidence Card Filtering
- Only send selected evidence cards to Writer (not all cards)
- Pre-filter evidence cards before sending to Evidence Mapper

```python
# In orchestrator._preprocess()
def filter_relevant_evidence_cards(
    all_cards: list[EvidenceCard],
    jd_keywords: list[str]
) -> list[EvidenceCard]:
    """Filter evidence cards that might be relevant to JD."""
    # Simple keyword matching or use embedding similarity
    relevant = []
    for card in all_cards:
        card_text = f"{card.project} {card.raw_text}".lower()
        if any(kw.lower() in card_text for kw in jd_keywords):
            relevant.append(card)
    return relevant
```

#### B. Prompt Optimization
- Use shorter, more focused prompts
- Remove redundant context from prompts
- Use structured outputs more efficiently

**Expected Impact:** 20-40% reduction in token costs

---

### 4. Provider Selection Optimization

**Current State:** Fixed provider assignments  
**Opportunity:** Dynamic provider selection based on cost/speed tradeoff

**Recommendations:**

#### A. Fast Path for Simple Tasks
- Use Gemini Flash for simple ATS scoring (faster, cheaper)
- Use Claude Haiku for preliminary JD analysis (faster, cheaper)
- Only use expensive models when needed

#### B. Fallback Strategy
- Try faster/cheaper provider first
- Fall back to more capable provider if quality is insufficient

**Expected Impact:** 30-50% cost reduction for simple cases

---

### 5. Incremental Processing

**Current State:** Full pipeline restart on audit failure  
**Opportunity:** Incremental updates instead of full restart

**Recommendations:**

#### A. Targeted Revisions
- Only re-run Writer for sections with violations
- Don't re-analyze JD or re-map evidence if unchanged

```python
def prepare_targeted_revision(
    blackboard: Blackboard,
    violations: list[TruthViolation]
) -> Blackboard:
    """Prepare revision instructions for only affected sections."""
    affected_sections = {v.bullet_id.split('-')[0] for v in violations}
    # Only revise affected sections
    return blackboard
```

**Expected Impact:** 40-60% reduction in retry time

---

### 6. Batch Processing

**Current State:** One resume at a time  
**Opportunity:** Batch processing for multiple job descriptions

**Recommendations:**

#### A. Parallel Resume Generation
- Process multiple JDs simultaneously (if API rate limits allow)
- Share evidence cards across all runs (load once)

```python
async def generate_multiple_resumes(
    jds: list[tuple[Path, str]],
    evidence_cards: list[EvidenceCard]
) -> list[Blackboard]:
    """Generate multiple resumes in parallel."""
    tasks = [
        generate_resume(jd_path, title, evidence_cards)
        for jd_path, title in jds
    ]
    return await asyncio.gather(*tasks)
```

**Expected Impact:** 2-4x throughput for batch operations

---

## Profiling Recommendations

### 1. Add Timing Instrumentation

```python
import time
from contextlib import contextmanager

@contextmanager
def timed_operation(operation_name: str):
    """Context manager for timing operations."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info(f"{operation_name} took {elapsed:.2f}s")
```

### 2. Token Counting per Agent

```python
def log_token_usage(agent_name: str, input_tokens: int, output_tokens: int):
    """Log token usage for cost tracking."""
    logger.info(
        f"{agent_name} token usage",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens
    )
```

### 3. Performance Metrics Collection

```python
class PerformanceMetrics:
    """Collect performance metrics for analysis."""
    
    def __init__(self):
        self.agent_times: dict[str, list[float]] = {}
        self.token_counts: dict[str, dict[str, int]] = {}
        self.costs: dict[str, float] = {}
    
    def record_agent_execution(self, agent_name: str, duration: float):
        """Record agent execution time."""
        if agent_name not in self.agent_times:
            self.agent_times[agent_name] = []
        self.agent_times[agent_name].append(duration)
```

---

## Implementation Priority

### Phase 1 (Quick Wins)
1. ✅ **Evidence Card Caching** - Easy to implement, high impact
2. ✅ **Token Optimization** - Filter evidence cards before sending
3. ✅ **Performance Metrics** - Add timing instrumentation

### Phase 2 (Medium Effort)
4. ⏭️ **Parallel Auditing** - ATS and Truth audit in parallel
5. ⏭️ **JD Analysis Caching** - Cache role profiles
6. ⏭️ **Incremental Revisions** - Only revise affected sections

### Phase 3 (Advanced)
7. ⏭️ **Dynamic Provider Selection** - Cost/speed optimization
8. ⏭️ **Batch Processing** - Multiple resumes in parallel
9. ⏭️ **Async Pipeline** - Full async/await implementation

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Pipeline Duration**
   - Total time
   - Per-agent time
   - Retry count and time

2. **Token Usage**
   - Input tokens per agent
   - Output tokens per agent
   - Total tokens per resume

3. **Cost per Resume**
   - Cost breakdown by provider
   - Cost per agent
   - Average cost per resume

4. **Success Rate**
   - First-pass success rate
   - Retry success rate
   - Audit pass rate

### Recommended Tools

- **cProfile** - Python profiling
- **memory_profiler** - Memory usage tracking
- **py-spy** - Real-time profiling
- **Custom logging** - Performance metrics collection

---

## Expected Overall Impact

If all optimizations are implemented:

- **Execution Time**: 40-60% reduction
- **Cost per Resume**: 30-50% reduction
- **Throughput**: 2-4x improvement for batch operations
- **User Experience**: Faster feedback, lower costs

---

## Next Steps

1. **Add Performance Instrumentation** (Phase 8)
   - Add timing to orchestrator
   - Log token usage per agent
   - Track costs per run

2. **Implement Quick Wins** (Post-Phase 8)
   - Evidence card caching
   - Token optimization
   - Performance metrics dashboard

3. **Measure Impact** (Post-Phase 8)
   - Run benchmarks before/after
   - Collect real-world usage data
   - Identify bottlenecks

4. **Iterate** (Ongoing)
   - Monitor performance metrics
   - Implement Phase 2 optimizations
   - Consider Phase 3 for scale

---

**Note:** Performance optimization should be data-driven. Implement instrumentation first, then optimize based on actual usage patterns and bottlenecks.
