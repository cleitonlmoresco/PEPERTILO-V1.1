from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass
class Evidencia:
    id: str
    tipo: str
    valor: Any
    fonte: str
    pagina: Optional[int] = None
    coordenadas: Optional[Dict[str, float]] = None
    confianca: float = 0.0
    contexto: Optional[str] = None
    observacao: Optional[str] = None


@dataclass
class TerminalConector:
    """Representação semântica única do terminal entregue pelo M4 ao M5."""
    conector_id: str
    numero: int | str
    x: float
    y: float
    segmento_fio: Optional[int] = None
    segmentos_candidatos: List[Dict[str, Any]] = field(default_factory=list)
    cor_fio: Optional[str] = None
    bitola: Optional[str] = None
    fonte_cor: Optional[str] = None
    fonte_bitola: Optional[str] = None
    evidencias: List[Dict[str, Any]] = field(default_factory=list)
    score_evidencia: float = 0.0
    status: str = "terminal_sem_fio"


@dataclass
class Conector:
    id: str
    terminais: List[TerminalConector] = field(default_factory=list)
    pagina_origem: Optional[int] = None
    tipo_estrutura: str = "conector"
    evidencias: List[str] = field(default_factory=list)
    status: str = "nao_validado"

@dataclass
class Pino:
    numero: Optional[int | str]
    funcao: Optional[str] = None
    componente_id: Optional[str] = None
    pagina_origem: Optional[int] = None
    evidencias: List[str] = field(default_factory=list)
    status: str = "nao_validado"

@dataclass
class Fio:
    cor: Optional[str]
    funcao: Optional[str] = None
    pagina_origem: Optional[int] = None
    origem_documento: Optional[str] = None
    evidencias: List[str] = field(default_factory=list)

@dataclass
class Conexao:
    pinos: List[int | str] = field(default_factory=list)
    funcao: Optional[str] = None
    cor_fio: Optional[str] = None
    tipo: Optional[str] = None
    pagina_origem: List[int] = field(default_factory=list)
    evidencias: List[str] = field(default_factory=list)
    score_evidencia: float = 0.0
    status: str = "nao_validada"
    observacoes: List[str] = field(default_factory=list)

@dataclass
class Programador:
    id: str
    nome: str
    interfaces: List[str] = field(default_factory=list)
    familias: List[str] = field(default_factory=list)
    status: str = "cadastrado"
    fonte: Optional[str] = None
    observacoes: Optional[str] = None

@dataclass
class Cabo:
    id: str
    programador_id: str
    nome: str
    interface: Optional[str] = None
    adaptador: Optional[str] = None
    evidencias: List[str] = field(default_factory=list)
    status: str = "nao_confirmado"
    observacoes: Optional[str] = None

@dataclass
class Mcu:
    id: str
    fabricante: Optional[str] = None
    familia: Optional[str] = None
    part_number: Optional[str] = None
    encapsulamento: Optional[str] = None
    pinos: Optional[int] = None
    interfaces: List[str] = field(default_factory=list)
    evidencias: List[str] = field(default_factory=list)

@dataclass
class Medicao:
    id: str
    servico_id: str
    ponto: str
    valor: Optional[float] = None
    unidade: Optional[str] = None
    esperado: Optional[str] = None
    instrumento: Optional[str] = None
    status: str = "nao_avaliado"
    observacao: Optional[str] = None
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ServicoBancada:
    id: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    ano: Optional[str] = None
    modulo: Optional[str] = None
    part_number: Optional[str] = None
    hw: Optional[str] = None
    sw: Optional[str] = None
    sintoma: Optional[str] = None
    status: str = "aberto"
    observacoes: Optional[str] = None


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)
