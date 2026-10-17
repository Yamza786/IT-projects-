# Automated Software Testing Lab

A deliberately small Python package with a pytest suite showing unit, boundary, and API-contract tests. Run from this directory:

```sh
python -m pip install pytest
python -m pytest -q
```

The sample service validates support tickets and calculates response targets. GitHub Actions runs the suite on pushes and pull requests. Add a failing test before changing behavior, then keep tests deterministic and isolated from real accounts or services.
