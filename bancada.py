from __future__ import annotations
from pathlib import Path
from typing import Dict
from bancada_db import listar_servicos, novo_servico, adicionar_medicao, listar_medicoes, adicionar_nota, listar_notas
from base_programadores import listar_programadores, buscar_programadores_por_familia


def diagnostico_resumo(medicoes):
    alertas=[]
    for m in medicoes:
        status=(m.get('status') or '').lower()
        if status in {'falha','invalido','fora'}:
            alertas.append(m)
    return {'total_medicoes': len(medicoes), 'alertas': alertas, 'status': 'atenção' if alertas else 'sem_alertas'}


def criar_api_bp(app):
    from flask import Blueprint, jsonify, request, render_template
    bp = Blueprint('bancada_api', __name__)

    @bp.route('/bancada')
    def bancada_home():
        return render_template('bancada.html', servicos=listar_servicos())

    @bp.route('/api/bancada/servico', methods=['POST'])
    def api_novo_servico():
        data = request.get_json(silent=True) or {}
        sid = novo_servico(**data)
        return jsonify({'id': sid, 'status': 'ok'})

    @bp.route('/api/bancada/servicos')
    def api_servicos():
        return jsonify({'servicos': listar_servicos()})

    @bp.route('/api/bancada/<servico_id>/medicoes', methods=['GET','POST'])
    def api_medicoes(servico_id):
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            mid = adicionar_medicao(servico_id, **data)
            return jsonify({'id': mid, 'status': 'ok'})
        meds = listar_medicoes(servico_id)
        return jsonify({'medicoes': meds, 'resumo': diagnostico_resumo(meds)})

    @bp.route('/api/bancada/<servico_id>/notas', methods=['GET','POST'])
    def api_notas(servico_id):
        if request.method == 'POST':
            data=request.get_json(silent=True) or {}
            nid=adicionar_nota(servico_id, str(data.get('texto','')).strip())
            return jsonify({'id':nid,'status':'ok'})
        return jsonify({'notas': listar_notas(servico_id)})

    @bp.route('/api/programadores')
    def api_programadores():
        return jsonify({'programadores': listar_programadores()})

    @bp.route('/api/programadores/familia/<familia>')
    def api_programadores_familia(familia):
        return jsonify({'programadores': buscar_programadores_por_familia(familia)})

    app.register_blueprint(bp)
