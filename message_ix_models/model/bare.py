import logging
from copy import copy
from functools import partial
from typing import Mapping
from urllib.parse import urlunsplit

import message_ix
from iam_units import registry
from sdmx.model import Code

import message_ix_models
from message_ix_models import ScenarioInfo
from message_ix_models.model.build import apply_spec
from message_ix_models.model.data import get_data
from message_ix_models.model.structure import get_codes
from message_ix_models.util import eval_anno

log = logging.getLogger(__name__)


# Settings and valid values; the default is listed first
SETTINGS = dict(
    period_start=[2010],
    period_end=[2110],
    # Recognized lists of nodes; these match the files in data/node/*.yaml
    regions=["R14", "R11", "RCP", "ISR"],
    res_with_dummies=[False, True],
    time_step=[10, 5],
)


def create_res(context, quiet=True):
    """Create a 'bare' MESSAGEix-GLOBIOM reference energy system (RES).

    Parameters
    ----------
    context : .Context
        :attr:`.Context.scenario_info` determines the model name and scenario name of
        the created Scenario. If not provided, the defaults are:

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


def get_spec(context) -> Mapping[str, ScenarioInfo]:
    """Return the spec for the MESSAGE-GLOBIOM global model RES.

    Returns
    -------
    :class:`dict` of :class:`.ScenarioInfo` objects
    """
    context.use_defaults(SETTINGS)

    # The RES is the base, so does not require/remove any elements
    spec = dict(require=ScenarioInfo(), remove=ScenarioInfo())

    add = ScenarioInfo()

    # Add technologies
    add.set["technology"] = copy(get_codes("technology"))

    # Add regions

    # Load configuration for the specified region mapping
    nodes = get_codes(f"node/{context.regions}")

    # Top-level "World" node
    # FIXME typing ignored temporarily for PR#9
    world = nodes[nodes.index("World")]  # type: ignore [arg-type]

    # Set elements: World, followed by the direct children of World
    add.set["node"] = [world] + world.child

    # Add the time horizon
    add.set["year"] = list(
        range(context.period_start, context.period_end + 1, context.time_step)
    )
    add.set["cat_year"] = [("firstmodelyear", context.period_start)]

    # First model year
    add.y0 = context.period_start

    # Add levels
    add.set["level"] = get_codes("level")

    # Add commodities
    c_list = get_codes("commodity")
    add.set["commodity"] = c_list

    # Add units, associated with commodities
    for c in c_list:
        unit = eval_anno(c, "unit")
        if unit is None:
            log.warning(f"Commodity {c} lacks defined units")
            continue

        try:
            # Check that the unit can be parsed by the pint.UnitRegistry
            registry(unit)
        except Exception:  # pragma: no cover
            # No coverage: code that triggers this exception should never be committed
            log.warning(f"Unit {unit} for commodity {c} not pint compatible")
        else:
            add.set["unit"].append(unit)

    # Deduplicate by converting to a set and then back; not strictly necessary,
    # but reduces duplicate log entries
    add.set["unit"] = sorted(set(add.set["unit"]))

    # Manually set the first model year
    add.y0 = context.period_start

    if context.res_with_dummies:
        # Add dummy technologies
        add.set["technology"].extend([Code(id="dummy"), Code(id="dummy source")])
        # Add a dummy commodity
        add.set["commodity"].append(Code(id="dummy"))

    spec["add"] = add
    return spec


def name(context):
    """Generate a candidate name for a model given `context`.

    The name has a form like::

        MESSAGEix-GLOBIOM R99 1990:2:2020+D

    where:

    - "R99" is the node list/regional aggregation.
    - "1990:2:2020" indicates the first model period is 1990, the last period is 2020,
      and periods have a duration of 2 years.
    - "+D" indicates dummy set elements are included in the structure.

    """
    return (
        f"MESSAGEix-GLOBIOM {context.regions} {context.period_start}:"
        f"{context.time_step}:{context.period_end}"
        + ("+D" if context.get("res_with_dummies", False) else "")
    )