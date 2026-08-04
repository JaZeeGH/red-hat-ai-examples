---
name: python-file-review
description: Use when the user asks to review a Python source file for code quality, style issues, bugs, complexity, or dead code. Runs ruff, analyzes docstrings and potential bugs, and writes a structured markdown report.
---

# Python File Review

Perform a structured code quality review of a Python source file and write
the findings to a report.

## Instructions

You will be given a path to a Python file. Follow these steps in order:

1. **Read the file** — read the full source to understand its purpose,
   structure, and what it exports.

2. **Run linting** — run `ruff check <file_path> --output-format=text` to
   identify style and correctness issues. If ruff is not available, note that
   and continue.

3. **Analyze the code** for the following categories:
   - **Docstrings** — missing or incomplete module, class, and function
     docstrings
   - **Complexity** — functions with deep nesting (more than 3 levels) or
     many branches (more than 5 conditions)
   - **Potential bugs** — bare `except` clauses, mutable default arguments,
     shadowed builtins
   - **Dead code** — unreachable statements, unused variables or imports not
     already caught by ruff

4. **Write the review report** to
   `/opt/app-root/workspace/reviews/<basename>-review.md`, where `<basename>`
   is the filename without the `.py` extension. Create the directory if it
   does not exist.

5. **Confirm** by reading back the first few lines of the written file to
   verify it was saved correctly, then report the full output path.

## Report format

The report must follow this structure:

```
# Code Review: <filename>

## Summary
<1-2 sentence overall assessment>

## Issues

### High
- <description> (line <N>)

### Medium
- <description> (line <N>)

### Low
- <description> (line <N>)

## Ruff output
<paste ruff output verbatim, or "not available" / "no issues found">

## Recommendations
<2-3 actionable suggestions prioritized by impact>
```

If a severity level has no issues, write "None identified" under it.

## Input

The path to the Python file to review, provided with the skill invocation.

## Output

A markdown report at `/opt/app-root/workspace/reviews/<basename>-review.md`.
