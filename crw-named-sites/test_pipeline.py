"""Targeted scientific checks; run with python test_pipeline.py."""
import unittest
from datetime import date, timedelta
from pull_sites import summarize, region_summary, discover_sites, parse_site

class Checks(unittest.TestCase):
    def test_site_discovery_deduplicates_and_excludes_regional_products(self):
        page='https://www.coralreefwatch.noaa.gov/product/vs_single_pixel_exp/example.php'
        html='''<a href="data/site.txt">site</a><a href="data/site.txt">again</a>
        <a href="../vs/data/region.txt">regional</a>
        <a href="https://example.com/product/vs_single_pixel_exp/data/other.txt">external</a>'''
        self.assertEqual(discover_sites(html,page), ['https://www.coralreefwatch.noaa.gov/product/vs_single_pixel_exp/data/site.txt'])
    def test_non_ascii_site_and_missing_days(self):
        raw='''Name:
Kāneʻohe Bay
Latitude:
21.475
Longitude:
-157.825
Maximum Monthly Mean:
27.2
YYYY, MM, DD, SST, SSTA, HS, DHW
2024, 2, 1, 25, -999.0, 0, 0
2024, 2, 3, 26, 0, 0, 0
'''
        meta, daily=parse_site(raw,'https://example.com/site.txt','hawaii')
        self.assertEqual(meta['name'],'Kāneʻohe Bay')
        self.assertIsNone(daily[0]['ssta_c'])
        self.assertIsNone(summarize(daily)[0]['sst_c'])
    def daily(self, days=29):
        return [dict(date=(date(2024,2,1)+timedelta(days=i)).isoformat(),sst_c=20+i,ssta_c=1,hotspot_c=1,dhw_c_weeks=i) for i in range(days)]
    def test_complete_month_and_peak(self):
        r=summarize(self.daily())[0]
        self.assertEqual(r['sst_c'],34)
        self.assertEqual(r['peak_dhw_c_weeks'],28)
    def test_missing_days_are_not_filled(self):
        r=summarize(self.daily(28))[0]
        self.assertIsNone(r['sst_c'])
        self.assertEqual(r['valid_days_sst_c'],28)
    def test_equal_weights_and_duplicate_pixels(self):
        monthly=lambda v:[dict(month='2024-02',sst_c=v,ssta_c=v,peak_dhw_c_weeks=v)]
        sites=[dict(id='a',lat=10,lon=20,monthly=monthly(20)),dict(id='alias',lat=10,lon=20,monthly=monthly(20)),dict(id='b',lat=10,lon=21,monthly=monthly(30))]
        r=region_summary(sites)[0]
        self.assertEqual(r['n_expected'],2)
        self.assertEqual(r['sst_c'],25)
        sites[-1]['monthly'][0]['sst_c']=None
        r=region_summary(sites)[0]
        self.assertIsNone(r['sst_c'])
        self.assertEqual(r['n_sst_c'],1)

if __name__=='__main__': unittest.main()
