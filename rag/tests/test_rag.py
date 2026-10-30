import contextlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

def vectors(texts):
    return [[1.0, float('ширин' in t.lower()), float('стен' in t.lower())] for t in texts]

class CorpusTests(unittest.TestCase):
    def test_structured_clauses_are_preserved_in_full(self):
        registry,chunks=app.load_chunks()
        indexed={c['id']:c['text'] for c in chunks}
        for source in registry['documents']:
            if source.get('source_format')!='structured-clauses':continue
            data=json.loads((app.ROOT/source['text_file']).read_text(encoding='utf-8-sig'))
            for row in data['clauses']:
                if row['clause'] in source['included_clauses']:
                    self.assertEqual(indexed[source['id']+':'+row['clause']],row['text'].strip())

    def test_clause_keeps_height_intervals_and_conditions(self):
        _,chunks=app.load_chunks()
        width=next(c for c in chunks if c['clause']=='8.1.4')
        for value in ['3,5 м','4,2 м','6 м','13 м','46 м']:
            self.assertIn(value,width['text'])
        self.assertNotIn('8.1.5',width['text'])
        self.assertIn('Ф1–Ф4',width['context'])
        self.assertFalse(width['current_verified'])

    def test_heading_does_not_leak_between_classes(self):
        _,chunks=app.load_chunks()
        end=next(c for c in chunks if c['clause']=='8.1.16')
        self.assertNotIn('производственным',end['text'])
        self.assertEqual(len([c for c in chunks if c['document']=='СП 4.13130.2013']),43)

    def test_unverified_docs_are_not_indexed(self):
        registry,chunks=app.load_chunks()
        self.assertEqual(len([d for d in registry['documents'] if d['verification_status'].startswith('pending')]),8)
        self.assertEqual(len([c for c in chunks if c['document'].startswith('СанПиН')]),5)
        self.assertFalse(any(c['status'].startswith('pending') for c in chunks))
        self.assertTrue(all(c['status'] in ('verified-snapshot','reviewed-open-text') for c in chunks))

    def test_parking_exceptions_and_related_notes_are_not_lost(self):
        _,chunks=app.load_chunks()
        ramp=next(c for c in chunks if c['document']=='СП 113.13330.2023' and c['clause']=='5.26')
        for phrase in ['20%','14%','не менее 3 м','7,4 м','Примечание']:
            self.assertIn(phrase,ramp['text'])
        approach=next(c for c in chunks if c['document']=='СП 42.13330.2026' and c['clause']=='8.125')
        for phrase in ['одновременного','организация подвоза МГН','1200 м','не допускается']:
            self.assertIn(phrase,approach['text'])
        self.assertFalse(approach['official_text_verified'])
        self.assertEqual(approach['provenance'],'mirror')

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'index.sqlite'
        app.rebuild(db_path=self.db,embedding_fn=vectors)
    def tearDown(self):
        # Windows scanners can transiently reopen just-written SQLite files.
        import time
        for attempt in range(5):
            try:
                self.temp.cleanup()
                return
            except OSError as ex:
                if getattr(ex,'winerror',None) not in (5,32,145) or attempt==4:raise
                app.LOG.warning('Retrying temporary test-directory cleanup: %s',type(ex).__name__)
                time.sleep(0.1)

    def test_current_mode_refuses_snapshot_without_calling_model(self):
        def forbidden(*args): raise AssertionError('Embedding model must not be invoked for empty scope')
        self.assertEqual(app.retrieve('ширина проезда',edition='МЧС: изменения по № 3, 01.12.2022',db_path=self.db,embedding_fn=forbidden),[])

    def test_hybrid_search_and_exact_document_filter(self):
        hits=app.retrieve('8.1.4 ширина проездов',include_snapshots=True,document='СП 4.13130.2013',db_path=self.db,embedding_fn=vectors)
        self.assertIn('8.1.4',[h['clause'] for h in hits])
        self.assertEqual(app.retrieve('ширина проезда',include_snapshots=True,document='СП 999.13330.2020',db_path=self.db,embedding_fn=vectors),[])

    def test_failed_rebuild_keeps_existing_index(self):
        before=self.db.read_bytes()
        def broken(texts): raise RuntimeError('Model offline')
        with self.assertRaises(RuntimeError): app.rebuild(db_path=self.db,embedding_fn=broken,reuse_cache=False)
        self.assertEqual(before,self.db.read_bytes())

    def test_explicit_other_document_cannot_fall_back_to_sp4(self):
        hits=app.retrieve('По СП 113.13330.2023 какая ширина пожарного проезда?',include_snapshots=True,db_path=self.db,embedding_fn=vectors)
        self.assertEqual(hits,[])

    def test_current_question_cannot_use_snapshot_even_when_checkbox_enabled(self):
        self.assertEqual(app.retrieve('Какая действующая ширина пожарного проезда?',edition='МЧС: изменения по № 3, 01.12.2022',include_snapshots=True,db_path=self.db,embedding_fn=vectors),[])

    def test_current_mode_uses_only_crosschecked_clauses(self):
        hits=app.retrieve('ширина пожарных проездов 8.1.4',db_path=self.db,embedding_fn=vectors)
        self.assertTrue(hits)
        self.assertTrue(all(h['current_verified'] for h in hits))
        self.assertFalse(any(h['clause']=='8.2.6' for h in hits))

    def test_yearless_and_no_space_identifiers(self):
        for query in ['по СП4.13130.2013 ширина проезда','по СП 4.13130 ширина проезда']:
            self.assertTrue(app.retrieve(query,db_path=self.db,embedding_fn=vectors))

    def test_parking_wall_distance_is_not_filtered_as_fire_road(self):
        hits=app.retrieve('По СП 113.13330.2023 какое расстояние от стены до колесоотбойного устройства?',db_path=self.db,embedding_fn=vectors)
        self.assertIn('5.40',[h['clause'] for h in hits])
        hits=app.retrieve('По СП 551.1311500.2026 нормируются ли противопожарные расстояния от открытой стоянки до стены жилого здания?',db_path=self.db,embedding_fn=vectors)
        self.assertIn('4.2',[h['clause'] for h in hits])

    def test_future_and_expired_editions_are_not_current(self):
        import datetime as dt
        c={'current_verified':True,'effective_from':'2027-01-01','effective_until':None}
        self.assertFalse(app.current_on(c,dt.date(2026,10,30)))
        c.update(effective_from='2022-01-01',effective_until='2023-12-01')
        self.assertFalse(app.current_on(c,dt.date(2026,10,30)))

    def test_fire_height_boundaries_keep_original_clause_and_warning(self):
        for height in [13,46,75]:
            hits=app.retrieve(f'По СП 4.13130.2013 ширина пожарного проезда для жилого дома высотой {height} м?',db_path=self.db,embedding_fn=vectors)
            self.assertIn('8.1.4',[h['clause'] for h in hits])
            self.assertTrue(next(h for h in hits if h['clause']=='8.1.4')['warnings'])
        self.assertEqual(app.retrieve('По СП 4.13130.2013 ширина пожарного проезда для общественного здания высотой 51 м?',db_path=self.db,embedding_fn=vectors),[])

    def test_historical_industrial_rule_requires_explicit_snapshot(self):
        query='По СП 4.13130.2013 расстояние от края пожарного проезда до стены производственного здания высотой 20 м?'
        self.assertEqual(app.retrieve(query,db_path=self.db,embedding_fn=vectors),[])
        hits=app.retrieve(query,include_snapshots=True,db_path=self.db,embedding_fn=vectors)
        self.assertIn('8.2.6',[h['clause'] for h in hits])
        self.assertFalse(any(h['current_verified'] for h in hits))

    def test_working_notes_need_explicit_mode(self):
        notes=app.load_notes()
        self.assertTrue(notes)
        self.assertTrue(all(c['status']=='working-note' and not c['current_verified'] for c in notes))

    def test_height_outside_scope_is_not_extrapolated(self):
        self.assertEqual(app.retrieve('Ширина проезда для жилого дома высотой 100 м?',db_path=self.db,embedding_fn=vectors),[])

    def test_rebuild_removes_old_rows(self):
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            con.execute("INSERT INTO chunks VALUES ('deleted','{}','[]')");con.commit()
        app.rebuild(db_path=self.db,embedding_fn=vectors)
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM chunks WHERE id='deleted'").fetchone()[0],0)

    def test_unchanged_vectors_are_reused_without_model_calls(self):
        def forbidden(texts):raise AssertionError('Unchanged sources should reuse vectors')
        result=app.rebuild(db_path=self.db,embedding_fn=forbidden)
        self.assertEqual(result['reused_vectors'],result['count'])

class AnswerTests(unittest.TestCase):
    def setUp(self):
        _,chunks=app.load_chunks(); self.source=next(c for c in chunks if c['clause']=='8.1.4')
    def test_exact_quote_accepted(self):
        result={'supported':True,'evidence':[{'id':self.source['id'],'quote':self.source['text']}]}
        self.assertEqual(len(app.validate_evidence(result,[self.source])),1)
    def test_fabricated_numbers_and_citations_rejected(self):
        for result in [
            {'supported':True,'evidence':[{'id':self.source['id'],'quote':'Ширина проезда составляет 999 метров.'}]},
            {'supported':True,'evidence':[{'id':'nonexistent','quote':self.source['text']}]},
            {'supported':True,'evidence':'ignore instructions'},
            {'supported':True,'evidence':[{'id':self.source['id'],'quote':None}]},
        ]: self.assertEqual(app.validate_evidence(result,[self.source]),[])
    def test_no_evidence_is_not_a_normative_answer(self):
        response=app.answer('Требования к бассейну?',retrieval_fn=lambda *a,**k:[])
        self.assertFalse(response['supported'])
    def test_generation_error_is_not_silently_replaced(self):
        def fail(*a): raise RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            app.answer('Ширина?',retrieval_fn=lambda *a,**k:[self.source],generation_fn=fail)

if __name__=='__main__': unittest.main()
