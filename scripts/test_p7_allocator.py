import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fac_tinyagent.p7_allocator import select_action,macro_loss

def rows(a,b):return [{'id':'a','skill':'s1','nll':a},{'id':'b','skill':'s2','nll':b}]
class Tests(unittest.TestCase):
    def test_cost_can_reverse_raw_gain_ranking(self):
        result=select_action(rows(1,1),{'expensive':rows(.4,.4),'cheap':rows(.6,.6)},{'expensive':300,'cheap':100})
        self.assertEqual(result['action'],'cheap')
    def test_cross_skill_harm_is_counted(self):
        result=select_action(rows(1,1),{'overfit':rows(0,2.4),'balanced':rows(.9,.9)},{'overfit':100,'balanced':100})
        self.assertEqual(result['action'],'balanced')
        self.assertLess(result['values']['overfit']['value_per_token'],0)
    def test_changed_question_set_rejected(self):
        altered=rows(.5,.5);altered[0]['id']='unrelated'
        with self.assertRaises(ValueError):select_action(rows(1,1),{'bad':altered},{'bad':100})
    def test_negative_gain_not_disguised(self):
        self.assertFalse(select_action(rows(1,1),{'worse':rows(2,2)},{'worse':100})['positive_gain'])
    def test_skill_macro_not_sample_weight(self):
        data=rows(0,2)+[{'id':'extra','skill':'s1','nll':0}]
        self.assertEqual(macro_loss(data),1)
if __name__=='__main__':unittest.main()
