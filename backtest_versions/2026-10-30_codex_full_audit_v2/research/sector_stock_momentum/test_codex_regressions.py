"""Codex fixes: future-label independence and self-financing bankruptcy boundary."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import backtest as bt
import ml2_run as ml
import winners_tracks as wt
from portfolio_accounting import capital_after_costs

class PortfolioRegression(unittest.TestCase):
    def test_fee_paid_before_returns(self):
        k, turn = capital_after_costs({'A': 1}, {}, .001)
        self.assertAlmostEqual(k, 1 / 1.001)
        self.assertAlmostEqual(k + turn * .001, 1)
        self.assertAlmostEqual(k * 1.2 - 1, .19880119880119884)

    def test_switch_self_finances(self):
        k, turn = capital_after_costs({'B': 1}, {'A': 1}, .001)
        self.assertAlmostEqual(k, .999 / 1.001)
        self.assertAlmostEqual(k + turn * .001, 1)

    def test_bankruptcy_is_absorbing(self):
        class PX:
            def ret(self, t, s, r): return (-1 if t.month == 1 else 10), 'ok'
        t = pd.date_range('2020-01-31', periods=3, freq='ME')
        d = wt.run_weights({'px': PX(), 'res': {}, 'rf': pd.Series(dtype=float)}, {x: {'A': 1} for x in t})
        self.assertEqual(d.net.tolist(), [-1., 0., 0.])
        self.assertTrue(d.bankrupt.all())
        self.assertTrue(((1+d.net).cumprod() == 0).all())
        self.assertEqual(d.turnover.iloc[1], 0)

class TimingRegression(unittest.TestCase):
    def setup_case(self, future, missing=False):
        dates = ['2011-01-31', '2012-10-31', '2013-01-31', '2014-10-31', '2014-11-30', '2014-12-31', '2015-01-31']
        X = pd.DataFrame([{'t': pd.Timestamp(t), 'ticker': s, 'mom_rank': i+1, 'status_oo': 'ok',
                           'ret_oo': future if t >= '2014-11-30' and s == 'A' else .1 if s=='A' else 0.}
                          for t in dates for i,s in enumerate(['A','B'])])
        if missing:X.loc[X.t == '2014-12-31', 'ret_oo'] = np.nan
        sessions = pd.bdate_range('2011-01-01','2016-03-01').difference(pd.DatetimeIndex(['2015-01-01']))
        class PX:
            sess = sessions
        S={'px':PX()}
        def predict(kind, p, tr, te, cols):
            self.assertTrue((tr.t <= pd.Timestamp('2014-10-31')).all())
            return (te.ticker == ('A' if p['alpha']==1 else 'B')).astype(float).to_numpy()
        def score(S,W):
            self.assertLessEqual(max(W), pd.Timestamp('2014-10-31'))
            return sum(float(X[(X.t==t)&(X.ticker==s)].ret_oo.iloc[0])*v for t,w in W.items() for s,v in w.items())
        with patch.object(ml,'TEST_YEARS',[2015]), patch.object(ml,'model_fit_predict',predict), patch.object(ml,'net_cagr',score):
            d,c=ml.walk_forward(X,S,'ridge',[],1)
        return d,c

    def test_future_changes_do_not_change_first_decision(self):
        a,ca=self.setup_case(100);b,cb=self.setup_case(-.99)
        self.assertEqual(ca,cb)
        pd.testing.assert_series_equal(a.score,b.score)
        self.assertTrue(a.loc[a.t==pd.Timestamp('2014-12-31'),'score'].notna().all())

    def test_missing_future_return_does_not_remove_candidate(self):
        a,_=self.setup_case(100,missing=True)
        self.assertEqual(len(a[a.t==pd.Timestamp('2014-12-31')]),2)
        self.assertTrue(a.loc[a.t==pd.Timestamp('2014-12-31'),'score'].notna().all())

    def test_exit_comes_after_next_month_end(self):
        sess=pd.to_datetime(['2015-01-02','2015-01-30','2015-02-02'])
        self.assertEqual(ml.label_available_at(pd.Timestamp('2014-12-31'),sess),pd.Timestamp('2015-02-02 23:59:00'))

if __name__ == '__main__': unittest.main()
