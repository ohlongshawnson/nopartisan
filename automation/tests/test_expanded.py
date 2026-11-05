import argparse
from contextlib import redirect_stdout
import copy
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation import expanded as e, pipeline as p, publish as q
from automation.tests.test_publish import FakeGitHub

FIXTURES = Path(__file__).parent/'fixtures/expanded'


def responses(cfg):
    paths={'senate_xml':'senate.xml','congress_csv':'congress.csv','house_xml':'house.xml',
           'whitehouse_administration':'administration.html','whitehouse_cabinet':'cabinet.html','nga_governors':'governors.html'}
    result={}
    for s in cfg['sources']:
        if s['kind']=='feed':
            raw=(FIXTURES.parent/'news.xml').read_bytes()
        else:
            raw=(FIXTURES/paths.get(s['kind'],s['id']+'.html')).read_bytes()
        result[s['url']]=raw
    for f in (FIXTURES/'governors').glob('*.html'):
        result['https://www.nga.org/governors/'+f.stem+'/']=f.read_bytes()
    return result


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.cfg=e.config(p.ROOT/'automation/publishing.json')
        self.raw=responses(self.cfg)
        # Fixtures must not become stale merely because the test date advances.
        clock=patch.object(e,'date')
        self.clock=clock.start()
        self.clock.today.return_value=date(2026,11,5)
        self.addCleanup(clock.stop)

    def collect(self):
        with patch.object(p.Fetcher,'get',side_effect=lambda url:self.raw[url]):
            return e.collect(self.cfg,self.folder)

    def test_complete_collection_aliases_categories_and_rejections(self):
        records=self.collect()
        by_phrase={r['phrase']:r for r in records}
        self.assertIn('bernie sanders',by_phrase)
        self.assertIn('chuck schumer',by_phrase)
        self.assertIn('alexandria ocasio-cortez',by_phrase)
        self.assertIn('jd vance',by_phrase)
        self.assertIn('gavin newsom',by_phrase)
        self.assertIn('republican national committee',by_phrase)
        self.assertIn('democratic national committee',by_phrase)
        self.assertIn('constitution party',by_phrase)
        self.assertIn('dccc',by_phrase)
        self.assertIn('continuing resolution',by_phrase)
        self.assertNotIn('john carter',by_phrase)
        self.assertNotIn('mark green',by_phrase)
        self.assertNotIn('green party',by_phrase)
        self.assertEqual(len(records),len(by_phrase))
        self.assertTrue(all(r['provenance'] for r in records))
        audit=p.load(self.folder/'collection-audit.json')
        self.assertEqual(audit['identities']['house'],438)  # Al Green withheld (singer namesake).
        self.assertEqual(audit['identities']['senate'],100)
        self.assertEqual(audit['identities']['governor'],55)
        self.assertEqual(audit['identities']['cabinet'],21)
        self.assertEqual(audit['identities']['executive'],2)
        self.assertNotIn('al green',by_phrase)
        self.assertNotIn('bill lee',by_phrase)
        self.assertNotIn('john curtis',by_phrase)
        self.assertIn('gov. bill lee',by_phrase)
        for malformed in ['angus s., jr. king','c. franklin','h. griffith','j. correa','j. hill','w. steube']:
            self.assertNotIn(malformed,by_phrase)
        self.assertIn('angus s. king, jr.',by_phrase)
        for former in ['pam bondi','roy cooper','phil murphy','glenn youngkin']:
            self.assertNotIn(former,by_phrase)
        self.assertGreater(len(audit['duplicates']),0)
        self.assertTrue(all(not x['publishable'] for x in p.load(self.folder/'discovery.json')))

    def test_house_completeness_vacancies_and_staleness(self):
        s=next(s for s in self.cfg['sources'] if s['kind']=='house_xml')
        raw=self.raw[s['url']]
        members,audit=e.house_xml(raw,s['checks'])
        self.assertEqual(audit['vacancies'],['FL20','TX23'])
        self.assertEqual(audit['districts'],441)
        root=p.xml(raw)
        root.find('members').remove(root.find('members/member'))
        with self.assertRaisesRegex(ValueError,'district'):
            e.house_xml(p.ET.tostring(root),s['checks'])
        with self.assertRaisesRegex(ValueError,'stale'):
            e.house_xml(raw.replace(b'November 3, 2026',b'January 3, 2025'),s['checks'])
        with self.assertRaisesRegex(ValueError,'future'):
            e.house_xml(raw.replace(b'20250103',b'20270103',1),s['checks'])

    def test_house_mismatched_identity_cannot_publish(self):
        s=next(s for s in self.cfg['sources'] if s['kind']=='house_xml')
        self.raw[s['url']]=self.raw[s['url']].replace(b'B001323',b'B999999')
        with self.assertRaisesRegex(ValueError,'membership sets'):
            self.collect()

    def test_house_wrong_state_party_or_name(self):
        s=next(s for s in self.cfg['sources'] if s['kind']=='congress_csv')
        original=self.raw[s['url']]
        for before,after in [(b'Nicholas',b'Wrongname'),(b',AK,Republican,',b',AL,Republican,'),
                             (b',AK,Republican,',b',AK,Democrat,')]:
            with self.subTest(change=before):
                self.raw[s['url']]=original.replace(before,after)
                with self.assertRaises(ValueError):self.collect()

    def test_cabinet_roles_and_executive_nonoffice_people(self):
        source=next(s for s in self.cfg['sources'] if s['kind']=='whitehouse_cabinet')
        raw=self.raw[source['url']]
        with self.assertRaisesRegex(ValueError,'required department'):
            e.whitehouse(raw.replace(b'Secretary of State',b'Assistant to Somebody'),source['kind'],source['checks'])
        source=next(s for s in self.cfg['sources'] if s['kind']=='whitehouse_administration')
        raw=self.raw[source['url']].replace(b'</main>',b'<h2>First Lady Melania Trump</h2><h2>Celebrity Guest</h2></main>')
        people=e.whitehouse(raw,source['kind'],source['checks'])
        self.assertEqual(len(people),2)

    def test_governor_coverage_and_current_profiles(self):
        s=next(s for s in self.cfg['sources'] if s['kind']=='nga_governors')
        roster=e.governors(self.raw[s['url']],s['checks'])
        alabama=next(r for r in roster if r['state']=='Alabama')
        raw=self.raw[alabama['profile_url']]
        for modified in [raw.replace(b'Current',b'2023'),raw.replace(b'Kay Ivey',b'Wrong Person'),
                         raw.replace(b'January 16, 2023 - Current',b'January 16, 2027 - Current')]:
            with self.assertRaises(ValueError):e.governor_profile(modified,alabama)
        florida=next(r for r in roster if r['state']=='Florida')
        raw=self.raw[florida['profile_url']].replace(b"Governor's Website",b"Governer's Website")
        self.assertTrue(e.governor_profile(raw,florida)['official_url'])
        newjersey=next(r for r in roster if r['state']=='New Jersey')
        self.assertIsNone(e.governor_profile(self.raw[newjersey['profile_url']],newjersey)['official_url'])

    def test_failed_new_source_never_reuses_previous_data(self):
        s=next(s for s in self.cfg['sources'] if s['kind']=='nga_governors')
        self.raw[s['url']]=b'<main><h1>Service unavailable</h1></main>'
        with self.assertRaises(ValueError):self.collect()
        self.assertEqual(p.load(self.folder/'sources.json')[-1]['status'],'failed')

    def test_reviewed_evidence_and_single_word_rejections(self):
        for phrase in ['bill','cabinet','RNC','PAC','primary']:
            with self.assertRaises(ValueError):e.candidate_valid({'phrase':phrase,'category':'legislative_phrase'})
        e.candidate_valid({'phrase':'DCCC','category':'committee'})
        s=next(s for s in self.cfg['sources'] if s['id']=='cpc')
        self.raw[s['url']]=b'<main><h1>Unrelated organization</h1><p>'+b'An unrelated factual page. '*6+b'</p></main>'
        with self.assertRaisesRegex(ValueError,'no longer evidenced'):self.collect()

    def test_news_discovery_is_separate_and_unpublishable(self):
        news=next(s for s in self.cfg['sources'] if s['kind']=='feed')
        self.raw[news['url']]=b'<rss><channel><item><title>Celebrity Example endorses Candidate Unknown</title><link>https://example.org/test</link></item></channel></rss>'
        records=self.collect()
        phrases={r['phrase'] for r in records}
        self.assertNotIn('celebrity example',phrases)
        self.assertNotIn('candidate unknown',phrases)
        discovery=p.load(self.folder/'discovery.json')
        self.assertTrue(any(x['phrase']=='Celebrity Example' for x in discovery))
        with self.assertRaises(ValueError):e.candidate_valid({'phrase':'Celebrity Example','category':'unverified_discovery'})

    def test_complete_publication_review_and_noop(self):
        cfg_path=self.folder/'config.json'
        p.save(cfg_path,self.cfg)
        token=self.folder/'credential';token.write_text('fixture-only');token.chmod(0o600)
        args=argparse.Namespace(config=str(cfg_path),data=str(self.folder/'state'),token_file=str(token),dry_run=False)
        base=p.encode({'schemaVersion':1,'version':'old','keywords':['Joe Biden','political campaign']})
        api=FakeGitHub(base)
        with patch.object(p.Fetcher,'get',side_effect=lambda url:self.raw[url]),redirect_stdout(io.StringIO()):
            result=q.run(args,api)
            self.assertEqual(result['status'],'published')
            result2=q.run(args,api)
        self.assertEqual(result2['status'],'unchanged')
        self.assertEqual(result['version'],result2['version'])
        self.assertEqual(api.files[q.PATHS[0]],api.files[q.PATHS[1]])
        review=p.load(Path(result['run'])/'categorized-diff.json')
        self.assertIn('joe biden',review['retained_without_current_evidence'])
        self.assertEqual(review['removed'],[])
        self.assertIn('committee',review['added_by_category'])
        self.assertEqual(set(json.loads(api.files[q.PATHS[0]])),{'schemaVersion','version','keywords'})

    def test_inspected_hash_gate_before_remote_writes(self):
        cfg_path=self.folder/'config.json';p.save(cfg_path,self.cfg)
        token=self.folder/'credential';token.write_text('fixture-only');token.chmod(0o600)
        args=argparse.Namespace(config=str(cfg_path),data=str(self.folder/'state'),token_file=str(token),dry_run=False,reviewed_sha256='wrong')
        api=FakeGitHub(p.encode({'schemaVersion':1,'version':'v','keywords':['Joe Biden']}))
        with patch.object(p.Fetcher,'get',side_effect=lambda url:self.raw[url]),redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'inspected'):
            q.run(args,api)
        self.assertFalse(any(call[0]!='GET' for call in api.calls))

    def test_alias_is_bound_to_current_holder_and_literal_evidence(self):
        source=next(s for s in self.cfg['sources'] if s['kind']=='whitehouse_cabinet')
        original=self.raw[source['url']]
        self.raw[source['url']]=original.replace(b'<p>Russell Vought</p>',b'')
        with self.assertRaisesRegex(ValueError,'alias no longer evidenced'):
            self.collect()
        # Synthetic future holder: old biography text must not publish the old alias.
        self.raw[source['url']]=original.replace(b'<h2>Russ Vought</h2>',b'<h2>Fixture Person</h2>')
        records=self.collect()
        self.assertNotIn('russell vought',{r['phrase'] for r in records})

    def test_expanded_failure_preserves_remote_and_prior_success(self):
        cfg_path=self.folder/'config.json';p.save(cfg_path,self.cfg)
        token=self.folder/'credential';token.write_text('fixture-only');token.chmod(0o600)
        args=argparse.Namespace(config=str(cfg_path),data=str(self.folder/'state'),token_file=str(token),dry_run=False)
        previous=p.encode({'schemaVersion':1,'version':'prior','keywords':['previous house coverage','Joe Biden']})
        api=FakeGitHub(previous)
        marker=Path(args.data)/'last-success.json';p.save(marker,{'commit':'prior-good'})
        self.raw['https://www.nga.org/governors/virginia/']=b'<h1>Temporary failure</h1>'
        with patch.object(p.Fetcher,'get',side_effect=lambda url:self.raw[url]),self.assertRaises(ValueError):
            q.run(args,api)
        self.assertEqual(api.calls,[])
        self.assertEqual(api.files[q.PATHS[0]],previous)
        self.assertEqual(p.load(marker),{'commit':'prior-good'})


if __name__=='__main__':
    unittest.main()
