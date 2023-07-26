import numpy as np

from message_ix_models.tools.costs.gdp import (
    calculate_adjusted_region_cost_ratios,
    get_gdp_data,
    linearly_regress_tech_cost_vs_gdp_ratios,
    project_gdp_converged_inv_costs,
)
from message_ix_models.tools.costs.learning import (
    get_cost_reduction_data,
    get_technology_first_year_data,
    project_NAM_inv_costs_using_learning_rates,
)
from message_ix_models.tools.costs.weo import (
    calculate_region_cost_ratios,
    get_cost_assumption_data,
    get_region_differentiated_costs,
    get_weo_data,
)


def test_get_gdp_data():
    res = get_gdp_data()

    # Check SSP1, SSP2, and SSP3 are all present in the data
    assert np.all(res.scenario.unique() == ["SSP1", "SSP2", "SSP3"])

    # Check that R11 regions are present
    assert np.all(
        res.r11_region.unique()
        == ["AFR", "CPA", "EEU", "FSU", "LAM", "MEA", "NAM", "PAO", "PAS", "SAS", "WEU"]
    )

    # Check that the GDP ratio for NAM is zero
    assert min(res.loc[res.r11_region == "NAM", "gdp_ratio_reg_to_nam"]) == 1.0
    assert max(res.loc[res.r11_region == "NAM", "gdp_ratio_reg_to_nam"]) == 1.0


def test_linearly_regress_tech_cost_vs_gdp_ratios():
    df_gdp = get_gdp_data()
    df_weo = get_weo_data()
    df_tech_cost_ratios = calculate_region_cost_ratios(df_weo)

    res = linearly_regress_tech_cost_vs_gdp_ratios(df_gdp, df_tech_cost_ratios)

    # Check SSP1, SSP2, and SSP3 are all present in the data
    assert np.all(res.scenario.unique() == ["SSP1", "SSP2", "SSP3"])

    # The absolute value of the slopes should be less than 1 probably
    assert abs(min(res.slope)) <= 1
    assert abs(max(res.slope)) <= 1


# Test function to calculate adjusted regionally differentiated cost ratios
def test_calculate_adjusted_region_cost_ratios():
    df_gdp = get_gdp_data()
    df_weo = get_weo_data()
    df_tech_cost_ratios = calculate_region_cost_ratios(df_weo)
    df_linreg = linearly_regress_tech_cost_vs_gdp_ratios(df_gdp, df_tech_cost_ratios)

    res = calculate_adjusted_region_cost_ratios(df_gdp, df_linreg)

    # Check SSP1, SSP2, and SSP3 are all present in the data
    # TODO: this test won't be good once we make changing scenarios configurable
    assert np.all(res.scenario.unique() == ["SSP1", "SSP2", "SSP3"])

    # Check that the adjusted cost ratios are greater than zero
    assert min(res.cost_ratio_adj) > 0

    # Check that the adjusted cost ratios for NAM are equal to 1
    assert min(res.loc[res.r11_region == "NAM", "cost_ratio_adj"]) == 1.0


# Test function to project GDP-converged investment costs
def test_project_gdp_converged_inv_costs():
    df_gdp = get_gdp_data()
    df_weo = get_weo_data()
    df_nam_orig_message = get_cost_assumption_data()
    df_tech_cost_ratios = calculate_region_cost_ratios(df_weo)
    df_linreg = linearly_regress_tech_cost_vs_gdp_ratios(df_gdp, df_tech_cost_ratios)
    df_adj_cost_ratios = calculate_adjusted_region_cost_ratios(df_gdp, df_linreg)

    df_region_diff = get_region_differentiated_costs(
        df_weo, df_nam_orig_message, df_tech_cost_ratios
    )

    df_learning_rates = get_cost_reduction_data()
    df_technology_first_year = get_technology_first_year_data()

    df_nam_learning = project_NAM_inv_costs_using_learning_rates(
        df_region_diff, df_learning_rates, df_technology_first_year
    )

    res = project_gdp_converged_inv_costs(df_nam_learning, df_adj_cost_ratios)

    # Check SSP1, SSP2, and SSP3 are all present in the data
    # TODO: this test won't be good once we make changing scenarios configurable
    assert np.all(res.scenario.unique() == ["SSP1", "SSP2", "SSP3"])

    # Check that the R11 regions are present
    # TODO: this won't be a good test once we make changing regions configurable
    assert np.all(
        res.r11_region.unique()
        == ["AFR", "CPA", "EEU", "FSU", "LAM", "MEA", "NAM", "PAO", "PAS", "SAS", "WEU"]
    )
