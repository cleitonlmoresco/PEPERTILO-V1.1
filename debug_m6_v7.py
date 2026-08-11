import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from extracao_datasheet import extrair_datasheet, extrair_datasheet_detalhado

OUT=os.path.join(os.path.dirname(__file__),'test_m6_complex.pdf')

def make_pdf():
 c=canvas.Canvas(OUT,pagesize=A4); w,h=A4
 rows=[('Pin','Signal','Function','Description','Type'),('1','VDD','POWER','Digital supply +5 V','I'),('2','VSS','GND','Circuit ground','P'),('3','RESET','Reset','External reset input','I'),('4','PA0','GPIO','General purpose I/O','I/O'),('5','CANH','CAN','CAN High','I/O'),('6','CANL','CAN','CAN Low','I/O')]
 for page in range(2):
  c.setFont('Helvetica-Bold',12); c.drawString(50,h-50,'MCU COMPLEX DATASHEET - PAGE %d'%(page+1))
  y=h-100
  xs=[50,100,190,260,420]
  c.setFont('Helvetica-Bold',8)
  for x,txt in zip(xs,rows[0]): c.drawString(x,y,txt)
  y-=22; c.setFont('Helvetica',8)
  subset=rows[1:] if page==0 else [('7','PB0','GPIO','General purpose I/O','I/O'),('8','PB1','GPIO','General purpose I/O','I/O'),('9','TXD','SCI','Serial transmit','O'),('10','RXD','SCI','Serial receive','I'),('11','VREF','Reference','Reference voltage','I'),('12','GND','Ground','\nPower ground','P')]
  for row in subset:
   for x,txt in zip(xs,row): c.drawString(x,y,str(txt).replace('\\n',' '))
   y-=22
  c.showPage()
 # third page: continuation row without pin + no grid
 c.setFont('Helvetica-Bold',12); c.drawString(50,h-50,'PIN DESCRIPTION CONTINUATION')
 c.setFont('Helvetica',8); y=h-100
 for txt in ['Pin','Signal','Function','Description']:
  pass
 c.drawString(50,y,'13'); c.drawString(100,y,'BOOT'); c.drawString(190,y,'Boot'); c.drawString(260,y,'Boot mode select input');
 y-=18; c.drawString(260,y,'Must be sampled during reset.'); y-=18
 c.drawString(50,y,'14'); c.drawString(100,y,'CLK'); c.drawString(190,y,'Clock'); c.drawString(260,y,'External clock input');
 c.save()

make_pdf()

r=extrair_datasheet_detalhado(OUT)
print(json.dumps({'total':r['total_registros'],'pages':r['paginas_processadas'],'backend':r['backend'],'tables':r['tabelas'],'sample':r['registros'][:3]},ensure_ascii=False,indent=2))
assert r['total_registros']==14, r['total_registros']
assert set(r['paginas_processadas'])=={1,2,3}
legacy=extrair_datasheet(OUT)
assert len(legacy)==14, len(legacy)
limited=extrair_datasheet(OUT,limite_paginas=1,detalhado=True)
assert limited['paginas_processadas']==[1]
assert limited['total_registros']==6
print('M6_COMPLEX_TESTS: 4/4 PASS')
