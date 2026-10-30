"""Compare official section 8 snapshot with an openly published consolidated edition.
Reads previously downloaded HTML; no approval is made by this script.
"""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import app

class Text(HTMLParser):
    def __init__(self): super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if not self.skip and tag in ('p','div','br','tr','h1','h2','h3'):self.parts.append('\n')
        if not self.skip and tag in ('td','th'):self.parts.append(' | ')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.skip and tag in ('p','div','tr'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
    def text(self):return '\n'.join(line.strip() for line in ''.join(self.parts).splitlines() if line.strip())

def parse(path):
    raw=path.read_bytes()
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('cp1251')
    parser=Text();parser.feed(text);return parser.text()

def clauses(text):
    found=list(re.finditer(r'(?m)^(8\.[12]\.\d+)\.?\s+',text))
    result={}
    for i,m in enumerate(found):
        body=text[m.start():found[i+1].start() if i+1<len(found) else len(text)]
        body=re.split(r'\n(?:8\.2\.?\s|Библиография|Приложение|Судебная практика)',body)[0].strip()
        # Editorial annotations are not part of normative wording.
        body=re.sub(r'\n\([^\n]*(?:ред\.|Приказ|введен|изменен)[^\n]*\)','',body)
        result[m.group(1)]=body
    return result

def normalized(text):
    text=text.lower().replace('ё','е').replace('²','2').replace('\u00a0',' ')
    text=re.sub(r'^(\d+\.\d+\.\d+)\.(?=\s)',r'\1',text)
    text=re.sub(r'(?<!\d),|,(?!\d)','',text)
    # Preserve decimal separators, signs, inequalities, ranges and all words.
    return re.sub(r'\s+','',text)

if __name__=='__main__':
    current=parse(app.STATE/'sp4-current.html')
    change=parse(app.STATE/'sp4-change4.html')
    start=change.find('Утверждено',change.find('659'))
    end=change.find('Популярные статьи',start)
    change=change[start:end].strip()
    if '6.9.27' not in change or 'Ключевые слова' not in change:raise ValueError('Incomplete change text')
    (app.ROOT/'sources/sp4-change4-legalacts.txt').write_text(change,encoding='utf-8',newline='\n')
    actual=clauses(current)
    _,expected=app.load_chunks()
    expected=[c for c in expected if c['id'].startswith('sp4-mchs-ch3:')]
    report=[]
    for item in expected:
        other=actual.get(item['clause'],'')
        report.append({'clause':item['clause'],'match':normalized(item['text'])==normalized(other),'expected':item['text'],'comparison':other})
    (app.STATE/'source-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'clauses':len(report),'matched':sum(r['match'] for r in report),'differences':[r['clause'] for r in report if not r['match']]},ensure_ascii=False))
