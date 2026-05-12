# Test layout

Tests are grouped by the application layer they protect:

- `cli/`: command-line entry points and batch workflow helpers.
- `config/`: environment and runtime configuration.
- `domain/`: pure domain logic such as chunking, language detection, glossary rules, quality checks, and term extraction.
- `graph/`: LangGraph routing and graph node behavior.
- `models/`: shared state/data model behavior.
- `services/`: external-facing services such as LLM providers, glossary persistence, and logging.
- `utils/`: small reusable helpers.

Run the full suite:

```bash
uv run pytest tests/ -v
```

Run one group:

```bash
uv run pytest tests/domain/ -v
uv run pytest tests/services/ -v
uv run pytest tests/cli/ -v
```

Run one file or one test:

```bash
uv run pytest tests/domain/test_domain_glossary.py -v
uv run pytest tests/cli/test_cli.py::TestParseInputPath::test_valid_path -v
```

When adding tests, put the file in the folder matching the `src/` layer first.
If a test crosses several layers, prefer `cli/` for user-facing workflows or the
highest-level layer that owns the behavior being asserted.
