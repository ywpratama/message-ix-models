import logging
from copy import copy
from functools import partial
from urllib.parse import urlunsplit

import message_ix
from sdmx.model.v21 import Code

import message_ix_models
from message_ix_models import ScenarioInfo, Spec

from .build import apply_spec
from .config import Config
from .data import get_data
from .structure import codelists, get_codes

log = logging.getLogger(__name__)


def _default_first(kind, default):
    return [default] + list(filter(lambda id: id != default, codelists(kind)))


#: Deprecated; use :class:`.model.Config` instead.
SETTINGS = dict(
    # Place the default value first
    regions=_default_first("node", "R14"),
    years=_default_first("year", "B"),
    res_with_dummies=[False, True],
)


def create_res(context, quiet=True):
    """Create a 'bare' MESSAGEix-GLOBIOM reference energy system (RES).

    Parameters
    ----------
    context : .Context
        :attr:`.model.Config.scenario_info` determines the model name and scenario name
        of the created Scenario. If not provided, the defaults are:

        - Model name generated by :func:`name`.
        - Scenario name "baseline".
    quiet : bool, optional
        Passed to `quiet` argument of :func:`.build.apply_spec`.

    Returns
    -------
    message_ix.Scenario
        A scenario as described by :func:`.bare.get_spec`, prepared using
        :func:`.apply_spec`.
    """
    mp = context.get_platform()

    # Retrieve the spec; this also sets defaults expected by name()
    spec = get_spec(context)

    # Model and scenario name for the RES
    args = dict(
        mp=mp,
        model=context.scenario_info.get("model", name(context)),
        scenario=context.scenario_info.get("scenario", "baseline"),
        version="new",
    )

    # TODO move this to ixmp as a method similar to ixmp.util.parse_url()
    url = urlunsplit(
        ("ixmp", mp.name, args["model"] + "/" + args["scenario"], "", args["version"])
    )
    log.info(f"Create {repr(url)}")

    # Create the Scenario
    scenario = message_ix.Scenario(**args)

    # TODO move to message_ix
    scenario.init_par("MERtoPPP", ["node", "year"])

    # Apply the spec
    apply_spec(
        scenario,
        spec,
        data=partial(get_data, context=context, spec=spec),
        quiet=quiet,
        message=f"Create using message-ix-models {message_ix_models.__version__}",
    )

    return scenario


def get_spec(context) -> Spec:
    """Return the spec for the MESSAGE-GLOBIOM global model RES.

    If :attr:`.Config.res_with_dummies` is set, additional elements are added:

    - ``commodity``: "dummy"
    - ``technology``: "dummy", "dummy supply"

    These **may** be used for testing purposes, but **should not** be used in production
    models.

    Returns
    -------
    :class:`dict` of :class:`.ScenarioInfo` objects
    """
    context.setdefault("model", Config())

    add = ScenarioInfo()

    # Add technologies
    add.set["technology"] = copy(get_codes("technology"))

    # Add regions

    # Load configuration for the specified region mapping
    nodes = get_codes(f"node/{context.model.regions}")

    # Top-level "World" node
    world = nodes[nodes.index("World")]

    # Set elements: World, followed by the direct children of World
    add.set["node"] = [world] + world.child

    # Add relations
    add.set["relation"] = get_codes(f"relation/{context.model.relations}")

    # Initialize time periods
    add.year_from_codes(get_codes(f"year/{context.model.years}"))

    # Add levels
    add.set["level"] = get_codes("level")

    # Add commodities
    add.set["commodity"] = get_codes("commodity")

    # Add units, associated with commodities
    units = set(
        commodity.eval_annotation(id="unit") for commodity in add.set["commodity"]
    )
    # Deduplicate by converting to a set and then back; not strictly necessary,
    # but reduces duplicate log entries
    add.set["unit"] = sorted(filter(None, units))

    if context.model.res_with_dummies:
        # Add dummy technologies
        add.set["technology"].extend([Code(id="dummy"), Code(id="dummy source")])
        # Add a dummy commodity
        add.set["commodity"].append(Code(id="dummy"))

    # The RES is the base, so does not require or remove any elements
    return Spec(add=add)


def name(context):
    """Generate a candidate name for a model given `context`.

    The name has a form like::

        MESSAGEix-GLOBIOM R99 YA +D

    where:

    - "R99" is the node list/regional aggregation.
    - "YA" indicates the year codelist (:doc:`/pkg-data/year`).
    - "+D" appears if :attr:`.Config.res_with_dummies` is true.

    """
    cfg = context.model
    return f"MESSAGEix-GLOBIOM {cfg.regions} Y{cfg.years}" + (
        " +D" if cfg.res_with_dummies else ""
    )
