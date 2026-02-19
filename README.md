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
## Semantic Analysis Agent
The **Semantic Analysis Agent** checks whether images’ `alt` text is *semantically consistent* with what the image depicts. It runs a *sequential pipeline* (tools only) and outputs a single structured report.

### High-level pipeline

1. **Image + Alt Extractor**
   - Parses the available HTML/DOM.
   - Collects all images and their related `alt` text (if present).

2. **Caption Generator**
   - Generates a caption for each extracted image using LLM calls.

3. **Alt–Caption Similarity Verifier**
   - Verifies that each image caption and its `alt` text are similar enough.
   - Output: `image_analyzer_report` (issues + summary)


```text
               ┌──────────────────────────────┐
               │   Semantic Analysis          │
               │   Component                  │
               └──────────────┬───────────────┘
                              │
                              │ [fetch_dom_html]
                              v
                ┌─────────────────────────────┐
                │  Image Extractor Tool       │
                │  (images + alt collection)  │
                └──────────────┬──────────────┘
                               │ images_inventory[]
                               v
                ┌─────────────────────────────┐
                │  Caption Generator Tool     │
                │  (caption per image)        │
                └──────────────┬──────────────┘
                               │ captions[]
                               v
                ┌─────────────────────────────┐
                │  Similarity Verifier Tool   │
                │  (alt vs caption match)     │
                └──────────────┬──────────────┘
                               │ semantic_report
                               v
                      Final Semantic JSON
                      issues[] + summary
```

## Installation and Usage
Install environment and dependencies: `cd` in `ax_tester` directory, then: 

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
rm -rf src/ax_tester.egg-info/
playwright install
npm i
```

Create a `.env` file as suggested in [env.example](/.env.example). Moreover, you can use any LLM model just by providing the required `API_KEY` in `.env` file and changing the used model name in [model.py](/src/common/model.py).

To run the client agent, using the same terminal with source `.venv`:
```bash
cd ..
adk web
```
> [!NOTE]
> `adk web` must be run from the parent directory of `ax_tester`.
