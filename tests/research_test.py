"""Research reproducibility, observation separation and saved-data scoring."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
server=module('research_server','lab/server.py');calibration=module('probe_calibration','tools/calibrate_probe.py')
s=server.research.scenarios
class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lab=server.Lab()
    def test_disjoint_reproducible_scenario_sets(self):
        a=s.generate(server.DEFAULTS,30,42,'development',True);b=s.generate(server.DEFAULTS,30,42,'evaluation',True)
        self.assertEqual(a,s.generate(server.DEFAULTS,30,42,'development',True));self.assertFalse({v['seed'] for v in a}&{v['seed'] for v in b})
    def test_observation_errors_never_modify_thermal_state(self):
        definition=s.scenario(server.DEFAULTS,42,errors={'temperature_bias_c':.5,'position_bias_m':.1,'dropout_probability':0})
        p=s.ObservationPipeline(definition,'fast');obs=p.observe(50,22.,.2,.03,.05)
        self.assertAlmostEqual(obs['depth_m'],.3);self.assertGreater(obs['temperature_c'],22.4)
        self.assertNotIn('true_gradient',obs);self.assertNotIn('reference_temperature_c',obs)
        definition['errors']['dropout_probability']=1
        self.assertIsNone(p.observe(100,22.,.2,.03,.05))
    def test_saved_scores_exact_and_failed_boundaries_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            result=server.research.run_comparison(self.lab.core,server.DEFAULTS,self.lab.native_config,repeats=2,seed=31,output=Path(temp)/'run',methods=['medium','response','ungated'],budget_s=30)
            saved=server.research.evaluation.evaluate_saved(Path(temp)/'run')
            self.assertEqual(saved['metrics'],result['metrics']);self.assertEqual(saved['paired'],result['paired'])
            self.assertTrue(any(m['boundary_failed'] for m in result['metrics']))
            self.assertTrue(all(m['full_profile_rmse_c'] is None for m in result['metrics']))
            self.assertTrue(all(not t['full_profile_complete'] for t in result['trials']))
            with self.assertRaises(ValueError):server.research.run_comparison(self.lab.core,server.DEFAULTS,self.lab.native_config,output=Path(temp)/'run')
    def test_synthetic_calibration_identifies_known_tau(self):
        times=[i*.1 for i in range(301)];values=[19+3*math.exp(-t/2.3) for t in times]
        fit=calibration.fit_step(times,values)
        self.assertLess(abs(fit['tau_s']-2.3),.02);self.assertLess(fit['residual_rmse_c'],.005);self.assertTrue(fit['duration_at_least_five_tau'])
        with self.assertRaises(ValueError):calibration.fit_step(times,[22.]*len(times))
if __name__=='__main__':unittest.main()
