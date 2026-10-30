"""Stage open consolidated texts without silently approving them for normative answers.

Uses only Python stdlib. Tables retain cell spans and row boundaries for later QA.
"""
from html.parser import HTMLParser
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT=Path(__file__).resolve().parent
STAGING=ROOT/'.state/source-candidates'
SOURCES=[
    ('sp113','СП 113.13330.2023','02.09.2026','https://legalacts.ru/doc/prikaz-minstroja-rossii-ot-05102023-n-718pr-ob-utverzhdenii/'),
    ('sanpin3684','СанПиН 2.1.3684-21','10.09.2026','https://legalacts.ru/doc/postanovlenie-glavnogo-gosudarstvennogo-sanitarnogo-vracha-rf-ot-28012021-n/'),
    ('sanpin3685','СанПиН 1.2.3685-21','24.12.2025','https://legalacts.ru/doc/postanovlenie-glavnogo-gosudarstvennogo-sanitarnogo-vracha-rf-ot-28012021-n_2/'),
]

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.stack=[];self.cell=None;self.before=''
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='table':
            labels=re.findall(r'Таблица\s+[\d.]+',self.before)
            self.stack.append({'label':labels[-1] if labels else None,'preceding_context':self.before[-1000:],'rows':[]})
        elif self.stack and tag=='tr':self.stack[-1]['rows'].append([])
        elif self.stack and tag in ('td','th'):
            self.cell={'type':tag,'rowspan':int(attrs.get('rowspan','1')),'colspan':int(attrs.get('colspan','1')),'text':'','images':[]}
        elif self.cell is not None and tag in ('p','br','div'):self.cell['text']+='\n'
        elif self.cell is not None and tag in ('sup','sub'):self.cell['text']+=('^{' if tag=='sup' else '_{')
        elif self.cell is not None and tag=='img':
            self.cell['images'].append({'src':attrs.get('src'),'alt':attrs.get('alt',''),'requires_review':True})
            self.cell['text']+='[FORMULA/IMAGE: '+attrs.get('alt','')+']'
        elif self.cell is None and tag in ('sup','sub'):self.before+=('^{' if tag=='sup' else '_{')
    def handle_data(self,data):
        if self.cell is not None:self.cell['text']+=data
        elif not self.stack:self.before=(self.before+data)[-2000:]
    def handle_endtag(self,tag):
        if tag in ('sup','sub') and self.cell is not None:self.cell['text']+='}'
        elif tag in ('sup','sub'):self.before+='}'
        if tag in ('td','th') and self.cell is not None and self.stack:
            if not self.stack[-1]['rows']:self.stack[-1]['rows'].append([])
            self.cell['text']=self.cell['text'].strip()
            self.stack[-1]['rows'][-1].append(self.cell);self.cell=None
        elif tag=='table' and self.stack:self.tables.append(self.stack.pop())

if __name__=='__main__':
    STAGING.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for id,document,edition,url in SOURCES:
        file=STAGING/(id+'.html')
        if not file.exists():
            with urllib.request.urlopen(url,timeout=60) as response:raw=response.read()
            file.write_bytes(raw)
        raw=file.read_bytes();html=raw.decode('utf-8-sig')
        header=re.search(r'<h1\b[^>]*>(.*?)</h1>',html,re.S|re.I)
        header=re.sub('<[^>]+>','',header.group(1)).strip() if header else ''
        if document not in html or edition not in html:raise ValueError(f'Wrong document or edition: {id}')
        parser=TableParser();parser.feed(html)
        if parser.stack:raise ValueError(f'Unclosed tables: {id}')
        output=STAGING/(id+'.tables.json')
        output.write_text(json.dumps(parser.tables,ensure_ascii=False,indent=2),encoding='utf-8')
        record={'id':id,'document':document,'edition_claimed_by_publisher':edition,'source_url':url,
            'source_type':'secondary-consolidated-publication','status':'staged-not-approved',
            'downloaded_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),
            'bytes':len(raw),'tables':len(parser.tables),'cells':sum(len(row) for t in parser.tables for row in t['rows']),
            'spanning_cells':sum(cell['rowspan']>1 or cell['colspan']>1 for t in parser.tables for row in t['rows'] for cell in row),
            'image_cells_requiring_review':sum(bool(cell['images']) for t in parser.tables for row in t['rows'] for cell in row),
            'title':header,'required_review':['full-text completeness','effective dates of each amendment','tables, spans, units and notes','clause applicability','independent source comparison']}
        manifest.append(record)
        print(json.dumps({k:record[k] for k in ('id','bytes','tables','cells','spanning_cells')},ensure_ascii=False),flush=True)
    (ROOT/'acquisition.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
