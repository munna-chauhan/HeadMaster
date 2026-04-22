# Skill-Creator Integration Analysis for HeadMaster

**Date:** 2026-04-22  
**Analyst:** Principal Engineer Review  
**Objective:** Identify valuable patterns from skill-creator for HeadMaster integration

---

## Executive Summary

skill-creator is an **evaluation-driven skill development framework** with sophisticated benchmarking, blind comparison, and iterative improvement workflows. HeadMaster can adopt **7 high-value patterns** to improve skill quality, reduce manual testing overhead, and automate skill optimization.

**Highest Impact Integrations:**
1. ⭐⭐⭐ Quantitative eval framework for HeadMaster skills (test /plan, /design, /execute)
2. ⭐⭐⭐ Benchmark aggregation for performance regression detection
3. ⭐⭐ Blind review system for isolated agent validation
4. ⭐⭐ Description optimization for skill triggering accuracy

---

## What Is skill-creator?

### Core Mission
**Build → Test → Benchmark → Improve → Repeat** — iterative skill development with quantitative validation.

### Workflow
```
User: "Create skill for X"
  ↓
AI: Drafts skill, writes test prompts
  ↓
AI: Spawns parallel subagents (with-skill + baseline)
  ↓
AI: Grades outputs, generates benchmark.json
  ↓
AI: Opens HTML viewer (qualitative + quantitative)
  ↓
User: Reviews outputs, leaves feedback
  ↓
AI: Improves skill based on feedback
  ↓
LOOP until satisfied
  ↓
AI: Optimizes skill description for triggering
```

### Key Innovations

#### 1. **Parallel With/Without Baseline**
```python
# Spawn in SAME turn
Agent(with_skill, prompt, save_to="eval-0/with_skill/")
Agent(without_skill, prompt, save_to="eval-0/without_skill/")

# Compare deltas: pass_rate, time, tokens
delta = {
    "pass_rate": +50%,
    "time": +13s,
    "tokens": +12K
}
```

**Value:** Proves skill actually improves outcomes vs baseline.

#### 2. **Quantitative Assertions**
```json
{
  "eval_id": 1,
  "prompt": "Extract table from PDF",
  "assertions": [
    "Output is a CSV file",
    "CSV has 3 columns: name, email, phone",
    "CSV has exactly 12 rows",
    "No rows have missing values"
  ]
}
```

**Grading:**
```json
{
  "expectations": [
    {"text": "Output is a CSV file", "passed": true, "evidence": "..."},
    {"text": "CSV has 3 columns", "passed": false, "evidence": "Only 2 columns found"}
  ],
  "summary": {"pass_rate": 0.75}
}
```

**Value:** Objective, automated pass/fail → no manual inspection required.

#### 3. **Benchmark Aggregation**
```python
# Runs 3x per config per eval → aggregate
aggregate_benchmark.py iteration-N/ --skill-name my-skill

# Output: benchmark.json
{
  "configurations": [
    {
      "name": "with_skill",
      "pass_rate": {"mean": 0.85, "stddev": 0.12},
      "time_seconds": {"mean": 23.4, "stddev": 2.1},
      "total_tokens": {"mean": 12450, "stddev": 890}
    },
    {
      "name": "without_skill",
      "pass_rate": {"mean": 0.35, "stddev": 0.15},
      "time_seconds": {"mean": 18.2, "stddev": 3.5}
    }
  ],
  "delta": {
    "pass_rate": "+143%",
    "time_seconds": "+28%",
    "total_tokens": "+65%"
  }
}
```

**Value:** Variance detection catches flaky tests. Mean ± stddev shows consistency.

#### 4. **HTML Eval Viewer**
```python
python eval-viewer/generate_review.py \
  workspace/iteration-N \
  --skill-name my-skill \
  --benchmark benchmark.json \
  --previous-workspace iteration-1

# Opens browser with 2 tabs:
# - Outputs: side-by-side qualitative review + feedback textbox
# - Benchmark: quantitative pass rates, timing, token usage
```

**User experience:**
- Click through test cases with prev/next
- See diff vs previous iteration
- Leave feedback (auto-saves to feedback.json)
- See formal grades (assertion pass/fail)

**Value:** Structured human review replaces ad-hoc manual testing.

#### 5. **Grader Agent (Independent Verification)**
```markdown
Role: Evaluate expectations against transcript + outputs

Process:
1. Read transcript completely
2. Examine output files (not just what transcript says)
3. Evaluate each assertion with evidence
4. Extract implicit claims and verify them
5. Critique evals themselves (are assertions discriminating?)
6. Write grading.json
```

**Key insight:**
> "A passing grade on a weak assertion is worse than useless — it creates false confidence."

Grader flags **non-discriminating assertions** (always pass regardless of skill quality).

#### 6. **Blind Comparison System**
```python
# agents/comparator.md
Agent(
  prompt="""
  Two outputs A and B for same task.
  Which is better? Why?
  (You don't know which used the skill)
  """
)

# agents/analyzer.md (post-hoc)
Agent(
  prompt="""
  Winner was A (new skill).
  Read both skills + transcripts.
  Why did A win? What should B change?
  """
)
```

**Value:** Eliminates confirmation bias. Comparator judges quality blind, analyzer explains why.

#### 7. **Description Optimization Loop**
```python
# Generate 20 trigger eval queries
evals = [
  {"query": "realistic user prompt", "should_trigger": true},
  {"query": "near-miss prompt", "should_trigger": false}
]

# Run optimization
python -m scripts.run_loop \
  --eval-set trigger-eval.json \
  --skill-path my-skill/ \
  --max-iterations 5

# Splits 60% train / 40% test
# Evaluates current description (3 runs per query)
# Proposes improvements based on failures
# Re-evaluates on both train + test
# Selects best by test score (not train → avoids overfitting)
```

**Output:** Optimized description with trigger accuracy metrics.

---

## HeadMaster Integration Opportunities

### Priority 1: Quantitative Skill Evaluation ⭐⭐⭐

**Problem:** HeadMaster skills untested. Changes may break existing workflows.

**Solution:** Adopt skill-creator eval framework.

#### Implementation Plan

**Step 1: Create eval test suites**

```
tests/skills/
├── plan/
│   ├── evals.json
│   └── fixtures/
├── design/
│   ├── evals.json
│   └── fixtures/
├── execute/
│   ├── evals.json
│   └── fixtures/
└── navigate/
    └── evals.json
```

**evals.json structure:**
```json
{
  "skill_name": "plan",
  "evals": [
    {
      "id": 1,
      "name": "lite-feature-discovery",
      "prompt": "Add rate limiting to /api/v1/users endpoint - 100 req/min per IP",
      "expected_output": "PRD with 6 sections (lite tier)",
      "assertions": [
        "PRD.md file created in docs/features/{slug}/planning/",
        "PRD has exactly 6 sections (lite tier detected)",
        "Section 3 'Functional Requirements' mentions rate limiting",
        "Section 4 'Technical Approach' mentions Redis or similar",
        "PRD Status: APPROVED appears at top"
      ],
      "files": []
    },
    {
      "id": 2,
      "name": "full-feature-multi-repo",
      "prompt": "Migrate Elasticsearch 5→9 across content-publication, elasticsearch-writer, distribution-services",
      "expected_output": "PRD with 14 sections (full tier)",
      "assertions": [
        "PRD.md has 14 sections (full tier detected)",
        "Section 9 'Rollback Strategy' exists and non-empty",
        "Section 12 'Repos & Owners' lists 3+ repos",
        "Complexity tier in loop_state.json is 'full'"
      ],
      "files": ["input/FEATURE_INPUT.md"]
    }
  ]
}
```

**Step 2: Create grader script**

```python
# scripts/grade_skill_run.py
# Reads transcript + outputs, evaluates assertions, writes grading.json
# Reuses skill-creator's grader agent pattern
```

**Step 3: Create benchmark runner**

```bash
# scripts/run_skill_benchmark.py
python scripts/run_skill_benchmark.py \
  --skill plan \
  --eval-set tests/skills/plan/evals.json \
  --iterations 3 \
  --output benchmarks/plan/

# Spawns 3 runs per eval, aggregates, generates benchmark.json
```

**Step 4: Add to CI/CD**

```yaml
# .github/workflows/skill-tests.yml
on: [push, pull_request]
jobs:
  test-skills:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/run_skill_benchmark.py --skill plan --iterations 1
      - run: python scripts/run_skill_benchmark.py --skill design --iterations 1
      - run: python scripts/run_skill_benchmark.py --skill execute --iterations 1
      - run: python scripts/check_benchmark_regression.py benchmarks/
```

**Value:**
- Catch skill regressions before merge
- Quantify skill improvements objectively
- Build test suite incrementally (start with 2-3 evals per skill)

---

### Priority 2: Benchmark Regression Detection ⭐⭐⭐

**Problem:** Skill changes may improve one scenario but break another. No way to detect.

**Solution:** Adopt aggregate_benchmark.py pattern.

#### Implementation

**scripts/check_benchmark_regression.py:**
```python
#!/usr/bin/env python3
"""Check for performance regression vs baseline benchmark.

Usage:
    python scripts/check_benchmark_regression.py benchmarks/plan/
    
Compares current run vs benchmarks/plan/baseline.json.
Fails CI if pass_rate drops >10% or time increases >50%.
"""

def check_regression(current: dict, baseline: dict) -> list:
    regressions = []
    
    # Pass rate regression
    current_pr = current["pass_rate"]["mean"]
    baseline_pr = baseline["pass_rate"]["mean"]
    if current_pr < baseline_pr * 0.9:  # 10% drop
        regressions.append(f"Pass rate dropped {baseline_pr - current_pr:.2%}")
    
    # Time regression
    current_t = current["time_seconds"]["mean"]
    baseline_t = baseline["time_seconds"]["mean"]
    if current_t > baseline_t * 1.5:  # 50% increase
        regressions.append(f"Time increased {(current_t / baseline_t - 1):.1%}")
    
    return regressions
```

**Workflow:**
```bash
# Before skill change
python scripts/run_skill_benchmark.py --skill plan --iterations 3
cp benchmarks/plan/benchmark.json benchmarks/plan/baseline.json

# After skill change
python scripts/run_skill_benchmark.py --skill plan --iterations 3
python scripts/check_benchmark_regression.py benchmarks/plan/

# Output:
# ✅ No regressions detected
# OR
# ❌ Regressions:
#    - Pass rate dropped 15% (85% → 70%)
#    - Time increased 80% (12s → 22s)
```

**Value:**
- Prevents accidental breakage
- Quantifies tradeoffs (time vs quality)
- Tracks skill evolution over time

---

### Priority 3: Blind Review for Isolated Agents ⭐⭐

**Problem:** HeadMaster claims isolated agent reviews. How to verify isolation is effective?

**Solution:** Adopt blind comparison system.

#### Use Case: Validate Review Agent Isolation

**Hypothesis:** Review agent isolation catches bugs developer agent missed.

**Test:**
```python
# Spawn 2 review agents for same git diff
Agent(
  subagent_type="review-agent",
  isolation="worktree",
  prompt="Review git diff. You know: nothing (blind)"
)

Agent(
  subagent_type="developer",  # Has full context
  prompt="Review your own git diff. You know: TDD, implementation decisions"
)

# Blind comparator judges which review is better
Agent(
  subagent_type="comparator",
  prompt="""
  Two code reviews A and B for same diff.
  Which catches more real issues? Which is more helpful?
  """
)

# Analyzer unblids results
Agent(
  subagent_type="analyzer",
  prompt="""
  Winner: A (isolated review agent)
  
  Analysis:
  - Isolated reviewer caught variable naming inconsistency
  - Contextual reviewer assumed name was intentional (knew why)
  - Isolated reviewer flagged missing null check
  - Contextual reviewer knew upstream validation exists
  
  Verdict: Isolation effective for surface bugs, misses architectural context
  """
)
```

**Value:**
- Empirically validate isolation effectiveness
- Identify when isolation helps vs hurts
- Tune review agent instructions based on findings

---

### Priority 4: Description Optimization ⭐⭐

**Problem:** Skills may not trigger when users need them. No data on triggering accuracy.

**Solution:** Adopt description optimization loop.

#### Implementation

**Step 1: Generate trigger evals**

```json
// tests/skills/plan/trigger-evals.json
[
  {
    "query": "we need to add SSO login to the app, thinking SAML + Google Workspace integration, probably touches auth-service and frontend, what do you think?",
    "should_trigger": true,
    "reason": "Multi-repo feature needing requirements + design"
  },
  {
    "query": "quick fix - the /healthcheck endpoint is returning 500, can you add a try/catch?",
    "should_trigger": false,
    "reason": "Hotfix, not a planned feature"
  },
  {
    "query": "boss wants a dashboard showing user signups by day for last 30 days, needs to be done by EOD",
    "should_trigger": true,
    "reason": "New feature (dashboard) even if urgent"
  }
]
```

**Step 2: Run optimization**

```bash
python -m scripts.optimize_skill_description \
  --skill plan \
  --eval-set tests/skills/plan/trigger-evals.json \
  --max-iterations 5

# Output:
# Iteration 1: train 15/20 (75%), test 6/8 (75%)
# Iteration 2: train 17/20 (85%), test 7/8 (88%)
# Iteration 3: train 18/20 (90%), test 7/8 (88%) ← selected (best test score)
# 
# Best description:
# "Plan technical features requiring requirements discovery, design, and implementation across single or multiple repos. Use when: user describes a new feature, enhancement needing architecture decisions, migrations, or requests 'help me plan X'. ALWAYS trigger for phrases like 'add feature', 'build', 'implement', 'migrate', even if phrased as questions. DO NOT trigger for: hotfixes, quick config changes, single-file edits."
```

**Value:**
- Data-driven skill triggering improvements
- Catches under-triggering (skill useful but not used)
- Avoids over-triggering (skill used inappropriately)

---

### Priority 5: HTML Eval Viewer for Skill Testing ⭐

**Problem:** Manual skill testing tedious. No structured review process.

**Solution:** Integrate eval-viewer for skill developers.

#### Workflow

```bash
# Skill developer tests /plan skill
python scripts/run_skill_benchmark.py \
  --skill plan \
  --eval-set tests/skills/plan/evals.json \
  --output workspace/plan-test/

# Opens HTML viewer
python skill-creator/eval-viewer/generate_review.py \
  workspace/plan-test/ \
  --skill-name plan \
  --benchmark workspace/plan-test/benchmark.json

# Browser opens → 2 tabs
# Outputs: shows PRD.md inline, previous iteration diff, formal grades
# Benchmark: pass rate 85%, time 8.2s, tokens 45K
```

**User reviews:**
- Clicks through 5 test cases
- Leaves feedback: "lite tier misclassified, should be standard"
- Clicks "Submit All Reviews" → saves feedback.json

**AI reads feedback, improves skill, reruns tests**

**Value:**
- Structured skill development workflow
- Faster iteration cycles
- Qualitative + quantitative feedback in one UI

---

### Priority 6: Grader Agent Pattern ⭐

**Problem:** Assertion quality unknown. May pass for wrong reasons.

**Solution:** Adopt grader agent "critique the evals" pattern.

#### Implementation

**Grader responsibilities:**
1. Grade assertions as pass/fail
2. **Critique assertions themselves**
   - Non-discriminating (always pass regardless of quality)
   - Superficial (filename correct but content wrong)
   - Unchecked outcomes (important result not asserted)

**Example:**
```json
{
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "PRD.md exists",
        "reason": "Empty file also passes — check file has >100 lines"
      },
      {
        "reason": "No assertion checks Section 3 'Functional Requirements' is non-empty. I observed a blank section that went uncaught."
      }
    ],
    "overall": "Assertions check structure but not content. Add content verification."
  }
}
```

**Value:**
- Self-improving test suite
- Catches bad assertions before they hide bugs
- Builds discriminating test suite over time

---

### Priority 7: Analyzer Agent for Pattern Detection ⭐

**Problem:** Aggregate metrics hide patterns (flaky tests, outliers, non-discriminating assertions).

**Solution:** Adopt analyzer agent pattern.

#### Implementation

**Analyzer reads benchmark.json, surfaces patterns:**

```json
{
  "analyst_notes": [
    "Assertion 'PRD.md exists' passes 100% in both with_skill and without_skill — not discriminating",
    "Eval 3 shows high variance (pass_rate 66% ± 47%) — run 2 failed, may be flaky",
    "Without-skill runs consistently fail on 'Section 9 Rollback Strategy' (0% pass rate)",
    "Skill adds 6.5s execution time but improves pass rate by 42%",
    "Token usage 35% higher with skill, primarily from TDD section loading"
  ]
}
```

**Actionable insights:**
- Remove non-discriminating assertions
- Investigate flaky eval 3
- Skill clearly adds value for rollback planning
- Token increase acceptable given quality improvement

**Value:**
- Automated pattern detection saves manual analysis
- Identifies test quality issues
- Justifies skill existence with data

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. ✅ Copy skill-creator scripts/ to HeadMaster
   - `aggregate_benchmark.py`
   - `package_skill.py` (already useful)
   - Adapt for HeadMaster directory structure

2. ✅ Create eval schema
   - `tests/skills/evals-schema.json`
   - Document assertion patterns

3. ✅ Build grader script
   - `scripts/grade_skill_run.py`
   - Reads transcript + outputs
   - Evaluates assertions
   - Writes grading.json

### Phase 2: Pilot Skill Tests (Week 3-4)
4. ✅ Create /plan skill evals
   - 3 test cases (lite, standard, full)
   - 5 assertions per case
   - Run manually, validate grading

5. ✅ Create benchmark runner
   - `scripts/run_skill_benchmark.py`
   - Spawns subagents, aggregates, generates benchmark.json

6. ✅ Test full workflow
   - Run benchmark
   - Review results
   - Iterate on assertions

### Phase 3: Expand Coverage (Month 2)
7. ✅ Add /design skill evals (4 cases)
8. ✅ Add /execute skill evals (5 cases)
9. ✅ Add /navigate skill evals (3 cases)
10. ✅ Integrate HTML viewer

### Phase 4: Automation (Month 3)
11. ✅ Add CI/CD skill tests
12. ✅ Implement regression detection
13. ✅ Baseline tracking
14. ✅ Performance dashboards

### Phase 5: Advanced Features (Month 4)
15. ✅ Description optimization
16. ✅ Blind comparison system
17. ✅ Analyzer agent integration

---

## Integration Patterns

### Pattern 1: Eval-Driven Skill Development

**Before (HeadMaster today):**
```
1. Write skill
2. Test manually (ad-hoc prompts)
3. Fix issues found
4. Hope it works in production
```

**After (skill-creator pattern):**
```
1. Write skill + eval suite (5 test cases)
2. Run benchmark (3 iterations per case)
3. Review HTML viewer (qualitative + quantitative)
4. Iterate based on feedback.json
5. Optimize description for triggering
6. Ship with 85%+ pass rate
```

### Pattern 2: Regression Detection

**Before:**
```
1. Change skill
2. Manual smoke test
3. Merge
4. User reports breakage
```

**After:**
```
1. Change skill
2. Run: python scripts/check_benchmark_regression.py
3. CI fails if pass_rate < baseline - 10%
4. Fix regression before merge
```

### Pattern 3: Baseline Comparison

**skill-creator pattern:**
```python
# For new skill
baseline = "without_skill"  # No skill at all

# For improving existing skill
baseline = "old_skill"  # Before changes
```

**HeadMaster adaptation:**
```python
# For skill improvement
baseline = "before_change"  # Snapshot old version
test = "after_change"  # Current version

# Compare delta
delta = {
    "pass_rate": "+8%",
    "time": "-2.1s",
    "tokens": "+3K"
}
```

---

## File Structure After Integration

```
HeadMaster/
├── scripts/
│   ├── aggregate_benchmark.py       # From skill-creator
│   ├── grade_skill_run.py           # Adapted grader
│   ├── run_skill_benchmark.py       # Benchmark runner
│   ├── check_benchmark_regression.py # CI check
│   └── optimize_skill_description.py # Description loop
├── tests/
│   └── skills/
│       ├── plan/
│       │   ├── evals.json
│       │   └── fixtures/
│       ├── design/
│       ├── execute/
│       └── navigate/
├── benchmarks/
│   ├── plan/
│   │   ├── baseline.json
│   │   └── 2026-04-22/
│   │       ├── benchmark.json
│   │       └── iteration-1/
│   └── design/
└── .claude/
    ├── agents/
    │   ├── grader.md               # From skill-creator
    │   ├── comparator.md           # From skill-creator
    │   └── analyzer.md             # From skill-creator
    └── skills/
        └── skill-test/             # New skill for testing skills
            └── SKILL.md
```

---

## Key Differences: skill-creator vs HeadMaster

| Aspect | skill-creator | HeadMaster | Integration Strategy |
|--------|---------------|-----------|---------------------|
| **Purpose** | Build arbitrary skills | SDLC automation pipeline | Adopt eval framework for HeadMaster skills |
| **Test frequency** | Every iteration | CI/CD + manual | Same: both contexts valuable |
| **Baseline** | With/without skill | Before/after changes | Adapt: HeadMaster compares versions |
| **Eval scope** | Skill-specific prompts | Feature workflows | Adapt: test full /plan → /execute flow |
| **Viewer** | Browser HTML | - | Direct copy: works as-is |
| **Description opt** | Trigger accuracy | - | Direct copy: useful for HeadMaster skills |
| **Blind comparison** | A/B testing | - | Adopt: validate isolation claims |

---

## ROI Estimate

### Time Savings
**Manual skill testing today:**
- 30 min per skill change
- 13 skills × 30 min = 6.5 hours per full test cycle
- ~2 full test cycles per month = 13 hours/month

**With eval framework:**
- 5 min automated benchmark run
- 10 min review HTML viewer
- 15 min per skill change
- 13 skills × 15 min = 3.25 hours per full test cycle
- **Savings: 10 hours/month**

### Quality Improvements
**Quantified regression prevention:**
- Current: 1-2 user-reported skill regressions/month
- With benchmarks: 80% caught in CI
- **Reduction: 1.6 regressions/month**

### Confidence in Changes
**Before:** "This probably works..."  
**After:** "Pass rate 88% across 15 test cases, +5% vs baseline"

---

## Recommendations

### Immediate Actions (This Week)
1. ✅ Copy `aggregate_benchmark.py` to HeadMaster
2. ✅ Create 3 evals for /plan skill (lite, standard, full)
3. ✅ Build minimal grader script
4. ✅ Run pilot benchmark manually

### High Priority (Next 2 Weeks)
5. ✅ Integrate HTML eval viewer
6. ✅ Create eval suites for /design and /execute
7. ✅ Add benchmark runner script

### Medium Priority (Next Month)
8. ✅ CI/CD integration
9. ✅ Regression detection
10. ✅ Baseline tracking

### Long Term (Quarter 2)
11. ✅ Description optimization
12. ✅ Blind comparison for isolation validation
13. ✅ Analyst agent integration

---

## Success Metrics

### Quantitative
- **Eval coverage:** 5+ test cases per critical skill (plan, design, execute)
- **Pass rate:** 85%+ on skill benchmarks
- **Regression detection:** 80%+ caught before user reports
- **CI execution time:** <10 min for full skill test suite

### Qualitative
- Skill developers use benchmark workflow voluntarily
- User-reported skill regressions decrease
- Confidence in skill changes increases
- Documentation uses benchmark results as proof of quality

---

## Conclusion

skill-creator provides battle-tested patterns for **evaluation-driven skill development**. HeadMaster should adopt:

**Must Have (P1):**
- ⭐⭐⭐ Quantitative eval framework
- ⭐⭐⭐ Benchmark aggregation + regression detection

**High Value (P2):**
- ⭐⭐ HTML eval viewer (structured review)
- ⭐⭐ Description optimization (trigger accuracy)
- ⭐⭐ Blind comparison (validate isolation)

**Nice to Have (P3):**
- ⭐ Grader agent critique pattern
- ⭐ Analyzer agent for pattern detection

**Implementation cost:** 2-3 weeks for P1+P2 features.  
**ROI:** 10 hours/month saved + 80% fewer regressions + higher confidence in changes.

**Recommendation:** Start with P1 pilot (/plan skill), expand to full coverage over 2 months.
