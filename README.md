# Accessibility Tester
AI agent capable of testing the accessibility (also referred to as a11y or ax) of web pages.

## Static Analysis Agent

The **Static Analysis Agent** runs an accessibility assessment from the available HTML/DOM (no user interaction required) and produces a single, validated JSON report by combining:
- automated findings (**axe-core**)
- iterative, agent-guided review (**Loop Finder**)

### High-level pipeline

1. **AxeCore Agent**
   - Runs **axe-core** against the page/DOM.
   - Output: `axe_report` (violations + affected nodes/instances)

2. **Loop Finder Agent**
   - Iteratively inspects the HTML and partial results to increase coverage.
   - Output: `loop_report` (additional issues, risk-based checks, agent-driven findings)

3. **Merge Agent**
   - Merges **`axe_report` + `loop_report`** into one unified report.
   - De-duplicates by *WCAG rule + same node*.
   - Assigns `source` (`axe|llm|both`) and `confidence`.

4. **JSON Formatter**
   - Normalizes and validates the final JSON:
     - safe escaping for HTML snippets

```text
                  ┌──────────────────────────┐
                  │   Static Analysis        │
                  │   Component              │
                  └────────────┬─────────────┘
                               │
                ┌──────────────┴───────────────┐
                │                              │ [set_wcag_level]
                |                              | [fetch_dom_html]
                v                              v
┌──────────────────────────┐   ┌───────────────────────────┐
│  AxeCore Agent           │   │  Loop Finder Agent        │
│  (axe-core scan)         │   │  (iterative checks)       │
└──────────────┬───────────┘   └───────────────┬───────────┘
               │ axe_report                    │ loop_report
               └───────────────┬───────────────┘
                               v
                  ┌──────────────────────────┐
                  │  Merge Agent             │
                  │  (dedupe + unify)        │
                  └────────────┬─────────────┘
                               │ merged_report
                               v
                  ┌──────────────────────────┐
                  │  JSON Formatter          │
                  │  (normalize + validate)  │
                  └────────────┬─────────────┘
                               │
                               v
                       Final Valid JSON         
                       issues[] + summary       
```

## Installation and Usage
Install environment and dependencies: `cd` in `ax_tester` directory, then: 

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
rm -rf src/ax_tester.egg-info/
npm i
```

To run the client agent, using the same terminal with source `.venv`:
```bash
cd ..
adk web
```
> [!NOTE]
> `adk wb` must be run from the parent directory of `ax_tester`.
