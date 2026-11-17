import sys,unittest,copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_jsonl
from fac_tinyagent.p81_semantics import semantic_sql_result
DATA=ROOT/'data_ext_p81_diagnosis_20261116';SQL=read_jsonl(DATA/'sql.jsonl')
def row(op,case='ties'):return next(r for r in SQL if r['operation']==op and r['case']==case)
def obs(names):return {'ok':True,'result':{'columns':['name'],'rows':[[x] for x in names]}}
class Tests(unittest.TestCase):
    def test_all_gold(self):
        for r in SQL:self.assertTrue(semantic_sql_result(r,r['expected_observation'],DATA/'probe.sqlite'))
    def test_unspecified_ties_allow_different_subset(self):
        self.assertTrue(semantic_sql_result(row('sort'),obs([f'p81_entity_2_{i}' for i in [1,3,5,6]]),DATA/'probe.sqlite'))
    def test_explicit_tie_rejects_reversed_ids(self):
        self.assertFalse(semantic_sql_result(row('filter_sort_tie'),obs([f'p81_entity_2_{i}' for i in [6,5,4,3]]),DATA/'probe.sqlite'))
    def test_filter_order_free_but_no_missing_rows(self):
        r=row('filter','few')
        self.assertTrue(semantic_sql_result(r,obs(['p81_entity_1_5','p81_entity_1_2']),DATA/'probe.sqlite'))
        self.assertFalse(semantic_sql_result(r,obs(['p81_entity_1_2']),DATA/'probe.sqlite'))
    def test_zero_and_duplicates(self):
        self.assertTrue(semantic_sql_result(row('filter_sort_tie','zero'),obs([]),DATA/'probe.sqlite'))
        self.assertFalse(semantic_sql_result(row('filter_sort','few'),obs(['p81_entity_1_2']*2),DATA/'probe.sqlite'))
    def test_file_factorial_truth(self):
        rs=read_jsonl(DATA/'file.jsonl');self.assertEqual(len(rs),48)
        for r in rs:
            self.assertNotEqual(r['min_line_answer'],r['max_line_answer'])
            self.assertEqual(r['expected_final_answer'],r['min_line_answer'] if r['intent']=='first' else r['max_line_answer'])
            self.assertEqual(r['first_presented_answer'],r['min_line_answer'] if r['presentation']=='ascending' else r['max_line_answer'])
if __name__=='__main__':unittest.main()
