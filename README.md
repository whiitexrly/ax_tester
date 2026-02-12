# Accessibility Tester
AI agent capable of testing the accessibility (also referred to as a11y or ax) of web pages.

## Usage
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
