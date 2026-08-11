# PEPERTILO Bancada V3 — M4/M5/MPU PRO

## Alterações desta versão

### M4 — percepção elétrica
- adiciona objetos `conectores`;
- detecta terminais numéricos dentro/próximos de conectores;
- associa cor e bitola a segmentos quando a evidência está no próprio documento;
- mantém `fonte=documento` para impedir mistura com cores de cabos de programadores.

### M5 — topologia
- reconstrói segmentos antes de montar o grafo;
- junção T conecta sem exigir bolinha;
- cruzamento interior/interior permanece separado sem evidência de junção;
- cruzamento com ponto de junção conecta;
- snap de endpoints;
- redes são agrupadas em objetos com `pinos`, `funcao`, `cor_fio`, `bitola`, `pagina_origem`;
- pino isolado não é contado como conexão;
- conectores são objetos de primeira classe;
- continuidade entre páginas permanece preparada por referências de folha/página.

### MPU PRO
Fluxo novo:

`MCU → part number → família → encapsulamento → pin 1/orientação → pin map documental → coordenadas`

Não há mais cálculo do número do pino a partir de `x/y`.

Base documental inicial inclui MC68HC912B32/BC32 em 80-pin QFP. O pin-map foi alinhado com o datasheet Motorola: RESET=32, EXTAL=33, XTAL=34, BKGD=17, VDD=10/47, VSS=11/48, VDDX=31/78, VSSX=30/77, VFP=69 etc.

### Programadores
- CarProg A10 recebeu o mapeamento documental do cabo A10:
  - BLUE = RESET
  - BROWN = GND
  - GREY = BKGD
  - RED = +5V
  - VIOLET = +12V
- Essas cores pertencem ao **cabo do programador**. Elas nunca são usadas para inferir a cor de um fio do veículo.
- UPA/ST10/EEPROM permanecem na base como ferramentas cadastradas; compatibilidade específica continua marcada como não confirmada até haver documentação correspondente.

## Fontes usadas na validação
- Motorola MC68HC912B32TS/D datasheet.
- CarProg Motorola HC912/9S12 Programmer Manual.
- ST M95160 datasheet.
- Diagrama de ECU Delphi MT20U usado como imagem de estresse.

## Limitações conhecidas
1. OCR continua sendo a principal limitação em fotografias/diagramas rasterizados.
2. Reconhecimento de ponte gráfica precisa de uma etapa dedicada de visão computacional.
3. Identificação automática do `pin 1` ainda exige evidência visual explícita; quando não existe, o sistema não inventa orientação.
4. M6 ainda precisa de uma reconstrução específica para tabelas de datasheet difíceis; a V3 não mascara esse problema.
