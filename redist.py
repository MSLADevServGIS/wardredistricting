# -*- coding: utf-8 -*-
"""
redist.py -- Redistricting operation
Author: Garin Wally; Jan 2017

This script processes data in-memory to calculate total estimated population
and group it by current ward boundaries and neighborhood council districts.
This is specifically for the Ward Redistricting project that occurs every odd
year, but can also be used for the nhood profiles.

Use:
    >>> redist.calc_pop()
"""

from math import ceil, floor

import pandas as pd

import arcpy
import archacks


# =============================================================================
# GLOBAL VARS

# Default gdb location
DEFAULT = "data/redist_data.gdb"

# Layers to remove from TOC when complete
RM_LYRS = ["cleaned_blks", "mem_NC_blks"]

# Field names
WARD = "Ward_Numbe"
NH_NAME = "Name"

# Selection of potential errors from Spatial Join operations
fix_qry = """
    "{0}" IS NULL AND (
        "EstTotPop14" >0
        OR "dwellings" > 0
        OR "dwellings_1" > 0)
    OR
    "{1}" IS NULL AND (
        "NewPop2015" > 0
        OR "NewPop2016" > 0)
    """.format(WARD, "ward14")  # TODO: this will need to be changed...


# Dictionary of carry-over values created in functions ("Global Dict")
# This would likely be frowned upon by the Python Community, but w/e
GD = {}

# Instructions for manual edits/changes
INSTRUCTIONS = ("Manually edit the ward and nc name field in "
                "'mem_cleaned_blks' for the features highlighted by "
                "'mem_errors'. "
                "Reminder: de-annexed areas may have been selected. Keep "
                "these as NULL.\n"
                "Also, create a new field 'TotNewHU<yy>' and calculate it as "
                "the sum of the appropriate HU fields.\n"
                "When finished, use `redist.save_and_summarize()`.")


# =============================================================================
# FUNCTIONS

def calc_pop(gdb_path=DEFAULT):
    """Join, calculate, and summarize population data.
    Args:
        gdb_path (str): optional argument to allow for changing the data source
    Returns None
    """
    # Get data
    print("Loading data from workspace: {}".format(gdb_path))
    archacks.TOC.refresh()
    archacks.add_all(gdb_path)

    # Set memory workspace
    mem = archacks.MemoryWorkspace()

    # Spatial Join with NCs
    print("Spatial Joining...")
    arcpy.SpatialJoin_analysis(
        "cleaned_blks", "NH Council Boundaries", "in_memory/mem_NC_blks",
        "JOIN_ONE_TO_ONE", "KEEP_ALL", None, "HAVE_THEIR_CENTER_IN")
    # Spatial Join with Wards
    arcpy.SpatialJoin_analysis(
        "mem_NC_blks", "Ward Boundaries", "in_memory/mem_cleaned_blks",
        "JOIN_ONE_TO_ONE", "KEEP_ALL", None, "HAVE_THEIR_CENTER_IN")

    # Join with data tables
    print("Joining with permit data...")
    mem.join_all("mem_cleaned_blks", "GEOID10")

    # Fill NULLs
    print("Filling NULL values...")
    na_fields = archacks.regex_fields(
        "mem_cleaned_blks", "dwellings|NewPop|TotPop|NewHU")
    archacks.fill_na("mem_cleaned_blks", list(na_fields))

    # Add/Calculate Population Field
    print("Calculating new population")
    # Get the most recent year of bp data
    GD["yr"] = str(max([int(f[-2:]) for f in archacks.TOC.keys()
                        if "bp" in f]))
    # Make total population field name
    GD["totpop_field"] = "EstTotPop{}".format(GD["yr"])
    # Add field
    arcpy.AddField_management("mem_cleaned_blks", GD["totpop_field"])
    pop_fields = archacks.regex_fields("mem_cleaned_blks", "NewPop\d{4}")
    # TODO: regex for "TotPop\d{2}"
    pop_calc = "[EstTotPop14]+[{}]".format("]+[".join(pop_fields))
    # Set default value to zero
    arcpy.CalculateField_management(
        "mem_cleaned_blks", GD["totpop_field"], 0, "VB")
    # Actual calculation
    arcpy.CalculateField_management(
        "mem_cleaned_blks", GD["totpop_field"], pop_calc, "VB")

    # Add/Calculate New Dwellings Field
    print("Calculating new units...")
    # Make new dwellings field name
    GD["newhu_field"] = "EstNewHU{}".format(GD["yr"])
    arcpy.AddField_management("mem_cleaned_blks", GD["newhu_field"])
    dwel_fields = archacks.regex_fields("mem_cleaned_blks", "dwellings")
    dwel_calc = "[{}]".format("]+[".join(dwel_fields))
    # Set default value to zero
    arcpy.CalculateField_management(
        "mem_cleaned_blks", GD["newhu_field"], 0, "VB")
    # Actual calculation
    arcpy.CalculateField_management(
        "mem_cleaned_blks", GD["newhu_field"], dwel_calc, "VB")

    # Symbolize
    print("Cleaning up and symbolizing...")
    archacks.TOC.refresh()
    # Cleanup
    [archacks.remove_lyr(rm_lyr) for rm_lyr in RM_LYRS]
    arcpy.ApplySymbologyFromLayer_management(
        "mem_cleaned_blks", "symbology/mem_cleaned_blks.lyr")
    # Highlight Spatial Join errors
    arcpy.Select_analysis("mem_cleaned_blks", "in_memory/mem_errors", fix_qry)
    arcpy.ApplySymbologyFromLayer_management(
        "mem_errors", "symbology/mem_errors.lyr")
    arcpy.SelectLayerByAttribute_management(
        "mem_cleaned_blks", "NEW_SELECTION", fix_qry)
    print("\n" + INSTRUCTIONS)
    return


def check_edits():
    tot17 = 73117  # +3 in deannexed area
    msg = "Total Population lower than in 2017!"
    if archacks.sum_field("mem_cleaned_blks", GD["totpop_field"]) < tot17:
        print(msg)
    elif archacks.sum_field("mem_cleaned_blks", NH_NAME) < tot17:
        print(msg)
    return


def save_and_summarize(save=True):
    """Saves edits to mem_cleaned_blks as table to disk.
    Args:
        save (bool): option to disable the save procedure; for debugging.
    Returns None.
    """
    out_xl = "summary{}.xlsx".format(GD["yr"])
    excel = pd.ExcelWriter(out_xl)
    new_wards = "ward{}".format(GD["yr"])
    # Save
    # TODO: optional not really...
    if save:
        print("Saving...")
        # Set output info
        out_path = DEFAULT + "/MtStPlane"
        out_fc = "pop20{}".format(GD["yr"])
        GD["out_fc"] = out_fc
        keep_fields = [
            "GEOID10", new_wards, NH_NAME,  # "EstNewPop<yr>",
            GD["newhu_field"], GD["totpop_field"]]
        # "Rename" Wards field
        arcpy.AddField_management("mem_cleaned_blks", new_wards)
        arcpy.CalculateField_management(
            "mem_cleaned_blks", new_wards, "[{}]".format(WARD), "VB")
        arcpy.FeatureClassToFeatureClass_conversion(
            "mem_cleaned_blks", "in_memory", "mem_cleaned_blks2")
        archacks.drop_all("mem_cleaned_blks2", keep_fields)
        arcpy.FeatureClassToFeatureClass_conversion(
            "mem_cleaned_blks2", out_path, out_fc)

    # Summarize new output table
    print("Summarizing...")
    # by Ward
    by_ward = archacks.groupby(
        GD["out_fc"], new_wards,
        [GD["newhu_field"], GD["totpop_field"]])
    by_ward.reset_index(inplace=True)
    by_nc = archacks.groupby("mem_cleaned_blks", NH_NAME,
                             [GD["newhu_field"], GD["totpop_field"]])
    by_nc.reset_index(inplace=True)
    tot_pop = int(by_ward.sum()[GD["totpop_field"]])

    # Metics
    print("\nEstimated Total Population: {}".format(tot_pop))
    avg = ceil(tot_pop/6)
    diff = ceil(0.03*avg)  # Is this cheating?
    rng = (int(floor(avg-diff)), int(ceil(avg+diff)))
    c = ["Total Population '{}".format(GD["yr"]),
         "Ward Avg", "+/- 3%", "Min", "Max"]
    metrics = pd.DataFrame({c[0]: tot_pop, c[1]: avg, c[2]: diff,
                            c[3]: min(rng), c[4]: max(rng)}, index=[0])
    metrics = metrics[c]
    print("Summary report exported to: {}".format(out_xl))
    by_nc.to_excel(excel, "by_NC")
    by_ward.to_excel(excel, "by_ward")
    metrics.to_excel(excel, "metrics")

    print("\nDone")
    return


# This here is the pride and joy. Would have saved me a lot of time in 2017...
# Written afterward.
class Analyze(object):
    def __init__(self, gdb, fc, year, pop_field, current_wards):
        self.gdb = gdb
        self.fc = fc
        self.year = year
        self.pop_field = pop_field
        self.current_wards = current_wards
        self.df = pd.DataFrame()
        self.headers = self.df.columns
        self.out_excel = "summary{}.xlsx".format(self.year)
        self._excel_writer = pd.ExcelWriter(self.out_excel)

    def check_scenario(self, scenario):
        """Returns the summary table for the input scenario field."""
        # Column names for output dataframe
        cols = ["Current Est", "Scenario Pop", "Change",
                "+/- from Avg", "% Avg"]
        # Groupby table for all fc attributes
        gb_sum = self.df.groupby(self.current_wards).sum()
        # Current population per ward
        cur_pop = gb_sum[self.pop_field]
        # Population per ward for the given scenario
        scen_pop = self.df.groupby(scenario).sum()[self.pop_field]
        # Difference between current and scenario
        changes = scen_pop - cur_pop
        changes.columns = ["", cols[1]]
        # Calc persons away from average
        from_avg = scen_pop.apply(lambda x: x-self.average)
        # As percent from average
        pct = "{0:.2f}%"
        percent = from_avg.apply(lambda x: pct.format((x/self.average)*100))
        # Combine all dataframes
        t = pd.concat([cur_pop, scen_pop, changes, from_avg, percent], axis=1)
        t.columns = cols
        return t

    def export_table(self, table_name):
        t = getattr(self, table_name)
        print(table_name)
        print(t)
        t.to_excel(self._excel_writer, table_name)
        return # TODO:

    def load(self, use_arcpy=False):
        """Loads an ESRI feature class as a dataframe; arcpy is much slower."""
        if use_arcpy:
            self.df = archacks.tbl2df(self.fc)
            return
        self.df = archacks.gdb2df(self.gdb, self.fc)
        return

    @property
    def total_pop(self):
        """Warning: this data includes populations that have been deannexed."""
        if len(self.df) > 0:
            return self.df[self.pop_field].sum()

    @property
    def ward_pop(self):
        """Accounts for deannexed areas."""
        if len(self.df) > 0:
            t = self.df.groupby(self.current_wards)[self.pop_field].sum()
            return int(t.sum())

    @property
    def average(self):
        """Average population of the wards."""
        if len(self.df) == 0:
            return None
        ward_set = set(self.df[self.current_wards])
        if None in ward_set:
            ward_set.remove(None)
        ward_len = float(len(ward_set))
        return ceil(self.ward_pop/ward_len)

    @property
    def difference(self):
        """3% of the average."""
        if len(self.df) == 0:
            return None
        return ceil(0.03*self.average)

    @property
    def range(self):
        """+/-3% variation from the average."""
        if len(self.df) == 0:
            return None
        mn = int(floor(self.average-self.difference))
        mx = int(ceil(self.average+self.difference))
        return (mn, mx)

    @property
    def metrics(self):
        """Summary table of metrics."""
        if len(self.df) == 0:
            return None
        pop = "Total Population '{}".format(self.year[2:])
        c = [pop, "Ward Avg", "+/- 3%", "Min", "Max"]
        metrics = pd.DataFrame(
            {c[0]: self.ward_pop,
             c[1]: self.average,
             c[2]: self.difference,
             c[3]: min(self.range),
             c[4]: max(self.range)},
            index=[0])
        return metrics[c]


# Only print the documentation if imported into ArcMap's Python Window
if archacks.is_active():
    print(__doc__)
