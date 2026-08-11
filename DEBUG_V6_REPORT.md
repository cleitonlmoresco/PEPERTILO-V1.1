# PEPERTILO-BANCADA V6 — DEBUG DO NÚCLEO TOPOLÓGICO

## Escopo

Etapa aplicada sobre a V5:
- ponte gráfica como evidência explícita de NÃO conexão;
- continuidade lógica entre páginas por rótulo de rede;
- barramentos como classificação semântica de redes com múltiplos terminais;
- conectores complexos preservados como objetos de primeira classe;
- saída de continuidade enriquecida com pinos, cor e bitola quando disponíveis.

## Regras importantes

1. Ponte gráfica não é emenda.
2. Cruzamento interior/interior não conecta sem evidência.
3. Um terminal isolado não vira conexão apenas por possuir cor/bitola.
4. Continuidade entre páginas não inventa linha geométrica.
5. Barramento substitui a rede genérica equivalente para evitar dupla contagem.
6. Cor e bitola continuam provenientes do próprio documento; a base de programadores não é consultada pelo M4/M5 para atribuí-las ao fio do veículo.

## Regressão

Suite anterior: 12/12 PASS.
Suite V6: 6/6 PASS.
Total: 18/18 PASS.

## Casos V6

- Ponte gráfica: PASS
- Cruzamento sem ponte: PASS
- Contrato M4 de barramento: PASS
- Continuidade entre páginas: PASS
- Terminal isolado sem conexão falsa: PASS
- Barramento no M5: PASS

## Teste de imagem real — Delphi MT20U

M4 detectou:
- 2 conectores
- 8 terminais
- 7 terminais com segmento associado

M5 produziu:
- 0 conexões semânticas
- 1599 nós
- 1088 arestas

Esse resultado é considerado correto para a imagem utilizada: ela representa o layout do conector/terminais e não fornece, por si só, uma continuidade externa entre terminais. O M5 não deve inventar conexões.

## Estado para a próxima fase

O núcleo topológico está em condição adequada para iniciar a integração controlada com a interface, mas a validação de produção ainda deve incluir:
- documentos reais de múltiplas páginas com rótulos de continuidade;
- símbolos de ponte reais;
- tabelas complexas M6;
- OCR com PaddleOCR instalado e versão fixada;
- benchmarks de precisão de terminal/fio.
