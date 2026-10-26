"""Testes de regressão do pipeline vetorial do PEPERTILO V1.1.

Cobrem os bugs corrigidos:
- ECU desenhada como path fechado de retas (sem item `re`);
- pinos alfanuméricos (A1..A30) e rótulos compostos (PINO 20 - INJ1);
- palavras separadas pelo PyMuPDF ("SENSOR 1", "PINO 1");
- limite de páginas na extração.
"""
from pathlib import Path
import sys
import tempfile
import unittest

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extracao_vetorial import (  # noqa: E402
    _retangulo_do_path,
    extrair_primitivas_vetorial,
)
from grafo_rastreador import _pinos_textuais, processar_diagrama  # noqa: E402


class _Ponto:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _texto_central(page, texto, cx, y, tamanho=8):
    largura = pymupdf.get_text_length(texto, fontname='helv', fontsize=tamanho)
    page.insert_text(pymupdf.Point(cx - largura / 2, y), texto, fontsize=tamanho)


class TestPipelineVetorial(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _diag30(self):
        """Diagrama sintético com 30 pinos alfanuméricos e 30 sensores."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(220, 50, 380, 710), color=(0, 0, 0), width=1.5)
        _texto_central(page, 'ECU', 300, 45)
        cores = ['BR', 'AZ', 'VM', 'PT', 'VD', 'LR']
        for i in range(30):
            y = 70 + i * 21
            page.insert_text(pymupdf.Point(224, y + 3), f'A{i + 1}', fontsize=8)
            page.draw_line(pymupdf.Point(220, y), pymupdf.Point(110, y),
                           color=(0, 0, 0), width=0)
            _texto_central(page, f'SENSOR {i + 1}', 92, y + 3)
            _texto_central(page, cores[i % 6], 150, y - 2, 6)
            _texto_central(page, '1.5 mm²', 185, y + 8, 6)
        caminho = self.dir / 'diag30.pdf'
        doc.save(caminho)
        doc.close()
        return caminho

    def _pin_composto(self):
        """Diagrama com rótulo 'PINO 20 - INJ1' em uma única linha visual."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(220, 50, 380, 300), color=(0, 0, 0), width=1.5)
        _texto_central(page, 'ECU', 300, 45)
        page.draw_line(pymupdf.Point(220, 100), pymupdf.Point(110, 100),
                       color=(0, 0, 0), width=0)
        _texto_central(page, 'PINO 20 - INJ1', 85, 103)
        caminho = self.dir / 'pino_composto.pdf'
        doc.save(caminho)
        doc.close()
        return caminho

    def test_diagrama_30_pinos_alfanumericos(self):
        dados = extrair_primitivas_vetorial(str(self._diag30()))
        self.assertEqual(len(dados), 1)
        pagina = dados[1]

        # A ECU é um retângulo `re` e as palavras "SENSOR 1" foram agrupadas.
        self.assertEqual(len(pagina['retangulos']), 1)
        self.assertTrue(any(t['texto'] == 'SENSOR 1' for t in pagina['textos']))
        self.assertTrue(any(t['texto'] == 'A1' for t in pagina['textos']))

        conexoes, _, pinos, _ = processar_diagrama(pagina)

        self.assertEqual(len(pinos), 30)
        self.assertEqual(len(conexoes), 30)
        self.assertEqual({c['pino'] for c in conexoes},
                         {f'A{i}' for i in range(1, 31)})
        self.assertEqual({c['destino'] for c in conexoes},
                         {f'SENSOR {i}' for i in range(1, 31)})

    def test_rotulo_composto_pino_funcao(self):
        dados = extrair_primitivas_vetorial(str(self._pin_composto()))
        conexoes, _, pinos, _ = processar_diagrama(dados[1])

        self.assertEqual(len(pinos), 1)
        self.assertIn('1:PIN:20', pinos)
        self.assertEqual(len(conexoes), 1)
        self.assertEqual(conexoes[0]['pino'], '20')
        self.assertEqual(conexoes[0]['destino'], 'INJ1')

    def test_reconhece_pinos_alfanumericos_e_compostos(self):
        textos = [
            {'texto': 'A1', 'x': 10, 'y': 10},
            {'texto': 'A30', 'x': 20, 'y': 20},
            {'texto': 'PIN 3', 'x': 30, 'y': 30},
            {'texto': 'PINO 20 - INJ1', 'x': 40, 'y': 40},
            {'texto': 'SENSOR 1', 'x': 50, 'y': 50},
            {'texto': 'BR', 'x': 60, 'y': 60},
        ]
        pinos = {p['numero']: p for p in _pinos_textuais(textos)}

        self.assertEqual(set(pinos), {'A1', 'A30', '3', '20'})
        self.assertEqual(pinos['20']['descricao'], 'INJ1')

    def test_retangulo_de_path_fechado(self):
        pontos = [_Ponto(10, 10), _Ponto(100, 10), _Ponto(100, 60),
                  _Ponto(10, 60), _Ponto(10, 10)]
        path = {
            'items': [('m', pontos[0]), ('l', pontos[1]), ('l', pontos[2]),
                      ('l', pontos[3]), ('l', pontos[4])],
            'closePath': True,
        }
        self.assertEqual(_retangulo_do_path(path), (10, 10, 100, 60))

    def test_path_aberto_nao_vira_ecu(self):
        path = {
            'items': [('m', _Ponto(10, 10)), ('l', _Ponto(100, 10)),
                      ('l', _Ponto(100, 60))],
            'closePath': False,
        }
        self.assertIsNone(_retangulo_do_path(path))

    def test_limite_de_paginas(self):
        doc = pymupdf.open()
        for i in range(3):
            page = doc.new_page()
            page.draw_line(pymupdf.Point(10, 10 + i), pymupdf.Point(100, 10 + i))
            page.insert_text(pymupdf.Point(20, 50 + i), f'PAGINA {i + 1}')
        caminho = self.dir / 'tres_paginas.pdf'
        doc.save(caminho)
        doc.close()

        todas = extrair_primitivas_vetorial(str(caminho))
        limitadas = extrair_primitivas_vetorial(str(caminho), limite_paginas=1)

        self.assertEqual(len(todas), 3)
        self.assertEqual(len(limitadas), 1)


if __name__ == '__main__':
    unittest.main()
