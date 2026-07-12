import sys, pathlib
BASE = pathlib.Path("/Users/siva/Downloads/MT/Nuclear Power Norway Price")
sys.path.insert(0, str(BASE/"studies"))
sys.path.insert(0, str(BASE/"NordicNuclearAnalysis NY"/"functions"))
from generate_thesis_figures import load_grid, MD_DATA, IC_DATA, sqlpath
from database_functions import getAreaPricesAverageFromDB
from powergama.database import Database

POSTER = {'BL_MD':85.7,'SMR1_MD':71.4,'SMR3_MD':45.2,'SMR6_MD':31.8,
          'BL_IC':159.3,'SMR1_IC':118.6,'SMR3_IC':59.5,'SMR6_IC':38.4}
SIMPLE = {'BL_MD':85.7,'SMR1_MD':63.1,'SMR3_MD':45.2,'SMR6_MD':39.8,
          'BL_IC':159.3,'SMR1_IC':109.7,'SMR3_IC':59.5,'SMR6_IC':42.4}

for tag, ddir in [('MD', MD_DATA), ('IC', IC_DATA)]:
    data = load_grid(ddir)
    for s in ['BL','SMR1','SMR3','SMR6']:
        name=f'{s}_{tag}'
        sql = sqlpath('scenarios', f'nuclear_{tag}', name, 'results', f'powergama_{name}.sqlite')
        db = Database(str(sql))
        vw = getAreaPricesAverageFromDB(data, db, areas=['NO'], timeMaxMin=[0, 262992])['NO']
        print(f"{name:9s}  volume-weighted(DB)={vw:6.2f}  | simple(thesis)={SIMPLE[name]:6.1f}  | poster={POSTER[name]:6.1f}", flush=True)
print("WEIGHT_TEST_DONE")
