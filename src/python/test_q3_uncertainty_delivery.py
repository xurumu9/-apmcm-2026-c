"""Cluster identity, predictive observation mechanism and failed-replicate handling."""
import unittest
import numpy as np
import pandas as pd
from q3_uncertainty_delivery import load_data,resample,draw_counts,draw_times,interval


class UncertaintyTests(unittest.TestCase):
    def test_cluster_pairing_and_repeated_identity(self):
        d=load_data();before=d.copy(deep=True)
        for unit in ['expID','natural_track']:
            sample,chosen=resample(d,unit,0);again,other=resample(d,unit,0)
            self.assertEqual(chosen,other);pd.testing.assert_frame_equal(sample,again)
            self.assertTrue((sample.groupby('expID').size()==2).all())
            self.assertTrue((sample.groupby('expID')['_source_exp_id'].nunique()==1).all())
            self.assertTrue((sample.groupby('_bootstrap_cluster_id')['_natural_track'].nunique()==1).all())
            self.assertLess(len(set(chosen)),len(chosen))
            if unit=='expID':self.assertEqual(sample.expID.nunique(),139)
        pd.testing.assert_frame_equal(d,before)

    def test_predictive_time_no_response_remains_missing(self):
        grid=pd.DataFrame(index=range(3));fit=(None,np.array([np.log(5),np.log(.5)]),{})
        pred=pd.DataFrame(dict(mass_recorded_zero=[.2,0,0],p_response=[.6,0,1]))
        time,kind=draw_times(grid,fit,pred,np.random.default_rng(1),5000)
        self.assertTrue(np.isnan(time[kind==0]).all());self.assertTrue((time[kind==1]==0).all())
        self.assertTrue(((time[kind==2]>0)&(time[kind==2]<=60)).all())
        self.assertTrue((kind[:,1]==0).all());self.assertTrue((kind[:,2]==2).all())
        self.assertAlmostEqual(np.mean(kind[:,0]==1),.2,delta=.03)

    def test_predictive_count_gate_and_truncation(self):
        grid=pd.DataFrame(index=range(3));fit=(None,np.array([np.log(2),np.log(.5)]),{})
        pred=pd.DataFrame(dict(q_positive=[0,1,.4]))
        values=draw_counts(None,grid,fit,pred,np.random.default_rng(2),5000)
        self.assertTrue((values[:,0]==0).all());self.assertTrue((values[:,1]>=1).all())
        self.assertTrue((values==np.floor(values)).all())
        self.assertAlmostEqual(values[:,1].mean(),2/(1-.25),delta=.15)
        self.assertAlmostEqual(np.mean(values[:,2]>0),.4,delta=.03)

    def test_failed_replicates_not_hidden(self):
        ci=interval([1.,2.,np.nan],3)
        self.assertEqual(ci['bootstrap_success_n'],2)
        self.assertIn('conditional_on_successful',ci['interval_scope'])
        empty=interval([np.nan],1);self.assertTrue(np.isnan(empty['lower']))


if __name__=='__main__':unittest.main()
