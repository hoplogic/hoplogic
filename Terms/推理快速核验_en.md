# VerifyFast (Rapid Inference Verification)

Perform rapid three-stage auditing of LLM-generated reasoning outputs (factor decomposition → fact checking → logic verification), using deterministic scoring formulas to quantify credibility and output structured reports.

## Core Concept

LLM hallucinations fall into two categories: **factual hallucinations** (stating falsehoods) and **reasoning hallucinations** (illogical reasoning). VerifyFast does not rely on LLM self-evaluation scoring, but instead:

1. First uses LLM for **error detection** (Phase 1-3), outputting structured error lists
2. Then uses **deterministic formulas** (Phase 4) to calculate scores directly from error counts, preventing LLM from inflating scores during the scoring phase

## Three-Stage Audit Protocol

```
context_input + model_output
        |
        v
  Phase 1: Factor Decomposition
  - Extract atomic facts (claims, max 5)
  - Extract reasoning chains (deductions)
        |
    ┌────┴────┐
    v         v
Phase 2    Phase 3
Fact Check    Logic Check
    |         |
    v         v
factual    logic
_errors    _errors
    └────┬────┘
         v
  Phase 4: Deterministic Scoring
  credit_score = f(high_count, low_count)
```

### Three-Level Error Classification Standard

| Level | Meaning | Action |
|------|------|------|
| Contradiction | Directly conflicts with context_input (opposite numbers, reversed direction) | Report as error |
| Unsupported | No mention in context_input, cannot be reasonably inferred | Report as error |
| Reasonable Inference | Can be inductively derived from existing data in context_input | **Not counted as error** |

### Severity Determination

| Severity | Fact Type | Logic Type |
|----------|--------|--------|
| **High** | Opposite direction from context_input, or numerical deviation >10% with opposite direction, sufficient to change core conclusions | Causal direction completely reversed, sycophancy causing factual directional distortion, sufficient to change core conclusions |
| **Low** | Numerical deviation ≤10% with consistent direction, unsupported qualitative evaluations, overgeneralization | Overgeneralization, missing intermediate steps but correct conclusion direction, concept substitution without changing conclusion direction |

### Deterministic Scoring Formula

```
High >= 3           -> 1 point (completely untrustworthy)
High 1-2            -> 2 points (basically untrustworthy)
Low >= 2, High == 0 -> 3 points (boundary, cannot accurately determine)
Low == 1, High == 0 -> 4 points (basically no problem)
No errors           -> 5 points (definitely no problem)
```

Scoring parameters are centrally managed in `strategy.yaml`, with Hop.py only handling execution orchestration.

## Zone-Based Evaluation Framework

### Why Not Use Exact Match for Accuracy Measurement

The 5-level scoring appears precise, but LLM auditing itself has uncertainty. In practical applications, **users don't care about the difference between 1 and 2 points, but rather "can this report be trusted?"**. Therefore, the 5-level scoring is consolidated into three bands:

| Band | Score Range | Meaning | User Decision |
|----|------|------|----------|
| **BAD** | 1-2 | Untrustworthy, serious errors exist | Reject/manual review |
| **MID** | 3 | Boundary, cannot determine | Use with caution, need additional information |
| **GOOD** | 4-5 | Trustworthy, no serious issues | Can be directly adopted |

### Three Types of Deviation Severity

| Deviation Type | Example | Severity | Explanation |
|----------|------|--------|------|
| **Within-band deviation** | Expected 1 actual 2, or expected 4 actual 5 | Acceptable | User decision unchanged |
| **Boundary deviation** | Expected 3 actual 4, or expected 4 actual 3 | Tolerable | MID zone is inherently gray area |
| **Cross-band confusion** | Expected 1-2 actual 4-5, or vice versa | **Fatal** | User decision completely reversed |

**Cross-band confusion (BAD<->GOOD Confusion) is the only unacceptable error**. Judging an untrustworthy report as trustworthy (false negative), or judging a trustworthy report as untrustworthy (false positive), will directly lead to wrong decisions.

### Zone Confusion Matrix

Evaluation uses a 3x3 confusion matrix (rows=expected zone, columns=actual zone):

```
              Actual
              BAD(1-2)  MID(3)  GOOD(4-5)
Expected
  BAD(1-2)      TP_bad    Boundary      Cross-band!
  MID(3)        Boundary      TP_mid    Boundary
  GOOD(4-5)     Cross-band!     Boundary      TP_good
```

Core metric: **Cross-band confusion rate = (BAD->GOOD + GOOD->BAD) / Total**

Target: **Cross-band confusion rate < 5%**

### Baseline Test Results (v3, kimi-full, n=20)

```
              BAD(1-2)  MID(3)  GOOD(4-5)
  BAD(1-2)       8        0        1       <- 1 cross-band case
  MID(3)         0        0        4       <- all boundary deviations
  GOOD(4-5)      0        1        6       <- 1 boundary deviation
```

| Metric | Value |
|------|-----|
| Zone accuracy | 14/20 = 70% |
| Cross-band confusion | 1/20 = 5% |
| Exact match | 10/20 = 50% |
| ±1 match | 18/20 = 90% |

The 1 case of cross-band confusion is #13 (major_factual): expected 2 points, actual 4 points. The LLM downgraded a fact fabrication that should have been High severity to Low, causing the score to jump from BAD zone to GOOD zone.

## LLM Configuration and Profile

### settings.yaml Structure

```yaml
defaults:
  max_tokens: 4000
  temperature: 0.1

llms:
  kimi-k2:
    base_url: "https://antchat.alipay.com/v1"
    model: "Kimi-K2-Instruct-0905"
    inference_engine: "aistudio-vllm"
  qwen3-235b:
    base_url: "https://antchat.alipay.com/v1"
    model: "Qwen3-235B-A22B"

profiles:
  kimi-full:          # Same model execution+verification
    run: kimi-k2
    verify: kimi-k2
  cross-verify:       # Cross-verification: different models
    run: kimi-k2
    verify: qwen3-235b
```

### Profile Meaning

Each profile defines a combination of `run` (execution model) + `verify` (verification model):

| Profile | run | verify | Characteristics |
|---------|-----|--------|------|
| kimi-full | Kimi-K2 | Kimi-K2 | Fast speed, same model may have consistency bias |
| cross-verify | Kimi-K2 | Qwen3-235B | Cross-verification reduces same-model blind spots |

Batch testing specifies which profiles to test via the `--profiles` parameter:

```bash
# Test all profiles
/batchhoptest VerifyFast verify_fast_20.jsonl

# Test specified profiles only
/batchhoptest VerifyFast verify_fast_20.jsonl --profiles kimi-full cross-verify
```

Results JSONL are distinguished by the `profile` field, with analysis grouped by profile for comparison.

### Strategy Configuration and Profile Linkage (Planned)

`strategy.yaml` supports per-profile strategy overrides:

```yaml
defaults:
  params:
    numeric_deviation_threshold: 0.10
    max_errors_per_phase: 3

profiles:
  kimi-full:
    params:
      numeric_deviation_threshold: 0.08   # Stricter threshold
  cross-verify:
    params:
      max_errors_per_phase: 5             # Allow more error output
```

This allows different LLMs to be paired with different audit strategy parameters, for example tightening thresholds when certain models have lenient severity judgments.

## Test Data Specification

### Input JSONL Format

```jsonl
{"id": 1, "tag": "clean", "difficulty": "easy", "description": "...", "context_input": "...", "model_output": "...", "expected_credit_score": 5}
```

### Tag System

| tag | Expected Score | Description | Expected Zone |
|-----|--------|------|--------|
| clean | 5 | Completely faithful to original text | GOOD |
| minor_factual | 4 | One low-severity factual deviation | GOOD |
| minor_logic | 4 | One low-severity logic issue | GOOD |
| multi_minor | 3 | Multiple low-severity errors combined | MID |
| major_factual | 2 | One high-severity factual error | BAD |
| major_logic | 2 | One high-severity logic error | BAD |
| severe_factual | 1 | Multiple high-severity factual errors | BAD |
| severe_logic | 1 | Multiple high-severity logic errors | BAD |
| severe_mixed | 1 | Mixed high-severity factual+logic errors | BAD |
| severe_fabrication | 1 | Large-scale fabrication | BAD |
| sycophancy | 1 | Sycophancy causing directional distortion | BAD |

### Zone Coverage Requirements

Test sets should cover all three zones with reasonable distribution:

| Zone | Recommended Proportion | Description |
|----|----------|------|
| BAD (1-2) | 30-40% | Key coverage, highest cost for cross-band confusion |
| MID (3) | 15-25% | Boundary cases, test gray area handling capability |
| GOOD (4-5) | 35-50% | Baseline coverage, ensure no false positives |

## Known Issues and Optimization Directions

### multi_minor Missed Detection

Current strategy is weak at detecting scenarios with multiple low-severity errors combined (4 cases all scored 1-2 points higher). LLMs tend to give "not an error" judgments for individual errors, causing the cumulative effect of multiple small errors to be ignored.

Possible optimization directions:
- Add multi-error sensitivity prompts in strategy.yaml
- Reduce exemption scope

### Severity Downgrade

In case #13, the LLM judged a fact fabrication that should have been High severity (985 admission rate) as Low. This is the direct cause of cross-band confusion.

Possible optimization directions:
- Add hard constraint in factual severity rules that "fabricated specific numbers" must be judged High
- Consider introducing reverse_verify for secondary verification of severity judgments

### Cross-profile Comparison

After enabling cross-verify profile (cross-verification with different models), observe whether cross-band confusion rate decreases. Severity judgment deviations from different models may compensate for each other.