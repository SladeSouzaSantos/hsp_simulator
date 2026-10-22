"""Offline-by-default regression suite; external integrations are explicit opt-in.

`python -m pytest -q` must not depend on NASA/PVGIS uptime or internet access.
Run `python -m pytest -q --run-live` to include real-provider integration.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--run-live', action='store_true', default=False,
        help='include tests which call external solar-data providers',
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption('--run-live'):
        return
    for item in items:
        if 'live' in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason='requires network; run python -m pytest --run-live'
            ))
