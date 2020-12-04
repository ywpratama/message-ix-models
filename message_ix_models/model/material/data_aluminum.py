# -*- coding: utf-8 -*-
"""
Created on Wed Aug 26 14:43:41 2020
Generate techno economic aluminum data based on aluminum_techno_economic.xlsx

@author: unlu
"""
import pandas as pd
import numpy as np
from collections import defaultdict

import message_ix
import ixmp

from .util import read_config
from .data_util import read_rel
from message_data.tools import (
    ScenarioInfo,
    broadcast,
    make_df,
    make_io,
    make_matched_dfs,
    same_node,
    add_par_data
)



def read_data_aluminum():
    """Read and clean data from :file:`aluminum_techno_economic.xlsx`."""

    # Ensure config is loaded, get the context
    context = read_config()

    # Shorter access to sets configuration
    # sets = context["material"]["generic"]

    fname = "aluminum_techno_economic.xlsx"
    # Read the file
    data_alu = pd.read_excel(
        context.get_path("material", fname),
        sheet_name="data",
    )

    # Drop columns that don't contain useful information
    data_alu= data_alu.drop(['Region', 'Source', 'Description'], axis = 1)

    data_alu_hist = pd.read_excel(
        context.get_path("material", fname),
        sheet_name="data_historical_5year",
        usecols = "A:F")

    data_alu_rel = read_rel(fname)
    # Unit conversion

    # At the moment this is done in the excel file, can be also done here
    # To make sure we use the same units

    return data_alu, data_alu_hist, data_alu_rel

def gen_data_aluminum(scenario, dry_run=False):

    config = read_config()["material"]["aluminum"]

    # Information about scenario, e.g. node, year
    s_info = ScenarioInfo(scenario)

    # Techno-economic assumptions
    data_aluminum, data_aluminum_hist, data_aluminum_rel= read_data_aluminum()
    tec_tv = set(data_aluminum_hist.technology) # set of tecs with time-varying values

    # List of data frames, to be concatenated together at end
    results = defaultdict(list)

    # For each technology there are differnet input and output combinations
    # Iterate over technologies

    allyears = s_info.set['year'] #s_info.Y is only for modeling years
    modelyears = s_info.Y #s_info.Y is only for modeling years
    nodes = s_info.N
    yv_ya = s_info.yv_ya
    fmy = s_info.y0

    # Do not parametrize GLB region the same way
    if "R11_GLB" in nodes:
        nodes.remove("R11_GLB")

    # 'World' is included by default when creating a message_ix.Scenario().
    # Need to remove it for the China bare model
    nodes.remove('World')

    for t in config["technology"]["add"]:

        # years = s_info.Y
        params = data_aluminum.loc[(data_aluminum["technology"] == t),"parameter"]\
        .values.tolist()

        # Obtain the active and vintage years
        av = data_aluminum.loc[(data_aluminum["technology"] == t),
                               'availability'].values[0]
        modelyears = [year for year in modelyears if year >= av]
        yva = yv_ya.loc[yv_ya.year_vtg >= av]

        # Iterate over parameters
        for par in params:

            # Obtain the parameter names, commodity,level,emission

            split = par.split("|")
            param_name = split[0]

            # Obtain the scalar value for the parameter

            val = data_aluminum.loc[((data_aluminum["technology"] == t) \
            & (data_aluminum["parameter"] == par)),'value'].values[0]

            common = dict(
            year_vtg= yv_ya.year_vtg,
            year_act= yv_ya.year_act,
            mode="M1",
            time="year",
            time_origin="year",
            time_dest="year",)

            # For the parameters which inlcudes index names
            if len(split)> 1:

                if (param_name == "input")|(param_name == "output"):

                    # Assign commodity and level names
                    com = split[1]
                    lev = split[2]

                    df = (make_df(param_name, technology=t, commodity=com, \
                    level=lev, value=val, unit='t', **common)\
                    .pipe(broadcast, node_loc=nodes).pipe(same_node))

                    results[param_name].append(df)

                elif param_name == "emission_factor":

                    # Assign the emisson type
                    emi = split[1]

                    df = (make_df(param_name, technology=t,value=val,\
                    emission=emi, unit='t', **common).pipe(broadcast, \
                    node_loc=nodes))
                    results[param_name].append(df)

            # Parameters with only parameter name

            else:
                df = (make_df(param_name, technology=t, value=val,unit='t', \
                **common).pipe(broadcast, node_loc=nodes))
                results[param_name].append(df)

    # Create external demand param
    parname = 'demand'
    demand = gen_mock_demand_aluminum(scenario)
    df = make_df(parname, level='demand', commodity='aluminum', value=demand.value, unit='t', \
        year=demand.year, time='year', node=demand.node)#.pipe(broadcast, node=nodes)
    results[parname].append(df)

    # # Add historical data
    #
    # for tec in data_aluminum_hist["technology"].unique():
    #
    #     y_hist = [1980,1985,1990,1995,2000,2005,2010,2015] #length need to match what's in the xls
    #     common_hist = dict(
    #         year_vtg= y_hist,
    #         year_act= y_hist,
    #         mode="M1",
    #         time="year",)
    #
    #     val_act = data_aluminum_hist.\
    #     loc[(data_aluminum_hist["technology"]== tec), "production"]
    #
    #     df_hist_act = (make_df("historical_activity", technology=tec, \
    #     value=val_act, unit='Mt', **common_hist).pipe(broadcast, node_loc=nodes))
    #
    #     results["historical_activity"].append(df_hist_act)
    #
    #     c_factor = data_aluminum.loc[((data_aluminum["technology"]== tec) \
    #                 & (data_aluminum["parameter"]=="capacity_factor")), "value"].values
    #
    #     val_cap = data_aluminum_hist.loc[(data_aluminum_hist["technology"]== tec), \
    #                                     "new_production"] / c_factor
    #
    #     df_hist_cap = (make_df("historical_new_capacity", technology=tec, \
    #     value=val_cap, unit='Mt', **common_hist).pipe(broadcast, node_loc=nodes))
    #
    #     results["historical_new_capacity"].append(df_hist_cap)

    # Add relations for scrap grades and availability

    for r in config['relation']['add']:
        print(r)

        params = data_aluminum_rel.loc[(data_aluminum_rel["relation"] == r),\
            "parameter"].values.tolist()

        common_rel = dict(
            year_rel = modelyears,
            year_act = modelyears,
            mode = 'M1',
            relation = r,)

        for par_name in params:
            if par_name == "relation_activity":

                tec_list = data_aluminum_rel.loc[((data_aluminum_rel["relation"] == r) \
                    & (data_aluminum_rel["parameter"] == par_name)) ,'technology']

                for tec in tec_list.unique():
                    print("tec list")
                    print(data_aluminum_rel["technology"].unique())
                    print(tec)

                    val = data_aluminum_rel.loc[((data_aluminum_rel["relation"] == r) \
                        & (data_aluminum_rel["parameter"] == par_name) & \
                        (data_aluminum_rel["technology"]==tec)),'value'].values[0]
                    print("relation value")
                    print(val)

                    df = (make_df(par_name, technology=tec, value=val, unit='-',\
                    **common_rel).pipe(broadcast, node_rel=nodes, node_loc=nodes))

                    results[par_name].append(df)

            elif par_name == "relation_upper":

                val = data_aluminum_rel.loc[((data_aluminum_rel["relation"] == r) \
                    & (data_aluminum_rel["parameter"] == par_name)),'value'].values[0]

                df = (make_df(par_name, value=val, unit='-',\
                **common_rel).pipe(broadcast, node_rel=nodes))

                results[par_name].append(df)

    results_aluminum = {par_name: pd.concat(dfs) for par_name,
                        dfs in results.items()}

    return results_aluminum



def gen_mock_demand_aluminum(scenario):

    context = read_config()
    s_info = ScenarioInfo(scenario)
    modelyears = s_info.Y #s_info.Y is only for modeling years
    fmy = s_info.y0

    # SSP2 R11 baseline GDP projection
    gdp_growth = pd.read_excel(
        context.get_path("material", "iamc_db ENGAGE baseline GDP PPP.xlsx"),
        sheet_name="data",)

    gdp_growth = gdp_growth.loc[(gdp_growth['Scenario']=='baseline') & \
    (gdp_growth['Region']!='World')].drop(['Model', 'Variable', 'Unit', 'Notes',\
     2000, 2005, 2010, 2015], axis = 1)

    gdp_growth['Region'] = 'R11_'+ gdp_growth['Region']

    # Aluminum 2015
    # https://www.world-aluminium.org/statistics/#data
    # Not all the regions match here. Some assumptions needed to be made.
    # MEA, PAS, SAS, EEU, FSU

    # Values in 2010 from IAI for China. Slightly varies for other regions.
    # Can be adjusted: https://alucycle.world-aluminium.org/public-access/

    fin_to_useful = 0.971
    useful_to_product = 0.866

    r = ['R11_AFR', 'R11_CPA', 'R11_EEU', 'R11_FSU', 'R11_LAM', \
        'R11_MEA', 'R11_NAM', 'R11_PAO', 'R11_PAS', 'R11_SAS', 'R11_WEU']
    d = [1.7, 31.5, 1.8, 2, 1.3, 6.1, 4.5, 2,1,1,3.7]
    d = [x * fin_to_useful * useful_to_product for x in d]

    demand2015_al = pd.DataFrame({'Region':r, 'Val':d}).\
        join(gdp_growth.set_index('Region'), on='Region').\
        rename(columns={'Region':'node'})

    demand2015_al.iloc[:,3:] = demand2015_al.iloc[:,3:].\
        div(demand2015_al[2020], axis=0).\
        multiply(demand2015_al["Val"], axis=0)

    demand2015_al = pd.melt(demand2015_al.drop(['Val', 'Scenario'], axis=1),\
        id_vars=['node'], var_name='year', value_name = 'value')

    # # Add temporary exogenous demand: 17.3 Mt in 2010 (IAI)
    # demand2010_aluminum = 17.3
    #
    # # The future projection of the demand: Increases by half of the GDP growth rate
    # # gdp_growth rate: SSP2 global model. Starting from 2020.
    # gdp_growth = [0.121448215899944, 0.0733079014579874,
    #                         0.0348154093342843, 0.021827616787921,
    #                         0.0134425983942219, 0.0108320197485592,
    #                         0.00884341208063, 0.00829374133206562,
    #                         # Add one more element since model is until 2110 normally
    #                         0.00649794573935969, 0.00649794573935969]
    # baseyear = list(range(2020, 2110+1, 10)) # Index for above vector
    # gdp_growth_interp = np.interp(modelyears, baseyear, gdp_growth)
    #
    # i = 0
    # values = []
    #
    # # Assume 5 year duration at the beginning
    # duration_period = (pd.Series(modelyears) - \
    #     pd.Series(modelyears).shift(1)).tolist()
    # duration_period[0] = 5
    #
    # val = (demand2010_aluminum * (1+ 0.147718884937996/2) ** duration_period[i])
    # values.append(val)
    #
    # for element in gdp_growth_interp:
    #     i = i + 1
    #     if i < len(modelyears):
    #         val = (val * (1+ element/2) ** duration_period[i])
    #         values.append(val)
    # # Adjust the demand to product level.
    #
    # values = [x * fin_to_useful * useful_to_product for x in values]

    return demand2015_al
