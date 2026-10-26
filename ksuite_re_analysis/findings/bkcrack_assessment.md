# bkcrack — avaliação de viabilidade

## O que é

[bkcrack](https://github.com/kimci86/bkcrack) implementa o ataque de
**texto-conhecido (known-plaintext)** de Biham–Kocher contra o ZipCrypto.
Com ≥12 bytes de plaintext conhecidos, recupera as **chaves internas** e decripta
o arquivo **sem a senha**.

## Por que NÃO serve aqui

1. **Todos os 312 `.ori` são deflate (método 8), nenhum stored.**
2. O bkcrack precisa de bytes conhecidos do **stream comprimido**, não do
   firmware bruto.
3. O deflate depende do arquivo inteiro — adivinhar 12 bytes contíguos do stream
   comprimido é inviável sem ter o `.ori` original exato e reproduzir a mesma
   compressão.

```
Métodos de compressão: {8: 312}   # 8 = deflate
Entradas stored: 0
```

## Quando valeria a pena

- Se algum ZIP tivesse entrada **stored** (método 0) e o conteúdo tivesse um
  cabeçalho de firmware conhecido (ex.: header Bosch/Motorola padrão).
- Se fosse possível obter um `.ori` **idêntico** de outra fonte e reproduzir o
  deflate exato.

## Ferramenta instalada

```
bkcrack 1.8.1 win64 — https://github.com/kimci86/bkcrack/releases
Uso: bkcrack -C alvo.zip -c entrada.ori -p plaintext.bin
```

## Conclusão

**Impraticável para este conjunto.** A força bruta/dicionário e a leitura do
algoritmo no binário são mais viáveis que o bkcrack aqui.
