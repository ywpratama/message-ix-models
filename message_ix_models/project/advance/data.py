import logging
from copy import copy

from genno import Computer, Key

from message_ix_models.tools.exo_data import (
    ExoDataSource,
    iamc_like_data_for_query,
    register_source,
)
from message_ix_models.util import (
    HAS_MESSAGE_DATA,
    iter_keys,
    package_data_path,
    private_data_path,
)

__all__ = [
    "ADVANCE",
]

log = logging.getLogger(__name__)


#: Expected location of the ADVANCE WP2 data snapshot.
LOCATION = "advance", "advance_compare_20171018-134445.csv.zip"

#: Name of the data file within the archive.
NAME = "advance_compare_20171018-134445.csv"


@register_source
class ADVANCE(ExoDataSource):
    """Provider of exogenous data from the ADVANCE project database.

    To use data from this source, call :func:`.exo_data.prepare_computer` with the
    arguments:

    - `source`: "ADVANCE"
    - `source_kw` including:

      - "model": one of 12 codes including "MESSAGE".
      - "measure": one of 3080 codes for the "VARIABLE" dimension.
      - "scenario": one of 51 codes including "ADV3TRAr2_Base".
      - "name", optional: override :attr:`.ExoDataSource.name`.
      - "aggregate", optional: if :any:`True`, aggregate data from the ADVANCE native
        regions using ``n::groups`` (same behaviour as the base class). Otherwise, do
        not aggregate.

    Example
    -------
    >>> keys = prepare_computer(
    ...     context,
    ...     computer,
    ...     source="ADVANCE",
    ...     source_kw=dict(
    ...         measure="Transport|Service demand|Road|Freight",
    ...         model="MESSAGE",
    ...         scenario="ADV3TRAr2_Base",
    ...     ),
    ... )
    >>> result = computer.get(keys[0])

    Load the metadata packaged with :mod:`message_ix_models` to identify usable
    `source_kw`:

    >>> import sdmx
    >>> from message_ix_models.util import package_data_path
    >>>
    >>> msg = sdmx.read_sdmx(package_data_path("sdmx", "ADVANCE.xml"))
    >>> msg
    <sdmx.StructureMessage>
    <Header>
        prepared: '2023-11-03T21:51:46.052879'
        source: en: Generated by message_ix_models 2023.9.13.dev57+ga558c0b4.d20231011
        test: False
    Codelist (5): MODEL SCENARIO REGION VARIABLE UNIT
    >>> msg.codelist["MODEL].items
    {'AIM/CGE': <Code AIM/CGE>,
     'DNE21+': <Code DNE21+>,
     'GCAM': <Code GCAM>,
     'GEM-E3': <Code GEM-E3>,
     'IMACLIM V1.1': <Code IMACLIM V1.1>,
     'IMAGE': <Code IMAGE>,
     'MESSAGE': <Code MESSAGE>,
     'POLES ADVANCE': <Code POLES ADVANCE>,
     'REMIND': <Code REMIND>,
     'TIAM-UCL': <Code TIAM-UCL>,
     'WITCH': <Code WITCH>,
     'iPETS V.1.5': <Code iPETS V.1.5>}
    """

    id = "ADVANCE"

    def __init__(self, source, source_kw):
        if not source == self.id:
            raise ValueError(source)

        # Map the `measure` keyword to a string appearing in the data
        _kw = copy(source_kw)
        measure = _kw.pop("measure")
        self.variable = {
            "GDP": "GDP|PPP",
            "POP": "Population",
        }.get(measure, measure)

        # Store the model and scenario ID
        self.model = _kw.pop("model", None)
        self.scenario = _kw.pop("scenario", None)

        # Set the name of the returned quantity
        self.name = _kw.pop("name", "")

        self.aggregate = _kw.pop("aggregate", True)

        if len(_kw):
            raise ValueError(_kw)

    def __call__(self):
        # Assemble a query string
        query = " and ".join(
            [
                f"SCENARIO == {self.scenario!r}",
                f"VARIABLE == {self.variable!r}",
                f"MODEL == {self.model!r}" if self.model else "True",
            ]
        )
        log.debug(query)

        # Expected location of the ADVANCE WP2 data snapshot.
        parts = LOCATION
        if HAS_MESSAGE_DATA:
            path = private_data_path(*parts)
        else:
            path = package_data_path("test", *parts)
            log.warning(f"Reading random data from {path}")

        return iamc_like_data_for_query(
            path, query, archive_member=NAME, non_iso_3166="keep"
        )

    def transform(self, c: "Computer", base_key: Key) -> Key:
        k = iter_keys(base_key)

        k1 = base_key
        if self.aggregate:
            # Aggregate
            k1 = k()
            c.add(k1, "aggregate", base_key, "n::groups", keep=False)

        # Interpolate to the desired set of periods
        kw = dict(fill_value="extrapolate")
        k2 = k()
        c.add(k2, "interpolate", k1, "y::coords", kwargs=kw)

        return k2
