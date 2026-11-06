from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflitoError
from app.core.tempo import garantir_utc
from app.models.bloco import Bloco
from app.models.execucao import Execucao, PausaExecucao
from app.repositories.execucao import ExecucaoRepository
from app.services.horas_liquidas import Intervalo, segundos_liquidos

STATUS_CONCLUIDOS = ("concluida", "parcial")


class _PausaLike(Protocol):
    @property
    def inicio(self) -> datetime: ...

    @property
    def fim(self) -> datetime | None: ...


@asynccontextmanager
async def conflito_se_integridade(session: AsyncSession, mensagem: str) -> AsyncIterator[None]:
    """Converte `IntegrityError` (id duplicado, cronômetro duplicado) em 409."""
    try:
        yield
    except IntegrityError as exc:
        await session.rollback()
        raise ConflitoError(mensagem) from exc


def recalcular_liquido(
    inicio: datetime,
    fim: datetime | None,
    pausas: Sequence[_PausaLike],
) -> int:
    if fim is None:
        return 0
    ini_utc = garantir_utc(inicio)
    fim_utc = garantir_utc(fim)
    if fim_utc <= ini_utc:
        return 0
    intervalos_pausa = [
        Intervalo(p.inicio, p.fim)
        for p in pausas
        if p.fim is not None and garantir_utc(p.fim) > garantir_utc(p.inicio)
    ]
    return segundos_liquidos(Intervalo(ini_utc, fim_utc), intervalos_pausa)


def encerrar_execucao_aberta(
    execucao: Execucao,
    instante: datetime,
    status_final: str = "concluida",
) -> None:
    """Fecha uma execução em andamento (e a pausa aberta, se houver) em `instante`."""
    ini_utc = garantir_utc(execucao.inicio)
    fim_efetivo = max(garantir_utc(instante), ini_utc + timedelta(seconds=1))
    for p in execucao.pausas:
        if p.fim is None:
            p_ini = garantir_utc(p.inicio)
            p.fim = max(fim_efetivo, p_ini + timedelta(seconds=1))
            fim_efetivo = max(fim_efetivo, garantir_utc(p.fim))
    execucao.fim = fim_efetivo
    execucao.status = status_final
    execucao.segundos_liquidos = (
        0
        if status_final == "pulada"
        else recalcular_liquido(execucao.inicio, execucao.fim, list(execucao.pausas))
    )
    execucao.versao += 1


def validar_coerencia(
    status: str,
    inicio: datetime,
    fim: datetime | None,
    pausas: Sequence[_PausaLike],
) -> None:
    """Valida o estado final de uma execução; levanta 422 se incoerente.

    - `em_andamento` exige `fim` nulo; qualquer outro status exige `fim > inicio`.
    - Pausas dentro do intervalo, sem sobreposição; pausa aberta só em andamento (e só uma).
    """
    ini = garantir_utc(inicio)
    fim_utc = garantir_utc(fim) if fim is not None else None
    em_andamento = status == "em_andamento"

    if em_andamento and fim_utc is not None:
        raise AppError(422, "Execução em andamento não pode ter fim", "validacao")
    if not em_andamento and fim_utc is None:
        raise AppError(422, f"Execução '{status}' exige o fim informado", "validacao")
    if fim_utc is not None and fim_utc <= ini:
        raise AppError(422, "O fim da execução deve ser posterior ao início", "validacao")

    ordenadas = sorted(pausas, key=lambda p: garantir_utc(p.inicio))
    fim_anterior: datetime | None = None
    for indice, p in enumerate(ordenadas):
        p_ini = garantir_utc(p.inicio)
        p_fim = garantir_utc(p.fim) if p.fim is not None else None
        if p_ini < ini or (fim_utc is not None and (p_fim is None or p_fim > fim_utc)):
            raise AppError(
                422, "As pausas devem ficar dentro do intervalo da execução", "validacao"
            )
        if p_fim is None:
            if not em_andamento:
                raise AppError(
                    422, "Pausa em aberto só é válida em execução em andamento", "validacao"
                )
            if indice != len(ordenadas) - 1:
                raise AppError(422, "Apenas a última pausa pode estar em aberto", "validacao")
        elif p_fim <= p_ini:
            raise AppError(422, "O fim da pausa deve ser posterior ao início", "validacao")
        if fim_anterior is not None and p_ini < fim_anterior:
            raise AppError(422, "As pausas da execução não podem se sobrepor", "validacao")
        fim_anterior = p_fim


@dataclass(frozen=True, slots=True)
class ResultadoConfirmacao:
    execucao: Execucao
    criada: bool


def confirmar_bloco(
    bloco: Bloco,
    existentes: Sequence[Execucao],
    agora: datetime,
    status: str = "concluida",
) -> ResultadoConfirmacao:
    """Regra única de "Fiz como planejado" (não destrutiva, idempotente).

    1. Já existe execução concluída/parcial no bloco: devolve-a (para `pulada`, qualquer
       execução já encerrada serve). Se ela veio de uma confirmação anterior (sem tempo
       medido), apenas o status é atualizado.
    2. Existe uma em andamento: encerra-a em `agora` (preserva o tempo medido).
    3. Nenhuma: cria a execução com o intervalo e as pausas planejados.
    Nunca altera o intervalo de execuções existentes nem as exclui.
    """
    encerradas = [e for e in existentes if e.fim is not None and e.status != "em_andamento"]
    # Confirmações anteriores não têm tempo medido: trocar o status delas não perde nada.
    confirmadas = [e for e in encerradas if e.origem == "confirmacao"]
    if confirmadas:
        alvo = confirmadas[-1]
        if alvo.status != status:
            alvo.status = status
            pausas_alvo = list(alvo.pausas)
            alvo.segundos_liquidos = (
                0 if status == "pulada" else recalcular_liquido(alvo.inicio, alvo.fim, pausas_alvo)
            )
            alvo.versao += 1
        return ResultadoConfirmacao(alvo, criada=False)

    aceitas = (
        encerradas
        if status == "pulada"
        else [e for e in encerradas if e.status in STATUS_CONCLUIDOS]
    )
    if aceitas:
        return ResultadoConfirmacao(aceitas[-1], criada=False)

    abertas = [e for e in existentes if e.status == "em_andamento" and e.fim is None]
    if abertas:
        for aberta in abertas:
            encerrar_execucao_aberta(aberta, agora, status_final=status)
        return ResultadoConfirmacao(abertas[-1], criada=False)

    pausas = [PausaExecucao(inicio=p.inicio, fim=p.fim) for p in bloco.pausas_planejadas]
    liquido = 0 if status == "pulada" else recalcular_liquido(bloco.inicio, bloco.fim, pausas)
    nova = Execucao(
        usuario_id=bloco.usuario_id,
        categoria_id=bloco.categoria_id,
        bloco_id=bloco.id,
        inicio=bloco.inicio,
        fim=bloco.fim,
        status=status,
        origem="confirmacao",
        segundos_liquidos=liquido,
        pausas=pausas,
    )
    return ResultadoConfirmacao(nova, criada=True)


async def registrar_confirmacao_bloco(
    session: AsyncSession,
    bloco: Bloco,
    agora: datetime,
    status: str = "concluida",
) -> Execucao:
    """Aplica `confirmar_bloco` e persiste (commit). Usada por `/blocos/{id}/confirmar` e
    `/execucoes/confirmar-bloco`, que compartilham a mesma regra."""
    repo = ExecucaoRepository(session)
    existentes = await repo.listar_por_bloco(bloco.usuario_id, bloco.id)
    resultado = confirmar_bloco(bloco, existentes, agora, status)
    async with conflito_se_integridade(session, "Conflito ao confirmar o bloco"):
        if resultado.criada:
            await repo.criar(resultado.execucao)
        await session.commit()
    recarregada = await repo.obter_do_usuario(bloco.usuario_id, resultado.execucao.id)
    assert recarregada is not None
    return recarregada
