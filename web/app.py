"""
PEPERTILO - Módulo 8 / Interface Web
Versão corrigida.

Correções principais:
- Corrige o NameError de resultado_roteador.
- Normaliza e valida a resposta do roteador antes de utilizá-la.
- SECRET_KEY somente por variável de ambiente (sem chave fixa no código).
- Timeout de job no servidor.
- Proteção contra índices/campos inválidos na correção manual.
- Download temporário usa after_this_request, evitando registrar handlers
  globais repetidamente.
- Limpeza de jobs e arquivos antigos.
- Suporte correto a limite_paginas no processamento principal.
"""

import os
import sys
import uuid
import io
import csv
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    current_app,
    after_this_request,
)
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logger_erros import logger, ErroPipeline, Severidade
from roteador import rotear_arquivo, TIPOS_VALIDOS


bp = Blueprint("modulo8", __name__, template_folder="templates")

UPLOAD_FOLDER = Path(__file__).resolve().parent / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

jobs = {}
JOBS_LOCK = threading.RLock()

JOB_EXPIRATION_DAYS = int(os.environ.get("JOB_EXPIRATION_DAYS", "7"))
JOB_TIMEOUT_MINUTES = int(os.environ.get("JOB_TIMEOUT_MINUTES", "5"))

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"
}


def now_iso():
    return datetime.now().isoformat()


def allowed_file(filename, allowed_extensions=None):
    allowed = allowed_extensions or ALLOWED_EXTENSIONS
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed
    )


def atualizar_job(job_id, **kwargs):
    with JOBS_LOCK:
        job = jobs.get(job_id)
        if job is None:
            return False
        job.update(kwargs)
        job["ultima_atualizacao"] = now_iso()
        return True


def criar_job(
    arquivos,
    caminhos,
    nome_modulo="",
    caminho_datasheet=None,
    limite_paginas=0,
):
    job_id = uuid.uuid4().hex[:8]

    job = {
        "id": job_id,
        "arquivos": list(arquivos),
        "caminhos": list(caminhos),
        "caminho_datasheet": caminho_datasheet,
        "nome_modulo": nome_modulo,
        "limite_paginas": max(0, int(limite_paginas or 0)),
        "status": "aguardando",
        "progresso": 0,
        "etapa": "Na fila",
        "resultado": None,
        "erros": [],
        "criado_em": now_iso(),
        "concluido_em": None,
        "ultima_atualizacao": now_iso(),
    }

    with JOBS_LOCK:
        jobs[job_id] = job

    return job_id


def limpar_jobs_antigos():
    agora = datetime.now()
    expiracao = timedelta(days=JOB_EXPIRATION_DAYS)

    with JOBS_LOCK:
        remover = []

        for jid, job in list(jobs.items()):
            if job.get("status") not in ("concluido", "erro"):
                continue

            try:
                criado = datetime.fromisoformat(job["criado_em"])
            except Exception:
                continue

            if agora - criado > expiracao:
                remover.append(jid)

        for jid in remover:
            job = jobs.pop(jid, None)
            if not job:
                continue

            # Remove uploads associados ao job.
            for caminho in job.get("caminhos", []):
                _remover_arquivo(caminho)

            _remover_arquivo(job.get("caminho_datasheet"))
            logger.info(f"Job {jid} removido por expiração")


def _remover_arquivo(caminho):
    if not caminho:
        return

    try:
        Path(caminho).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning(f"Não foi possível remover arquivo temporário: {exc}")


def _normalizar_resultado_roteador(resultado_roteador):
    """
    Valida a estrutura esperada pelo M8.

    O roteador deve retornar:
    {
        'arquivo': ...,
        'tipo': ...,
        'descricao': ...,
        'resultado': {
            'status': 'ok'|'erro',
            ...
        }
    }
    """
    if not isinstance(resultado_roteador, dict):
        raise ErroPipeline(
            "O roteador retornou um resultado inválido.",
            modulo="M8",
            severidade=Severidade.CRITICA,
        )

    tipo = resultado_roteador.get("tipo")
    resultado = resultado_roteador.get("resultado")

    if not tipo:
        raise ErroPipeline(
            "O roteador não informou o tipo do arquivo.",
            modulo="M8",
            severidade=Severidade.CRITICA,
        )

    if not isinstance(resultado, dict):
        raise ErroPipeline(
            "O roteador não retornou o campo 'resultado' como dicionário.",
            modulo="M8",
            severidade=Severidade.CRITICA,
        )

    return resultado_roteador, resultado


def _processar_datasheet_separado(caminho, limite_paginas):
    if not caminho or not Path(caminho).exists():
        return {}

    try:
        from extracao_datasheet import extrair_datasheet

        # Mantém compatibilidade com implementações antigas que aceitam
        # apenas caminho_pdf.
        try:
            resultado = extrair_datasheet(
                caminho,
                limite_paginas=limite_paginas,
            )
        except TypeError:
            resultado = extrair_datasheet(caminho)

        return resultado if isinstance(resultado, dict) else {}

    except Exception as exc:
        logger.warning(f"Erro no datasheet complementar: {exc}")
        return {}


def _resultado_final(resultado_roteador, resultado_roteador_result, job):
    """
    Constrói a estrutura que a interface espera.

    IMPORTANTE:
    Usa somente resultado_roteador_result para os campos internos.
    Isso elimina o bug que causava:
        NameError: name 'resultado_roteador' is not defined
    """
    conexoes = resultado_roteador_result.get("conexoes") or []
    pinos = resultado_roteador_result.get("pinos") or []
    funcoes = resultado_roteador_result.get("funcoes") or {}

    if not isinstance(funcoes, dict):
        funcoes = {}

    # Datasheet enviado separadamente complementa as funções.
    caminho_ds = job.get("caminho_datasheet")
    limite = job.get("limite_paginas", 0)

    funcoes_ds = _processar_datasheet_separado(caminho_ds, limite)
    if funcoes_ds:
        funcoes = {**funcoes, **funcoes_ds}

    return {
        "conexoes": conexoes,
        "pinos": pinos,
        "funcoes": funcoes,
        "num_conexoes": len(conexoes),
        "num_pinos": len(pinos) or len(funcoes),
        "tipo": resultado_roteador.get("tipo", ""),
        "descricao_tipo": resultado_roteador.get("descricao", ""),
        "modulo_processado": resultado_roteador_result.get("modulo", ""),
        "modo": resultado_roteador_result.get("modo", ""),
        "num_paginas": resultado_roteador_result.get("num_paginas", 0),
        "mensagem": resultado_roteador_result.get("mensagem", ""),
        "status_roteador": resultado_roteador_result.get("status", ""),
        "conectores": resultado_roteador_result.get("conectores") or [],
        "topologia": resultado_roteador_result.get("topologia") or [],
        "identificacao_mpu": resultado_roteador_result.get("identificacao_mpu") or {},
        "programadores": resultado_roteador_result.get("programadores") or [],
        "regra_mpu": resultado_roteador_result.get("regra_mpu") or "",
    }


def processar_job_assincrono(job_id):
    def tarefa():
        inicio = datetime.now()

        try:
            with JOBS_LOCK:
                job = jobs.get(job_id)

            if not job:
                return

            atualizar_job(
                job_id,
                status="processando",
                progresso=2,
                etapa="Classificando arquivo",
            )

            caminhos = job.get("caminhos") or []
            if not caminhos:
                raise ErroPipeline(
                    "Nenhum arquivo para processar.",
                    modulo="M8",
                    severidade=Severidade.CRITICA,
                )

            caminho_principal = caminhos[0]

            if not Path(caminho_principal).exists():
                raise ErroPipeline(
                    f"Arquivo não encontrado: {caminho_principal}",
                    modulo="M8",
                    severidade=Severidade.CRITICA,
                )

            limite = int(job.get("limite_paginas") or 0)

            atualizar_job(
                job_id,
                progresso=10,
                etapa="Executando roteador",
            )

            # ==========================================================
            # CORREÇÃO PRINCIPAL:
            # O retorno é armazenado explicitamente em
            # resultado_roteador e resultado_roteador_result.
            # Nunca usar resultado_roteador fora deste escopo sem
            # inicialização.
            # ==========================================================
            resultado_roteador = rotear_arquivo(
                caminho_principal,
                limite_paginas=limite,
            )

            resultado_roteador, resultado_roteador_result = (
                _normalizar_resultado_roteador(resultado_roteador)
            )

            if resultado_roteador_result.get("status") != "ok":
                raise ErroPipeline(
                    resultado_roteador_result.get(
                        "mensagem",
                        "O roteador não conseguiu processar o arquivo.",
                    ),
                    modulo=resultado_roteador.get("tipo", "Roteador"),
                    severidade=Severidade.ALTA,
                )

            atualizar_job(
                job_id,
                progresso=75,
                etapa="Validando resultado",
            )

            # A variável original do roteador foi preservada acima.
            resultado = _resultado_final(
                resultado_roteador,
                resultado_roteador_result,
                job,
            )

            atualizar_job(
                job_id,
                progresso=90,
                etapa="Finalizando resultado",
            )

            # Segurança adicional: não aceitar resultado vazio como
            # sucesso completo.
            if (
                resultado["num_conexoes"] == 0
                and resultado["num_pinos"] == 0
                and not resultado["funcoes"]
            ):
                resultado["qualidade"] = "incompleto"
                resultado["mensagem_qualidade"] = (
                    "O pipeline terminou, mas não encontrou conexões, "
                    "pinos ou funções suficientes para validar o resultado."
                )
            else:
                resultado["qualidade"] = "processado"

            atualizar_job(
                job_id,
                status="concluido",
                progresso=100,
                etapa="Finalizado",
                resultado=resultado,
                concluido_em=now_iso(),
            )

            duracao = (datetime.now() - inicio).total_seconds()
            logger.info(
                f"Job {job_id} concluído em {duracao:.2f}s",
                extra={"modulo": "M8"},
            )

        except ErroPipeline as exc:
            logger.error(
                f"Job {job_id} falhou: {exc.mensagem}",
                extra={"modulo": "M8"},
            )
            atualizar_job(
                job_id,
                status="erro",
                progresso=100,
                etapa=f"Falha: {exc.mensagem[:80]}",
                erros=[exc.to_dict()],
            )

        except Exception as exc:
            logger.critical(
                f"Job {job_id} erro inesperado: {exc}",
                exc_info=True,
                extra={"modulo": "M8"},
            )
            atualizar_job(
                job_id,
                status="erro",
                progresso=100,
                etapa="Erro inesperado",
                erros=[
                    {
                        "mensagem": str(exc),
                        "severidade": "critica",
                        "modulo": "M8",
                    }
                ],
            )

    thread = threading.Thread(
        target=tarefa,
        name=f"PEPERTILO-job-{job_id}",
        daemon=True,
    )
    thread.start()


@bp.route("/")
def index():
    limpar_jobs_antigos()

    with JOBS_LOCK:
        lista_jobs = list(jobs.values())[-20:]

    return render_template(
        "index.html",
        jobs=lista_jobs,
        tipos=TIPOS_VALIDOS,
    )


@bp.route("/carregamento/<job_id>")
def carregamento(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job:
        return redirect(url_for("modulo8.index"))

    return render_template(
        "carregamento.html",
        job_id=job_id,
        job=job,
    )


@bp.route("/upload", methods=["POST"])
def upload():
    if "arquivos" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    arquivos_enviados = request.files.getlist("arquivos")
    datasheet = request.files.get("datasheet")

    nome_modulo = request.form.get(
        "nome_modulo",
        "",
    ).strip()

    try:
        limite_paginas = max(
            0,
            int(request.form.get("limite_paginas", 0) or 0),
        )
    except (TypeError, ValueError):
        limite_paginas = 0

    if not arquivos_enviados or all(
        not f or not f.filename for f in arquivos_enviados
    ):
        return jsonify({"erro": "Nenhum arquivo selecionado"}), 400

    caminhos = []
    nomes_originais = []

    for file in arquivos_enviados:
        if not file or not file.filename:
            continue

        if not allowed_file(file.filename):
            continue

        filename = secure_filename(file.filename)
        nome_unico = f"{uuid.uuid4().hex[:8]}_{filename}"
        caminho = UPLOAD_FOLDER / nome_unico

        try:
            file.save(str(caminho))
            caminhos.append(str(caminho))
            nomes_originais.append(file.filename)
            logger.info(f"Arquivo salvo: {caminho}")
        except Exception as exc:
            logger.error(f"Falha ao salvar upload: {exc}")

    caminho_ds = None

    if datasheet and datasheet.filename:
        if allowed_file(datasheet.filename):
            filename = secure_filename(datasheet.filename)
            nome_ds = f"ds_{uuid.uuid4().hex[:8]}_{filename}"
            caminho_ds_obj = UPLOAD_FOLDER / nome_ds

            try:
                datasheet.save(str(caminho_ds_obj))
                caminho_ds = str(caminho_ds_obj)
                logger.info(f"Datasheet salvo: {caminho_ds}")
            except Exception as exc:
                logger.error(f"Falha ao salvar datasheet: {exc}")

    if not caminhos:
        return jsonify({"erro": "Nenhum arquivo válido"}), 400

    job_id = criar_job(
        arquivos=nomes_originais,
        caminhos=caminhos,
        nome_modulo=nome_modulo,
        caminho_datasheet=caminho_ds,
        limite_paginas=limite_paginas,
    )

    processar_job_assincrono(job_id)

    return jsonify(
        {
            "job_id": job_id,
            "status": "iniciado",
        }
    )


@bp.route("/status/<job_id>")
def status_job(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"erro": "Job não encontrado"}), 404

    criado = datetime.fromisoformat(job["criado_em"])
    expirado = (
        job["status"] == "processando"
        and datetime.now() - criado
        > timedelta(minutes=JOB_TIMEOUT_MINUTES)
    )

    if expirado:
        atualizar_job(
            job_id,
            status="erro",
            etapa="Timeout de processamento",
            erros=[
                {
                    "mensagem": (
                        f"Processamento excedeu {JOB_TIMEOUT_MINUTES} minutos."
                    ),
                    "severidade": "critica",
                    "modulo": "M8",
                }
            ],
        )

        with JOBS_LOCK:
            job = jobs.get(job_id)

    return jsonify(
        {
            "id": job["id"],
            "status": job["status"],
            "progresso": job["progresso"],
            "etapa": job["etapa"],
            "erros": job.get("erros", []),
            "qualidade": (
                job.get("resultado", {}) or {}
            ).get("qualidade"),
        }
    )


@bp.route("/jobs")
def listar_jobs():
    limpar_jobs_antigos()

    with JOBS_LOCK:
        dados = {
            jid: {
                "status": j["status"],
                "progresso": j["progresso"],
                "criado_em": j["criado_em"],
                "concluido_em": j["concluido_em"],
            }
            for jid, j in jobs.items()
        }

    return jsonify(dados)


@bp.route("/resultado/<job_id>")
def ver_resultado(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job or job["status"] != "concluido":
        return redirect(url_for("modulo8.index"))

    resultado = job.get("resultado") or {}

    if resultado.get("modo") == "mpu":
        return render_template(
            "resultado_mpu.html",
            job=job,
            resultado=resultado,
        )

    return render_template(
        "resultado.html",
        job=job,
        resultado=resultado,
    )


@bp.route("/api/conexoes/<job_id>")
def api_conexoes(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"erro": "Job não encontrado"}), 404

    resultado = job.get("resultado") or {}
    funcoes = resultado.get("funcoes") or {}

    if not isinstance(funcoes, dict):
        funcoes = {}

    conexoes_api = []

    for indice, conn in enumerate(resultado.get("conexoes") or []):
        if isinstance(conn, dict):
            pino = conn.get("pino", "")
            destino = conn.get("destino", "")
            cor = conn.get("cor", "")
            bitola = conn.get("bitola", "")
            confianca = conn.get("confianca", 0)
        else:
            conn = list(conn) if isinstance(conn, (tuple, list)) else []
            pino = conn[0] if len(conn) > 0 else ""
            destino = conn[1] if len(conn) > 1 else ""
            cor = conn[2] if len(conn) > 2 else ""
            bitola = conn[3] if len(conn) > 3 else ""
            confianca = conn[4] if len(conn) > 4 else 0

        conexoes_api.append(
            {
                "indice": indice,
                "pino": pino,
                "destino": destino,
                "cor": cor,
                "bitola": bitola,
                "funcao": funcoes.get(pino, "Desconhecida"),
                "confianca": confianca,
            }
        )

    return jsonify(
        {
            "conexoes": conexoes_api,
            "total": len(conexoes_api),
        }
    )


@bp.route("/api/corrigir/<job_id>", methods=["POST"])
def api_corrigir(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"erro": "Job não encontrado"}), 404

    dados = request.get_json(silent=True) or {}

    try:
        indice = int(dados.get("indice"))
    except (TypeError, ValueError):
        return jsonify({"erro": "Índice inválido"}), 400

    campo = dados.get("campo")
    valor = dados.get("valor", "")

    resultado = job.get("resultado") or {}
    conexoes = resultado.get("conexoes") or []

    if not (0 <= indice < len(conexoes)):
        return jsonify({"erro": "Índice inválido"}), 400

    mapeamento = {
        "pino": 0,
        "destino": 1,
        "cor": 2,
        "bitola": 3,
    }

    if campo not in mapeamento:
        return jsonify({"erro": "Campo não permitido"}), 400

    conn = conexoes[indice]

    if isinstance(conn, dict):
        conn[campo] = valor
    else:
        conn = list(conn) if isinstance(conn, (tuple, list)) else []
        posicao = mapeamento[campo]

        while len(conn) <= posicao:
            conn.append("")

        conn[posicao] = valor
        conexoes[indice] = tuple(conn)

    resultado["conexoes"] = conexoes
    resultado["corrigido_manualmente"] = True
    resultado["qualidade"] = "revisado_manualmente"

    with JOBS_LOCK:
        job["resultado"] = resultado

    logger.info(
        f"Correção aplicada: job={job_id}, índice={indice}, campo={campo}"
    )

    return jsonify({"status": "ok"})


@bp.route("/download/<job_id>")
def download_planilha(job_id):
    with JOBS_LOCK:
        job = jobs.get(job_id)

    if not job:
        return jsonify({"erro": "Job não encontrado"}), 404

    if job.get("status") != "concluido":
        return jsonify({"erro": "Job ainda não foi concluído"}), 409

    resultado = job.get("resultado") or {}

    if resultado.get("modo") == "mpu":
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Pino",
                "Lado",
                "Função",
                "Cor do Fio",
                "Ferramenta",
                "Confiança",
            ]
        )

        for pino in resultado.get("pinos") or []:
            if not isinstance(pino, dict):
                continue

            writer.writerow(
                [
                    pino.get("pino", ""),
                    pino.get("lado", ""),
                    pino.get("funcao", ""),
                    pino.get("cor_fio", ""),
                    pino.get("ferramenta", ""),
                    f"{pino.get('confianca', 0)}%",
                ]
            )

        output.seek(0)
        nome_modulo = (
            job.get("nome_modulo") or "MPU"
        ).replace(" ", "_")

        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"pinos_{nome_modulo}.csv",
        )

    conexoes = resultado.get("conexoes") or []

    if not conexoes:
        funcoes = resultado.get("funcoes") or {}

        if funcoes:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Pino", "Função"])

            for pino, func in funcoes.items():
                writer.writerow([pino, func])

            output.seek(0)

            nome_modulo = (
                job.get("nome_modulo") or "Manual"
            ).replace(" ", "_")

            return send_file(
                io.BytesIO(output.getvalue().encode("utf-8-sig")),
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"funcoes_{nome_modulo}.csv",
            )

        return jsonify(
            {
                "erro": (
                    "Nenhum dado confiável foi encontrado para exportar."
                )
            }
        ), 400

    try:
        from consolidacao_exportacao import (
            consolidar_conexoes,
            gerar_excel,
        )

        pin_func = resultado.get("funcoes") or None
        df = consolidar_conexoes(conexoes, pin_func)

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".xlsx",
        )
        tmp.close()

        gerar_excel(df, tmp.name)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(tmp.name)
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(
                    f"Erro ao remover arquivo temporário: {exc}"
                )
            return response

        nome_modulo = (
            job.get("nome_modulo") or "ECU"
        ).replace(" ", "_")

        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=f"pinagem_{nome_modulo}.xlsx",
        )

    except Exception as exc:
        logger.error(
            f"Erro ao gerar planilha: {exc}",
            exc_info=True,
        )
        return jsonify(
            {
                "erro": f"Não foi possível gerar a planilha: {exc}"
            }
        ), 500


@bp.route("/busca")
def busca():
    return render_template("busca.html")


@bp.route("/api/buscar")
def api_buscar():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify(
            {
                "resultados": [],
                "total": 0,
            }
        )

    resultados = []
    termo = query.lower()

    with JOBS_LOCK:
        jobs_snapshot = list(jobs.values())

    for job in jobs_snapshot:
        if job.get("status") != "concluido":
            continue

        nome = job.get("nome_modulo") or ""
        arquivos = " ".join(job.get("arquivos") or [])

        if termo in nome.lower() or termo in arquivos.lower():
            resultados.append(
                {
                    "id": job["id"],
                    "nome": nome or "Sem nome",
                    "arquivos": job.get("arquivos") or [],
                    "data": job.get("concluido_em"),
                    "status": "Concluído",
                }
            )

    return jsonify(
        {
            "resultados": resultados,
            "total": len(resultados),
        }
    )


try:
    from bancada import criar_api_bp
except Exception as _bancada_import_error:
    criar_api_bp = None

def criar_app():
    app = Flask(__name__)

    secret_key = os.environ.get("SECRET_KEY", "").strip()

    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY deve ser definida no ambiente. "
            "No PowerShell use: "
            '$env:SECRET_KEY="uma-chave-local-forte"'
        )

    app.config.update(
        SECRET_KEY=secret_key,
        MAX_CONTENT_LENGTH=int(
            os.environ.get("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024))
        ),
    )

    app.register_blueprint(bp, url_prefix="/")
    if criar_api_bp is not None:
        criar_api_bp(app)

    logger.info(
        "Aplicação PEPERTILO M8 inicializada",
        extra={"modulo": "M8", "funcao": "criar_app"},
    )

    return app


app = criar_app()


if __name__ == "__main__":
    logger.info(
        "Servidor web iniciado",
        extra={"modulo": "M8", "funcao": "main"},
    )

    app.run(
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        use_reloader=False,
    )
