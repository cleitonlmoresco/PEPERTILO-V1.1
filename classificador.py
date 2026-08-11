"""M1 - Classificação de documentos técnicos.

A classificação é deliberadamente baseada em evidências: vetores, texto e
estrutura da página. Não usa apenas contagem de objetos.
"""
import os
import pymupdf
from PIL import Image
from logger_erros import logger, monitorar, ErroPipeline, Severidade, tratar_erro_controlado

TIPOS_VALIDOS = {
    'pdf_vetorial': 'PDF com conteúdo vetorial útil para engenharia',
    'pdf_rasterizado': 'PDF predominantemente baseado em imagens',
    'imagem_limpa': 'Imagem digitalizada ou captura limpa',
    'foto_celular': 'Foto de documento/diagrama',
    'manual': 'Documento técnico predominantemente textual/tabelar',
    'desconhecido': 'Tipo não identificado'
}


def get_tipo_arquivo(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    if ext == '.pdf': return 'pdf'
    if ext in ('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp'): return 'imagem'
    logger.warning(f"Extensão não reconhecida: {ext}", extra={'modulo':'M1'})
    return 'desconhecido'


def _contar_primitivas_vetoriais(page):
    drawings = page.get_drawings() or []
    linhas = retangulos = curvas = 0
    for path in drawings:
        for item in path.get('items', ()):
            kind = item[0] if item else None
            if kind == 'l': linhas += 1
            elif kind == 're': retangulos += 1
            elif kind in ('c', 'qu'): curvas += 1
    return linhas, retangulos, curvas, len(drawings)


@monitorar(modulo='M1')
def analisar_vetores_pdf(caminho_pdf):
    doc = pymupdf.open(caminho_pdf)
    stats = {'paginas': len(doc), 'paginas_vetoriais': 0, 'linhas': 0,
             'retangulos': 0, 'curvas': 0, 'drawings': 0, 'texto_chars': 0,
             'texto_palavras': 0}
    try:
        for page in doc:
            l, r, c, d = _contar_primitivas_vetoriais(page)
            stats['linhas'] += l; stats['retangulos'] += r
            stats['curvas'] += c; stats['drawings'] += d
            stats['texto_chars'] += len(page.get_text('text') or '')
            stats['texto_palavras'] += len(page.get_text('words') or [])
            if l + r + c > 0:
                stats['paginas_vetoriais'] += 1
    finally:
        doc.close()
    return stats


@monitorar(modulo='M1')
def possui_camada_vetorial(caminho_pdf, limiar_linhas=5):
    s = analisar_vetores_pdf(caminho_pdf)
    # "Camada vetorial útil" significa que há linhas/curvas suficientes para
    # representar fios/elementos gráficos. Retângulos isolados de tabela não
    # bastam para classificar como diagrama.
    return (s['paginas_vetoriais'] > 0 and
            (s['linhas'] + s['curvas']) >= limiar_linhas)


def analisar_conteudo_pdf(caminho_pdf):
    try:
        s = analisar_vetores_pdf(caminho_pdf)
        linhas = s['linhas'] + s['curvas']
        texto = s['texto_chars']
        # Documento textual/tabelar: muito texto e baixa densidade de fios.
        if texto >= 300 and linhas <= 8 and s['retangulos'] <= 12:
            return 'manual'
        if texto >= 350 and linhas < max(20, texto / 30):
            return 'manual'
        if linhas >= 5:
            return 'diagrama'
        if s['retangulos'] >= 20 and texto >= 350:
            return 'manual'
        return 'misto' if (texto or s['drawings']) else 'vazio'
    except Exception as e:
        logger.warning(f"Erro na pré-classificação: {e}", extra={'modulo':'M1'})
        return 'desconhecido'


@monitorar(modulo='M1')
def analisar_imagem(caminho_imagem):
    if not os.path.exists(caminho_imagem):
        raise ErroPipeline(f"Arquivo não encontrado: {caminho_imagem}", modulo='M1', severidade=Severidade.ALTA)
    with Image.open(caminho_imagem) as img:
        largura, altura = img.size
        proporcao = largura / max(altura, 1)
        exif = img._getexif() if hasattr(img, '_getexif') else None
        fabricante = ''
        if exif: fabricante = str(exif.get(271, ''))
        provavel_foto = bool(exif and any(m in fabricante.lower() for m in ('samsung','apple','xiaomi','motorola','lg')))
        # Proporção isolada é apenas evidência fraca; não deve rotular tudo como foto.
        if abs(proporcao-1.33) < .08 or abs(proporcao-1.78) < .08:
            provavel_foto = provavel_foto and True
    return {'largura':largura,'altura':altura,'proporcao':proporcao,
            'tem_exif':bool(exif),'fabricante':fabricante,'provavel_foto':provavel_foto}


@monitorar(modulo='M1')
def classificar_arquivo(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        raise ErroPipeline(f"Arquivo não encontrado: {caminho_arquivo}", modulo='M1', severidade=Severidade.CRITICA)
    base = get_tipo_arquivo(caminho_arquivo)
    logger.info(f"Classificando arquivo: {os.path.basename(caminho_arquivo)} (tipo base: {base})", extra={'modulo':'M1'})
    if base == 'pdf':
        s = analisar_vetores_pdf(caminho_arquivo)
        categoria = analisar_conteudo_pdf(caminho_arquivo)
        if categoria == 'manual':
            return 'manual'
        if (s['linhas'] + s['curvas']) >= 5 and s['paginas_vetoriais'] > 0:
            return 'pdf_vetorial'
        return 'pdf_rasterizado'
    if base == 'imagem':
        info, erro = tratar_erro_controlado(analisar_imagem, caminho_arquivo,
                                             valor_padrao={'provavel_foto':False}, modulo='M1')
        if erro: logger.warning(f"Falha na análise da imagem: {erro}", extra={'modulo':'M1'})
        return 'foto_celular' if info.get('provavel_foto') else 'imagem_limpa'
    return 'desconhecido'


if __name__ == '__main__':
    import sys
    print(classificar_arquivo(sys.argv[1]))
