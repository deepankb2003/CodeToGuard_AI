# Coding Standards

Ground truth for the quality agent's RAG retrieval. Keep each section short
and concrete — the agent quotes these excerpts back to justify findings, so
vague guidance produces vague reviews.

## Error Handling

Never use a bare `except:` or `except Exception:` to silently swallow errors
in code paths that matter for correctness. Catch the specific exception you
expect, and either handle it or re-raise with added context. Logging-and-continuing
is fine at system boundaries (webhook handlers, background jobs) but should
never hide an error inside business logic.

## Secrets & Credentials

Never hardcode API keys, tokens, passwords, or connection strings with
embedded credentials in source files. All secrets must come from
`app.config.settings`, which loads them from the environment. Flag any
string literal that looks like a credential (long random-looking tokens,
`sk-...`, `postgresql://user:pass@...`).

## Function Size & Complexity

A function doing more than one clearly-named thing should be split. Watch for
functions over ~40 lines or with more than 3 levels of nesting — these are
usually doing too much and are hard to test in isolation.

## Docstrings & Comments

Public functions and classes need a docstring explaining *why* they exist or
*what contract* they hold — not a restatement of the function signature.
Comments should explain non-obvious reasoning (a workaround, an invariant), not
narrate what the next line of code obviously does.

## Testing

New logic should ship with a test that exercises it, especially for anything
touching parsing, external API responses, or security-sensitive code paths
(auth, input validation, credential handling).

## Logging

Use the module-level `logger`, never `print()`, for anything other than a
one-off local script. Don't log secrets, tokens, or full request bodies at
INFO level or above.

## Type Hints

Public function signatures should have type hints on parameters and return
values. This project targets modern Python, so prefer `str | None` over
`Optional[str]` in new code.

## Naming Conventions

Use `snake_case` for functions and variables, `PascalCase` for classes, and
`UPPER_SNAKE_CASE` for module-level constants. Avoid one-letter variable names
outside of short comprehensions/loops.
