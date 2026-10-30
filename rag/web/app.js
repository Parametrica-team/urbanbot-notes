const $ = (id) => document.getElementById(id)
let token = ''
function text(tag, value, className) { const el=document.createElement(tag); el.textContent=value; if(className)el.className=className; return el }
async function init() {
  try {
    const response=await fetch('/api/status'); const data=await response.json()
    if(!response.ok)throw Error(data.error)
    token=data.csrf_token
    $('coverage').textContent=data.coverage
    $('status').textContent=`Фрагментов: ${data.count}. Индекс: ${new Date(data.built_at).toLocaleString('ru')}. Модели: ${data.models.join(', ')}.`
    $('submit').disabled=false
    const seen=new Set()
    for(const item of data.documents.filter(d=>d.verification_status==='verified-snapshot')) {
      if(!seen.has(item.document)){const option=text('option',item.document); option.value=item.document; $('document').append(option);seen.add(item.document)}
      const edition=text('option',item.edition); edition.value=item.edition; $('edition').append(edition)
    }
  } catch(error) { $('coverage').textContent='Сервис пока не готов.'; $('status').textContent=error.message; $('status').className='error' }
}
$('ask').addEventListener('submit',async(event)=>{
  event.preventDefault(); $('submit').disabled=true; $('result').replaceChildren(text('p','Ищу фрагменты и проверяю цитаты…'))
  try {
    const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-RAG-Token':token},body:JSON.stringify({question:$('question').value,document:$('document').value,edition:$('edition').value,include_snapshots:$('snapshots').checked,include_notes:$('notes').checked})})
    const data=await response.json(); if(!response.ok)throw Error(data.error)
    $('result').replaceChildren(text('h2',data.supported?'Найденные основания':'Недостаточно подтверждённых данных'),text('p',data.answer))
    for(const evidence of data.evidence||[]) {
      const s=evidence.source; const card=text('article','','source')
      card.append(text('h3',`${s.document} · ${s.clause}`),text('p',`${s.edition} · ${s.status==='working-note'?'рабочая заметка, не нормативное основание':s.current_verified?'актуальность проверена':'снимок редакции; текущая применимость не подтверждена'}`,'meta'),text('blockquote',evidence.quote))
      const url=new URL(s.source_url); if(url.protocol==='https:') {const a=text('a','Открыть источник ↗');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';card.append(a)}
      const detail=text('details','');detail.append(text('summary','Условия и полный фрагмент'),text('pre',s.context+'\n\n'+s.text));card.append(detail)
      $('result').append(card)
    }
  }catch(error){$('result').replaceChildren(text('p',error.message,'error'))}finally{$('submit').disabled=false}
})
init()
