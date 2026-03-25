# Accessibility Tester
AI agent capable of testing the accessibility (also referred to as a11y or ax) of web pages.

## Browser Session (`BROWSER_SESSION`)

The project uses a shared singleton session defined in [`src/utils/browser_session.py`](src/utils/browser_session.py):
- one Playwright browser/context/page per run
- one source of truth for the current page used by agents/tools
- centralized keyboard actions (`press_key`) and navigation (`goto`)

### Runtime lifecycle

1. Initialize session once with root tool `initialize_session`.
2. Navigate with root tool `navigate_to_page`.
3. Run analysis tools/agents on the current page in `BROWSER_SESSION`.

### Tool contract

- Tools must reuse `BROWSER_SESSION.page` and must not create a new browser/context/page.
- Runtime tools must not navigate again to the same URL internally.
- Runtime tools should not require `url` input when they operate on the current page.
- Keyboard press timing logic is centralized in `BROWSER_SESSION.press_key`.

## Unified Report Schema

All final reports use the same `Report` schema:
- `tool_name`: name of the tool/aggregator that produced the report
- `issue_list`: list of normalized issues
- `total_issues`: total number of issues in `issue_list`
- `page`: analyzed URL
- `metadata`: list of `{key, value}` entries for tool-specific extra data

Each issue follows a single `Issue` schema and includes `image_url_or_path` (nullable):
- use the original image URL when the image comes from the analyzed page
- use a local path/folder when the issue refers to saved local screenshots
- use `null` when not available

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
   - Output: `static_report` (`Report`)

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
                               │ static_report
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
   - Output: `image_analyzer_report` (`Report`)


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

## Navigator Agent
The **Navigator Agent** performs runtime navigation using Playwright and emits a stream of `NavigatorState` snapshots. It follows a producer/consumer model:
- **Producer (Navigator)**: walks focusable elements (Tab/Space), captures screenshots and AX info.
- **Consumers**: analyze each state independently and emit WCAG issues. Each consumer specializes in one WCAG rule (or a small set of closely related ones).

The default consumer set is centralized in:
- [`build_default_navigator_consumers()`](src/tools/consumers/__init__.py)

### High-level pipeline

0. **Runtime Navigator Tool** 
   - Navigates the page using keyboard.
   - Emits `NavigatorState` (prev/current focus context).

1. **Focus Visible Consumer** (WCAG 2.4.7, Level AA)
   - Consumes each state and collects element screenshots.
   - Uses LLM analysis to detect missing focus indicators.
   - Output: `focus_visible_report` (`Report`)

2. **Link Purpose Consumer** (WCAG 2.4.4 + 2.4.9)
   - Collects focused links (`role=link`) from AX info.
   - Sends accessible name/description + href + HTML snippet to LLM.
   - Output: `link_purpose_report` (`Report`)

3. **On Focus Consumer** (WCAG 3.2.1, Level A)
   - Detects unexpected context changes caused by focus transitions.
   - Flags events such as:
     - new tab/window opened only by focus
     - URL/title change triggered by focus alone
     - wrong focus restore behavior after `Space` / `Escape` on expandable widgets
   - Output: `on_focus_report` (`Report`)

4. **No Keyboard Trap Consumer** (WCAG 2.1.2, Level A)
   - Triggered on `Escape` transitions after expandable/modal interactions.
   - Uses root/before/after screenshots to verify that `Escape` closes the active modal.
   - Flags potential keyboard traps when modal remains open.
   - Output: `no_keyboard_trap_report` (`Report`)

### Implemented Consumers

| Consumer | Rule(s) | Strategy | Report key |
|---|---|---|---|
| `FocusVisibleConsumer` | `2.4.7` | LLM vision on focused element screenshots | `focus_visible_report` |
| `LinkPurposeConsumer` | `2.4.4`, `2.4.9` | LLM text analysis on link AX name/description + href + snippet | `link_purpose_report` |
| `OnFocusConsumer` | `3.2.1` | Deterministic transition checks on focus path/url/title/page count | `on_focus_report` |
| `NoKeyboardTrapConsumer` | `2.1.2` | LLM vision check before/after `Escape` for modal close behavior | `no_keyboard_trap_report` |

```text
               ┌──────────────────────────────┐
               │   Runtime Navigator          │
               │   Component                  │
               └───────────────┬──────────────┘
                               │
                               │ NavigatorState stream
                               v
              ┌─────────────────────────────┐
              | ┌─────────────────────────────┐
              └─│          Consumer           │
                └──────────────┬──────────────┘
                               │ <name>_report
                               │
                               v
                    Runtime Consumer Reports
                    (one Report per consumer)
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


## Code style

This project uses **Ruff** for formatting and linting. The same checks are enforced by the CI workflow ([`python-format.yml`](.github/workflows/python-format.yml)), so your push/PR will fail if they don’t pass. Run the following commands before pushing from root directory:

```bash
ruff check --fix && ruff format
```
