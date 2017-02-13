# Missoula Ward Redistricting Project
Every odd-year the Ward Boundaries of the City of Missoula must be considered for
an update to ensure all are within 3% of the average population. At least two
scenarios should be made to show how Wards that are higher or lower than +/-3%
could be redistricted to become more equal in population.  
The City of Missoula estimates population increase using a model which uses
the most recent Decennial Census Block data (population, housing occupancy rate,
and average household size) and annual City building permit data.  

    Ann. Population Increase = (New Dwelling Units * Occupancy Rate * Avg Household Size) for each blk  
    Est. Current Population = Census Population + SUM(Annual Population Increase per year since Census)  

## Data  
* The "redist_base.mxd" is a READ-ONLY map file for executing the redistricting script  
* Ward Boundaries and Neighborhood Council Districts are required  
## "redist_data.gdb"
* `cleaned_blks` - a clean dataset of 2010 Census Blocks (Geometry & Block ID)  
* `base` - a table of 2010 Census metrics used to calculate population increase
(Census Population, Occupancy Rate, Avg Household Size)  
* `pop2014_fixed` - Previous Redistricting analysis (2010-2014); used as baseline for 2016-17  
* `pop20XX` - New baseline data created per year  
* Annual Population Increase tables (e.g. "bp2015", "bp2016", etc) - Contain
total new dwelling units and population increase per block)  

## Tools (redist.py)
Using the `redist.py` module should be fairly straight forward:
* Open the `redist_base.mxd` map document  
* Open the Python Window  
* Entering the command `import redist` will load the necessary code and display instructions  
* Use `redist.calc_pop()` to automatically do the procedure in "Processing" below  
* Further instructions should be printed to the console  
* Manually check/edit the Ward and Nhood fields for those features highlighted by the error layer  
* Manually add a field `TotNewHU<yy>` where <yy> is the last two digits of the year  
* Calculate this field as the sum of the appropriate HU fields  
* Use `redist.save_and_summarize()` to export the data and summary report  

## Notes
* Never ever, ever, ever clip data in this project; use Clipping Masks / Definition Queries  
* Employ database table JOINs, etc to reduce exported data  
* Anything multiplied by zero is zero; NULLs should be converted to 0 or appropriate values  


# Processing

## Fixing Casey's Data (`pop2014_fixed`)
Casey Wilson's 2014-15 data had to first be dissolved by GEOID10 (carring
over the HU and population fields using SUM, and the "ward14" using "FIRST"),
then a handful of ward 2 blks needed to be moved into ward 1 (see "2to1.png").  

## Redistricting Procedure
* Open a blank ArcMap document  
* Add the current Ward Boundaries and Neighborhood Council districts  
* Add the "cleaned_blks" feature class  
* Add the tables "pop20XX", "bp2015", "bp2016", and any other years of bp data  
* Join the bp tables in ascending order to the "cleaned_blks" layer  
* Copy/paste the following code into the Python Window to Spatial Join "cleaned_blks" with NCs and Wards:  
* `arcpy.SpatialJoin_analysis("cleaned_blks", "NH Council Boundaries", "in_memory/mem_NCs_blks", "JOIN_ONE_TO_ONE", "KEEP_ALL", None, "HAVE_THEIR_CENTER_IN")`  
* `arcpy.SpatialJoin_analysis("mem_NCs_blks", "Ward Boundaries", "in_memory/mem_ward_blks", "JOIN_ONE_TO_ONE", "KEEP_ALL", None, "HAVE_THEIR_CENTER_IN")`  
* ESRI's Spatial Join tool is far from perfect, so now errors must be manually fixed.
* NOTE: It may be tempting to use "CLOSEST" or others for the Spatial Join, but the Centroid method is best.  
# Manual editing
* Differences between the spatial join and "cleaned_blks" are best shown with
a Def Query similar to `"pop2014_fixed$.ward14" IS NOT NULL` on "cleaned_blks" as shown
in "SpatialJoinErrors.png"  
* Use the following query to manually update the 'Ward_Numbe' field in an Editing Session  

    "Ward_Numbe" IS NULL AND (
    "pop2014_fixed_EstTotPop14" IS NOT NULL 
    OR "bp2015__dwellings" > 0
    OR "bp2016__dwellings" > 0)

* Update old ward AND new ward fields using this query:  

    "pop2014_fixed_ward14" IS NULL 
    AND (
    "bp2015__NewPop2015" > 0
    OR "bp2016__NewPop2016" > 0)

* Convert NULL to 0 for fields used in calculations (dwellings, populations, etc)  
* Create a new column for the current year's total estimated population
* Create a pivot table (or groupby) for total pop by ward and start doing math in Excel
* Note: sorry for the lack of detail down here, the script is really the way to go.  

## Notes for next time
* Make use of the Analyze object to compare scenarios and export tables  
* Change the code a little to guess less i.e. take more field names as parameters or something  
