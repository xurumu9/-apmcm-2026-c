"""Audit edge cases: preserve uncertain boundaries and raw values, distinguish conflicts."""
import unittest
import numpy as np
import pandas as pd
from q3_duration_diagnostics import audit_duration,record_distribution


class DurationAuditTests(unittest.TestCase):
    def test_boundary_is_not_automatically_censoring_or_exclusion(self):
        d=pd.DataFrame(dict(expID=[1,2,3,4,5],CallType=['flat']*5,Context=['after']*5,Date=['x']*5,
            HeadsUpYesNo=[1,1,0,0,1],HeadsUpLatency=[0,5,np.nan,5,np.nan],HeadsUpDuration=[60,60,0,0,10]))
        before=d.copy(deep=True);a=audit_duration(d,'HeadsUp')
        self.assertTrue(a.loc[0,'eligible_positive_record'])
        self.assertTrue(a.loc[0,'unresolved_boundary'])
        self.assertTrue(a.loc[1,'latency_plus_duration_gt_window'])
        self.assertFalse(a.loc[1,'eligible_record'])
        self.assertTrue(a.loc[2,'eligible_record'])
        self.assertTrue(a.loc[3,'flag_latency_conflict'])
        self.assertTrue(a.loc[4,'flag_latency_conflict'])
        self.assertFalse(a.duration_encoding_verified.any())
        pd.testing.assert_frame_equal(d,before)

    def test_working_density_normalization_and_distinct_mean_median(self):
        from scipy.integrate import quad
        for family in ['gamma','lognormal']:
            base=record_distribution(family,np.array([3.]),.3)
            mass=quad(lambda y:base.pdf(y)[0],0,np.inf)[0]
            self.assertAlmostEqual(mass,1,places=7)
            self.assertGreater(base.mean()[0],base.ppf(.5)[0])
            # Unbounded working-record tail remains visible; no clipping at 60.
            self.assertGreater(base.sf(60)[0],0)


if __name__=='__main__':
    unittest.main()
