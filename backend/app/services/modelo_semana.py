from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tempo import combinar_data_hora_local, garantir_utc
from app.models.bloco import Bloco, PausaPlanejada
from app.models.modelo_semana import ModeloBloco
from app.models.usuario import Usuario
from app.repositories.bloco import BlocoRepository
from app.repositories.modelo_semana import ModeloBlocoRepository
from app.services.lembrete import agendar_lembrete_para_bloco


def dia_semana_convencao_ritmo(dia: date) -> int:
    """Converte `date.weekday()` (0=seg..6=dom) para a convenção Ritmo (`0=domingo .. 6=sábado`)."""
    return (dia.weekday() + 1) % 7


class MaterializadorSemanaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.modelos = ModeloBlocoRepository(session)
        self.blocos = BlocoRepository(session)

    async def aplicar_modelo_na_semana(
        self, usuario: Usuario, data_inicio: date, agora: datetime | None = None
    ) -> list[Bloco]:
        """Materializa de forma idempotente os `ModeloBloco` ativos nos 7 dias da semana.

        Não faz commit: quem chama decide (blocos e lembretes saem na mesma transação).
        Modelos excluídos ou inativos são ignorados. Os lembretes de cada bloco novo ou alterado
        seguem `ModeloBloco.lembretes` (ou o padrão do usuário, se vazio).
        """
        modelos_ativos = await self.modelos.listar_do_usuario(usuario.id, apenas_ativos=True)
        por_dia_semana: dict[int, list[ModeloBloco]] = {}
        for m in modelos_ativos:
            por_dia_semana.setdefault(m.dia_semana, []).append(m)

        data_fim = data_inicio + timedelta(days=6)
        existentes_lista = await self.blocos.listar_vinculados_por_periodo(
            usuario.id, data_inicio, data_fim, incluir_excluidos=True
        )
        mapa_existentes: dict[tuple[UUID, date], Bloco] = {
            (b.modelo_bloco_id, b.data_local): b
            for b in existentes_lista
            if b.modelo_bloco_id is not None
        }

        materializados: list[Bloco] = []
        a_agendar: list[tuple[Bloco, ModeloBloco]] = []
        for offset in range(7):
            dia = data_inicio + timedelta(days=offset)
            ds = dia_semana_convencao_ritmo(dia)
            for modelo in por_dia_semana.get(ds, []):
                existente = mapa_existentes.get((modelo.id, dia))
                bloco, alterado = self._sincronizar_item(usuario, modelo, dia, existente)
                if bloco is None:
                    continue
                materializados.append(bloco)
                if alterado:
                    a_agendar.append((bloco, modelo))

        await self.session.flush()
        for bloco, modelo in a_agendar:
            await agendar_lembrete_para_bloco(
                self.session,
                bloco,
                usuario.antecedencia_padrao_min,
                antecedencias=modelo.lembretes,
                agora=agora,
            )
        return materializados

    def _sincronizar_item(
        self,
        usuario: Usuario,
        modelo: ModeloBloco,
        dia: date,
        existente: Bloco | None,
    ) -> tuple[Bloco | None, bool]:
        """Retorna `(bloco, alterado)`; `bloco` é `None` se o usuário excluiu a instância."""
        inicio_utc, fim_utc = combinar_data_hora_local(
            dia, modelo.hora_inicio, modelo.hora_fim, usuario.fuso
        )
        pausas_tuplas = self._calcular_intervalos_pausas(inicio_utc, fim_utc, modelo.pausas)

        if existente is None:
            novo = Bloco(
                usuario_id=usuario.id,
                categoria_id=modelo.categoria_id,
                modelo_bloco_id=modelo.id,
                tipo="rotina",
                titulo=modelo.titulo,
                data_local=dia,
                inicio=inicio_utc,
                fim=fim_utc,
                desvinculado=False,
                pausas_planejadas=[
                    PausaPlanejada(inicio=p_ini, fim=p_fim) for p_ini, p_fim in pausas_tuplas
                ],
            )
            self.session.add(novo)
            return novo, True

        if existente.excluido_em is not None:
            return None, False
        if existente.desvinculado:
            return existente, False

        pausas_atuais = [
            (garantir_utc(p.inicio), garantir_utc(p.fim)) for p in existente.pausas_planejadas
        ]
        campos_iguais = (
            existente.categoria_id == modelo.categoria_id
            and existente.titulo == modelo.titulo
            and garantir_utc(existente.inicio) == inicio_utc
            and garantir_utc(existente.fim) == fim_utc
            and pausas_atuais == pausas_tuplas
        )
        if campos_iguais:
            return existente, False

        existente.categoria_id = modelo.categoria_id
        existente.titulo = modelo.titulo
        existente.inicio = inicio_utc
        existente.fim = fim_utc
        if pausas_atuais != pausas_tuplas:
            existente.pausas_planejadas.clear()
            for p_ini, p_fim in pausas_tuplas:
                existente.pausas_planejadas.append(PausaPlanejada(inicio=p_ini, fim=p_fim))
        existente.versao += 1
        return existente, True

    @staticmethod
    def _calcular_intervalos_pausas(
        inicio_utc: datetime, fim_utc: datetime, definicoes: list[dict[str, int]]
    ) -> list[tuple[datetime, datetime]]:
        resultado: list[tuple[datetime, datetime]] = []
        for item in definicoes:
            offset_min = int(item["offset_min"])
            duracao_min = int(item["duracao_min"])
            p_ini = inicio_utc + timedelta(minutes=offset_min)
            p_fim = p_ini + timedelta(minutes=duracao_min)
            if p_ini >= inicio_utc and p_fim <= fim_utc and p_fim > p_ini:
                resultado.append((p_ini, p_fim))
        return resultado
