import logging
import sys

import pytest

from message_ix_models.model import snapshot
from message_ix_models.testing import GHA

log = logging.getLogger(__name__)


@snapshot.load.minimum_version
@pytest.mark.skipif(
    condition=GHA and sys.platform in ("darwin", "win32"), reason="Slow."
)
def test_load(test_context, load_snapshots):
    scenario_names = []

    for scenario in load_snapshots:
        scenario_names.append(scenario.scenario)

    assert len(scenario_names) >= 2
