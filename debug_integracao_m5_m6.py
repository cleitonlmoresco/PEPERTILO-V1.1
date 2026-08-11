import json, subprocess, sys
from pathlib import Path
from extracao_datasheet import extrair_datasheet_detalhado
from integracao_m5_m6 import correlacionar_m5_m6
from roteador import processar_pdf_vetorial

ROOT=Path(__file__).parent

passed=[]; failed=[]
def check(name, cond, detail=''):
    (passed if cond else failed).append({'nome':name,'detalhe':detail})
    print(('PASS' if cond else 'FAIL'), name, detail)

# 1: concordância M5/M6
m5={
 'conexoes':[
   {'tipo':'rede','pinos':[34,46],'funcao':'GND','cor_fio':'BROWN','bitola':'0,50 mm²','pagina_origem':[1],'evidencias':['terminal_fio'],'status':'rede_topologica'},
   {'tipo':'rede','pinos':[32],'funcao':'RESET','pagina_origem':[1],'evidencias':['terminal_fio'],'status':'terminal'},
 ] ,
 'conectores':[{'id':'CON1','terminais':[{'numero':34,'cor_fio':'BROWN','bitola':'0,50 mm²','status':'terminal_com_fio'},{'numero':46,'cor_fio':'BROWN','bitola':'0,50 mm²','status':'terminal_com_fio'},{'numero':32,'status':'terminal_com_fio'}], 'pagina':1}]
}
m6={'registros':[
 {'pino':'34','sinal':'VSS','funcao':'GND','descricao':'Ground','pagina':2,'origem':'pdfplumber','confianca':0.98},
 {'pino':'46','sinal':'VSS','funcao':'VSS','descricao':'Ground','pagina':2,'origem':'pdfplumber','confianca':0.98},
 {'pino':'32','sinal':'RESET','funcao':'RESET','descricao':'Reset input','pagina':2,'origem':'pdfplumber','confianca':0.98},
]}
r=correlacionar_m5_m6(m5,m6)
check('concordância por sinônimo GND/VSS', r['status']=='validado_sem_conflitos' and len(r['concordancias'])>=3, json.dumps(r,ensure_ascii=False))

# 2: conflito não é escondido
m6c={'registros':[dict(x) for x in m6['registros']]}
m6c['registros'][2]['funcao']='GND'
r=correlacionar_m5_m6(m5,m6c)
check('conflito M5 RESET x M6 GND', r['status']=='conflito_requer_revisao' and any(x['pino']==32 for x in r['conflitos']), json.dumps(r,ensure_ascii=False))

# 3: pin only M6
r=correlacionar_m5_m6(m5, {'registros': m6['registros']+[{'pino':'80','sinal':'VDD','funcao':'VDD','pagina':2,'origem':'pdfplumber','confianca':.98}]})
check('pino somente M6 preservado', 80 in r['pinos_somente_m6'])

# 4: real local datasheet extraction, feed correlation
pdf=ROOT/'04_datasheet_local.pdf'
d=extrair_datasheet_detalhado(str(pdf),0)
check('M6 local produz registros', d['total_registros'] >= 5, f"{d['total_registros']} registros")
r=correlacionar_m5_m6(m5,d)
check('correlação com M6 local executa', r['tipo']=='integracao_m5_m6')

# 5: real vector PDF route retains M5 and optionally M6 correlation
vp=ROOT/'03_teste_vetorial_local.pdf'
rr=processar_pdf_vetorial(str(vp))
check('roteador vetorial continua OK', rr.get('status')=='ok' and rr.get('modulo')=='M5', str(rr.get('mensagem')))

report={'passed':len(passed),'failed':len(failed),'tests':passed+failed}
(ROOT/'DEBUG_M5_M6_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':len(passed),'failed':len(failed)},ensure_ascii=False))
if failed: raise SystemExit(1)
