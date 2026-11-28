"""Numerical checks for custom Q3 likelihoods; no experiment outputs or raw edits."""
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import poisson, nbinom, lognorm, weibull_min
from statsmodels.discrete.truncated_model import TruncatedLFPoisson, TruncatedLFNegativeBinomialP

from q3_count_latency_models import count_logpmf, log_nonzero, time_logs, time_quantile, positive_time_mean


class LikelihoodTests(unittest.TestCase):
    def test_count_likelihood_against_library(self):
        y=np.array([1,2,4,10]);x=np.column_stack([np.ones(4),np.arange(4)/3]);beta=np.array([.3,.4]);la=-.4
        for family in ['poisson','nb2']:
            lp,p0=count_logpmf(y,x@beta,family,la)
            model=TruncatedLFPoisson(y,x) if family=='poisson' else TruncatedLFNegativeBinomialP(y,x,p=2)
            params=beta if family=='poisson' else np.r_[beta,np.exp(la)]
            np.testing.assert_allclose(lp-log_nonzero(p0),model.loglikeobs(params),rtol=1e-9)
            for mu in [.1,1,10]:
                lp,p0=count_logpmf(np.arange(1,10000),np.full(9999,np.log(mu)),family,la)
                self.assertAlmostEqual(np.exp(lp-log_nonzero(p0)).sum(),1,places=9)

    def test_time_density_cdf_and_mean(self):
        for family,dist in [('lognormal',lognorm),('weibull',weibull_min)]:
            for eta,h in [(0.,0.),(2.,-.3),(5.,.2)]:
                shape=np.exp(h);base=dist(shape,scale=np.exp(eta))
                t=np.array([.01,1.,10.,60.]);lp,lc,ls=time_logs(t,eta,h,family)
                np.testing.assert_allclose(lp,base.logpdf(t),rtol=1e-8)
                np.testing.assert_allclose(lc,base.logcdf(t),atol=1e-12)
                np.testing.assert_allclose(ls,base.logsf(t),atol=1e-12)
                f60=base.cdf(60)
                mass=quad(lambda s:base.pdf(s)/f60,0,60,epsabs=1e-8)[0]
                self.assertAlmostEqual(mass,1,places=7)
                u=np.array([.1,.5,.9]);q=time_quantile(u,np.repeat(eta,3),h,family)
                np.testing.assert_allclose(base.cdf(q)/f60,u,rtol=1e-8)
                reference=quad(lambda s:s*base.pdf(s)/f60,0,60,epsabs=1e-8)[0]
                calculated=positive_time_mean(np.array([eta]),h,family)[0]
                self.assertAlmostEqual(calculated,reference,delta=2e-4)

    def test_zero_not_a_continuous_time(self):
        for family in ['lognormal','weibull']:
            with self.assertRaises(AssertionError):
                time_logs(np.array([0.]),0.,0.,family)


if __name__=='__main__':
    unittest.main()
