# pytest-django-query-counts

This is a `pytest` plugin that allows to report SQL query counts
for each test function.

It is very similar to `pytest --durations` option.

## Installation

1. Copy this file into your Django project, e.g. `my_project/test/plugins/query_counts.py`;
2. Add `pytest_plugins = ["my_project.test.plugins.query_counts"]` to your `conftest.py`;

## Use
```
pytest --query-counts=10  # shows 10 biggest query counts
```

## Misc

Probably should create it as PyPI installable package, but <aint_nobody_got_time_for_that.gif>
