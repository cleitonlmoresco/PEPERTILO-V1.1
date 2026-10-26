# Análise do banco interno — `res\data\SystemData.s3d`

## Resultado

- Arquivo **SQLite 3 válido**, 5.120 bytes, **sem criptografia**.
- 3 tabelas.

### `SELECTION` (6 linhas) — último veículo usado por dispositivo

| DEVICE | TIPO | MARCA | MODELO | VERSÃO | TIPO ECU | MODO |
|---|---|---|---|---|---|---|
| 2 | CAR | MITSUBISHI | LANCER EVO VI | 2000 4L TURBO | 4G63T | BOOT MIT |
| 1 | CAR | FORD | RANGER | 2.3 | — | OBDII |
| 1 | TRUCK | MERCEDES TRUCK | ACTROS (MP1) | 4141 11.95L V6 | OM501LA | BOOT |
| 1 | BIKE | HARLEY DAVIDSON | CVO (FLTR) | Road Glide | — | OBDII |
| 1 | TRACTOR | AGCO | DT-B SERIES | DT225B 8.4L I6 | 84CTA | OBDII |
| 1 | BOAT | HYUNDAI SEASALL | S-SERIES | S270S 3.0 V6 CRDi | — | OBDII |

> DEVICE 1 = KESS v2, DEVICE 2 = K-TAG.

### `SETTINGS` (1 linha)

```
LANGUAGE = 2 (inglês)   RESOLUTION = 1024x768
```

### `SQLITEADMIN_QUERIES` — vazia (ferramenta usada para criar).

## Conclusão

O banco guarda **apenas estado da UI** (último veículo, idioma, resolução).
**Não contém senhas, chaves ou licenças.**
