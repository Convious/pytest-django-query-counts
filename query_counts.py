# This is a `pytest` plugin that allows to report SQL query counts
# for each test function.
#
# It is very similar to `pytest --durations` option.
#
# Installation:
# 1. Copy this file into your Django project, e.g. `my_project/test/plugins/query_counts.py`;
# 2. Add `pytest_plugins = ["my_project.test.plugins.query_counts"]` to your `conftest.py`;
#
# Use:
# >> pytest --query-counts=10  # shows 10 biggest query counts

from contextlib import ExitStack

import _pytest
import pytest
from django.db import connection, connections  # type: ignore

# Undocumented "private" django API, do not remember how I stumbled upon it,
# but as it's used in django's own tests, I guess it's safe to use it here.
from django.test.utils import CaptureQueriesContext as CQC


def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup("django")
    group._addoption(
        "--query-counts",
        action="store",
        type=int,
        dest="query_counts",
        default=None,
        metavar="N",
        help="Shows N biggest SQL query counts for setup/test (N=0 for all)",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: _pytest.nodes.Node, call: pytest.CallInfo):
    result = yield
    # yield does not return final result in pytest - we need to call `get_result()` for that.
    #
    # https://docs.pytest.org/en/latest/how-to/writing_hook_functions.html#hookwrapper-executing-around-other-hooks
    report = result.get_result()

    # I could not figure out how to neatly and disticntly distinguish SQL query counts
    # per each test step, thus reporting only what we have after teardown, i.e. test is
    # complete
    if report.when == "teardown":
        report._query_counts = getattr(item, "_query_counts", {})
    return report


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: _pytest.nodes.Node):
    # This hook is called on every test function call
    connection_names = connection._connections.settings.keys()  # type: ignore

    # ExitStack allows to programatically combine context managers
    # https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack
    with ExitStack() as stack:
        query_contexts = {
            cname: stack.enter_context(CQC(connections[cname]))
            for cname in connection_names
        }

        # As we are wrapping default `pytest_runtest_call` with query counting mechanism
        # we must to `yield` execution to continue to other calls, if we'd try to
        # do something like `item.runtest()` then test item will be executed multiple times
        # by other hooks - and thus may fail
        #
        # https://docs.pytest.org/en/latest/how-to/writing_hook_functions.html#hookwrapper-executing-around-other-hooks
        yield

    # Extract query count mapping for all connections into our test function (i.e. `item`)
    item._query_counts = {  # type: ignore
        cname: len(query_context) for cname, query_context in query_contexts.items()
    }


def pytest_terminal_summary(
    terminalreporter: _pytest.terminal.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
):
    # inspired by pytest's standard `--durations` report, as without example pytest's
    # extendibility is a tough nut to crack.
    #
    # This hook is called after test-suite finished.
    #
    # https://github.com/pytest-dev/pytest/blob/e54c6a1362589b32a2e63bb780192b86216ecec8/src/_pytest/runner.py#L69-L98

    query_counts_option = config.option.query_counts
    if query_counts_option is None:
        return

    tr = terminalreporter
    query_list = []
    for reports in tr.stats.values():
        for report in reports:
            if hasattr(report, "_query_counts"):
                query_list.append(report)
    if not query_list:
        return

    query_list.sort(key=lambda x: sum(x._query_counts.values()), reverse=True)

    if not query_counts_option:
        tr.write_sep("=", "biggest query counts")
    else:
        tr.write_sep("=", "%s biggest query counts" % query_counts_option)
        query_list = query_list[:query_counts_option]

    for report in query_list:
        tr.write_line(f"{str(report._query_counts):<80} {report.nodeid}")
