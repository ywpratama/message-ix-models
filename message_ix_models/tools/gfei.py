"""Handle data from the Global Fuel Economy Initiative (GFEI)."""

import logging
from typing import TYPE_CHECKING

import genno
import plotnine as p9

from message_ix_models.tools.exo_data import ExoDataSource, register_source
from message_ix_models.util import path_fallback

if TYPE_CHECKING:
    from genno import Computer, Quantity

    from message_ix_models import Context

log = logging.getLogger(__name__)


@register_source
class GFEI(ExoDataSource):
    """Provider of exogenous data from the GFEI 2017 data source.

    To use data from this source, call :func:`.exo_data.prepare_computer` with the
    arguments:

    - `source`: "GFEI".
    - `source_kw` including:

      - `plot` (optional, default :any:`False`): add a task with the key
        "plot GFEI debug" to generate diagnostic plot using :class:`.Plot`.
      - `aggregate`, `interpolate`: see :meth:`.ExoDataSource.transform`.

    The source data:

    - is derived from
      https://theicct.org/publications/gfei-tech-policy-drivers-2005-2017, specifically
      the data underlying “Figure 37. Fuel consumption range by type of powertrain and
      vehicle size, 2017”.
    - has resolution of individual countries.
    - corresponds to new vehicle registrations in 2017.
    - has units of megajoule / kilometre, converted from original litres of gasoline
      equivalent per 100 km.

    .. note:: if py:`source_kw["aggregate"] is True`, the aggregation performed is an
       unweighted :func:`sum`. To produce meaningful values for multi-country regions,
       instead perform perform a weighted mean using appropriate weights; for instance
       the vehicle activity for each country. The class currently **does not** do this
       automatically.
    """

    id = "GFEI"

    #: By default, do not aggregate.
    aggregate = False

    #: By default, do not interpolate.
    interpolate = False

    def __init__(self, source, source_kw):
        if source != self.id:
            raise ValueError(source)

        self.plot = source_kw.pop("plot", False)

        self.raise_on_extra_kw(source_kw)

        # Set the name of the returned quantity
        self.name = "fuel economy"

        self.path = path_fallback(
            "transport", "GFEI_FE_by_Powertrain_2017.csv", where="private test"
        )
        if "test" in self.path.parts:
            log.warning(f"Reading random data from {self.path}")

    def __call__(self):
        import genno.operator

        from message_ix_models.util.pycountry import iso_3166_alpha_3

        def relabel_n(qty: "Quantity") -> "Quantity":
            labels = {n: iso_3166_alpha_3(n) for n in qty.coords["n"].data}
            return genno.operator.relabel(qty, {"n": labels})

        # - Read the CSV file, rename columns.
        # - Assign the y value.
        # - Convert units.
        return (
            genno.operator.load_file(
                self.path, dims={"Country": "n", "FuelTypeReduced": "t"}
            )
            .pipe(relabel_n)
            .pipe(lambda qty: qty.expand_dims(y=[2017]))
            .pipe(genno.operator.convert_units, "MJ / (vehicle km)")
        )

    def transform(self, c: "Computer", base_key: genno.Key) -> genno.Key:
        """Prepare `c` to transform raw data from `base_key`."""
        ks = genno.KeySeq(super().transform(c, base_key))

        if self.plot:
            # Path for debug output
            context: "Context" = c.graph["context"]
            debug_path = context.get_local_path("debug")
            debug_path.mkdir(parents=True, exist_ok=True)
            c.configure(output_dir=debug_path)

            c.add(f"plot {self.id} debug", Plot, ks.base)

        return ks.base


class Plot(genno.compat.plotnine.Plot):
    """Diagnostic plot of processed data."""

    basename = "GFEI-fuel-economy-t"

    static = [
        p9.aes(x="n", y="value"),
        p9.geom_col(stat="identity", position="dodge"),
        p9.theme(axis_text_x=p9.element_text(rotation=90, hjust=1)),
    ]

    def generate(self, data):
        for technology, group_df in data.groupby("t"):
            yield p9.ggplot(group_df) + self.static + p9.ggtitle(technology)
