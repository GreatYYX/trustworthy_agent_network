# Experiment Results

This directory contains push-ready outputs from the paired Trustworthy Agent
Network experiments.

- `latest.json` records the Git revision, UTC run time, deterministic TAN
  results, configured model, and live-run exit status.
- `model-run-<model>.txt` is the complete live bolted-on model transcript.

Regenerate both artifacts from the repository root:

```bash
guardrail_examples/venv/bin/python guardrail_examples/run_results.py
```

For an offline-only run that does not call a model API:

```bash
guardrail_examples/venv/bin/python guardrail_examples/run_results.py --skip-live
```

The website's third `TAN baked-in` mode is a readable projection of the
deterministic results in `latest.json`.

Validate the three website modes and their complete case inventory with:

```bash
node docs/demo-data.test.js
```
