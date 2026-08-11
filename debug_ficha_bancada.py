import sys, json
from consolidacao_bancada import consolidar_bancada, validar_operacao_programador
from base_programadores import listar_programadores

def run():
    mpu={"modo":"mpu","orientacao":"PIN1_SUPERIOR_ESQUERDO",
         "identificacao":{"identificado":True,"part_number":"MC68HC912BC32",
          "fabricante":"Motorola","familia":"HC12","encapsulamento":"80-pin QFP",
          "pinos":80,"masksets":["9H91F"],"interfaces":["BDM"],
          "status_pinmap":"documental",
          "pin_map":{"32":"RESET","17":"SMODN/TAGHI/BKGD","48":"VSS","47":"VDD"}}}
    integ={"tipo":"integracao_m5_m6","status":"validado_sem_conflitos",
           "mapa_pinos":[
             {"pino":32,"funcao":"RESET","cor_fio":["BLUE"],"bitola":["0,50 mm²"],"status":"concordante"},
             {"pino":48,"funcao":"GND","cor_fio":["BROWN"],"bitola":["0,50 mm²"],"status":"concordante"}],
           "resumo":{"pinos_m5":2,"pinos_m6":2,"concordancias":2,"conflitos":0}}
    f=consolidar_bancada(integ,mpu)
    assert f["status_operacional"]=="pronto_para_analise"
    assert any(x["pino"]==17 and "funcao_mpu" in x for x in f["pinagem"])
    a=validar_operacao_programador(f,"CarProg_A10")
    assert a["habilitado"] is True
    assert a["programador"]["cabos_documentados"][0]["sinais"]["GND"]=="BROWN"
    # conflito bloqueia operação
    integ2=dict(integ); integ2["status"]="conflito_requer_revisao"
    f2=consolidar_bancada(integ2,mpu)
    assert f2["status_operacional"]=="revisao_obrigatoria"
    assert not validar_operacao_programador(f2,"CarProg_A10")["habilitado"]
    # sem pinmap confirmado bloqueia
    mpu2=json.loads(json.dumps(mpu)); mpu2["identificacao"]["status_pinmap"]="sem_pinmap_confirmado"; mpu2["identificacao"]["pin_map"]={}
    f3=consolidar_bancada(resultado_mpu=mpu2)
    assert "PINMAP_NAO_CONFIRMADO" in f3["bloqueios"]
    print("8/8 PASS")
run()
