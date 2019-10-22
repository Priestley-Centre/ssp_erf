import os.path

import pyam
import pymagicc.definitions
import tqdm
from openscm.scmdataframe import ScmDataFrame
from pymagicc.io import MAGICCData

# scenario data available from https://www.rcmip.org/ (the emissions protocol)
RCMIP_DATA = os.path.join("data", "rcmip", "rcmip-emissions-annual-means-v2-0-0.csv")
OUTPUT_PATH = os.path.join("data", "rcmip", "scen-files")

UNIT_CONV = {
    ("*NH3*", "Mt NH3/yr"): ["Mt N/yr", (14) / (14 + 3)],
    ("*NOx*", "Mt NOx/yr"): ["Mt N/yr", (14) / (14 + 2 * 16)],
    ("*SOx*", "Mt SO2/yr"): ["Mt S/yr", (32) / (32 + 2 * 16)],
    ("*CO2*", "Mt CO2/yr"): ["Gt C/yr", (12) / ((12 + 2 * 16) * 1000)],
    ("*NMVOC*", "Mt VOC/yr"): ["Mt NMVOC/yr", 1],
}

scen_vars = pymagicc.definitions.convert_magicc7_to_openscm_variables(
    [
        "{}_EMIS".format(v)
        for v in pymagicc.definitions.PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1
    ]
)

rcmip_db_ssps = ScmDataFrame(RCMIP_DATA)
for scenario in tqdm.tqdm(
    rcmip_db_ssps.filter(scenario="*ssp*")["scenario"].unique(),
    desc="Scenario",
):
    # OpenSCM units not quite up to it yet...
    tmp_df = (
        rcmip_db_ssps.filter(variable="Em*", region="World", scenario=scenario)
        .to_iamdataframe()
        .data
    )
    tmp_df["year"] = tmp_df["time"].apply(lambda x: x.year)
    tmp_df = tmp_df.drop("time", axis="columns")
    tmp_df["variable"] = tmp_df["variable"].apply(
        lambda x: x.replace("|Sulfur", "|SOx")
        .replace("|VOC", "|NMVOC")
        .replace("|F-Gases|HFC", "")
        .replace("|F-Gases|PFC", "")
        .replace("|F-Gases", "")
        .replace("|Montreal Gases", "")
        .replace("HFC4310mee", "HFC4310")
    )
    tmp_df = pyam.IamDataFrame(tmp_df).filter(variable=scen_vars)

    for (var_filter, target_unit), conv_args in UNIT_CONV.items():
        var_df = tmp_df.filter(variable=var_filter)
        tmp_df = tmp_df.filter(variable=var_filter, keep=False)
        var_df = var_df.convert_unit({target_unit: conv_args})
        tmp_df = tmp_df.append(var_df)

    writer = MAGICCData(tmp_df)
    writer.set_meta("SET", "todo")
    writer.metadata = {
        "description": "{} emissions".format(scenario),
        "notes": "written from the RCMIP (rcmip.org) protocol ({}), consistent with CMIP6 emissions".format(os.path.basename(RCMIP_DATA)),
    }
    fn = "{}.SCEN".format(scenario.upper())
    writer.write(os.path.join(OUTPUT_PATH, fn), magicc_version=6)
