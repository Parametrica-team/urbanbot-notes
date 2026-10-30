"""Reproducible DOCX extraction and source registry. Does not approve new sources."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import hashlib
import json

ROOT=Path(__file__).resolve().parent
W={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def extract_docx(file):
    with ZipFile(file) as archive:
        root=ET.fromstring(archive.read('word/document.xml'))
    body=root.find('w:body',W)
    lines=[]
    for node in body:
        if node.tag.endswith('}p'):
            lines.append(''.join(t.text or '' for t in node.findall('.//w:t',W)))
        elif node.tag.endswith('}tbl'):
            # Explicit row and cell boundaries; no flattening of table values into prose.
            lines.append('[TABLE]')
            for row in node.findall('w:tr',W):
                lines.append(' | '.join(' / '.join(''.join(t.text or '' for t in p.findall('.//w:t',W)) for p in cell.findall('.//w:p',W)) for cell in row.findall('w:tc',W)))
            lines.append('[/TABLE]')
    return '\n'.join(lines)

if __name__=='__main__':
    file=ROOT/'sources/sp4-mchs.docx'
    expected='fecdffa84cdc7fafa026d6ec99c12a8b40323b844c266e74744cdb6acb5ff5d5'
    if hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
        raise ValueError('Source changed. A new file requires explicit review, not automatic approval.')
    output=ROOT/'sources/sp4-mchs.txt'
    output.write_text(extract_docx(file),encoding='utf-8',newline='\n')
    registry={
      'schema_version':1,
      'coverage':'Первый корпус: раздел 8 СП 4.13130.2013 из официального DOCX МЧС с изменением № 3. Текущая редакция с № 4 полностью не сверена. Остальные СП и СанПиН пока в очереди; подтверждённых актуальных нормативных ответов нет.',
      'documents':[{
        'id':'sp4-mchs-ch3', 'document':'СП 4.13130.2013',
        'edition':'МЧС: изменения по № 3, 01.12.2022',
        'verification_status':'verified-snapshot', 'current_verified':False,
        'effective_from':'2022-12-01', 'effective_until':None,
        'checked_at':'2026-10-30', 'included_prefixes':['8.1.','8.2.'],
        'scope_context':'Проверенный снимок текста МЧС, раздел 8. Актуальность после изменения № 4 не подтверждена. Пункт 1.2 исключает Ф1.3 выше 75 м, прочие классы выше 50 м и специальные объекты с перечисленными исключениями. Применимость к конкретному проекту не установлена.',
        'scopes':{'8.1':'Раздел 8.1: жилые и общественные здания, классы Ф1–Ф4. Не переносить требования для Ф5.',
                  '8.2':'Раздел 8.2: производственные и складские здания, класс Ф5. Не переносить требования для Ф1–Ф4.'},
        'source_url':'https://mchs.gov.ru/dokumenty/vse-dokumenty/6667',
        'download_url':'https://mchs.gov.ru/uploads/document/2023-05-25/381ce09fdac7d762943edd0a37a53357.docx',
        'registry_url':'https://protect.gost.ru/sp/details/fe915813-95ec-43a6-ab1c-91027e06bf1c',
        'raw_file':'sources/sp4-mchs.docx','raw_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
        'text_file':'sources/sp4-mchs.txt','text_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'verification_note':'Скачан официальный DOCX; структура раздела 8 и значения ширин сверены. В документе перечислены приказы до 610 от 15.06.2022. В реестре найдено изменение № 4; просмотр полного текста изменения требует авторизации, поэтому current_verified=false. Число 13 м встречается в двух интервалах: не разрешать неоднозначность автоматически.'
      }]
    }
    pending=[('sp42-2026','СП 42.13330.2026'),('sp476','СП 476.1325800.2020'),('sp396','СП 396.1325800.2018'),('sp113','СП 113.13330.2023'),('sp59','СП 59.13330.2020'),('sp551','СП 551.1311500.2026'),('sanpin3684','СанПиН 2.1.3684-21'),('sanpin3685','СанПиН 1.2.3685-21')]
    for id,document in pending:
        registry['documents'].append({'id':id,'document':document,'verification_status':'pending-full-text-review','current_verified':False,'edition':None,'reason':'Карточка или рабочая выжимка не заменяет сверку полного нормативного текста; не включён в ответы.'})
    target=ROOT/'registry.json'
    if target.exists():
        # Never overwrite approvals or additional sources in an established registry.
        existing=json.loads(target.read_text(encoding='utf-8-sig'))
        record=next((d for d in existing['documents'] if d['id']=='sp4-mchs-ch3'),None)
        if record:
            record['raw_sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
            record['text_sha256']=hashlib.sha256(output.read_bytes()).hexdigest()
        registry=existing
        target=ROOT/'registry.candidate.json'
    target.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Extracted source; wrote {target.name}. Existing registry approvals were not changed.')
