from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def garantir_utc(dt: datetime) -> datetime:
    """Normaliza qualquer `datetime` para UTC aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def data_local_no_fuso(instante: datetime, fuso_iana: str) -> date:
    """Retorna a `date` local correspondente ao instante no fuso IANA do usuário."""
    tz = ZoneInfo(fuso_iana)
    return garantir_utc(instante).astimezone(tz).date()


def limites_utc_do_dia(dia: date, fuso_iana: str) -> tuple[datetime, datetime]:
    """Retorna `(inicio_utc, fim_utc)` da meia-noite local até a próxima meia-noite local."""
    tz = ZoneInfo(fuso_iana)
    inicio_local = datetime.combine(dia, time.min, tzinfo=tz)
    fim_local = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=tz)
    return inicio_local.astimezone(UTC), fim_local.astimezone(UTC)


def combinar_data_hora_local(
    dia: date,
    hora_inicio: time,
    hora_fim: time,
    fuso_iana: str,
) -> tuple[datetime, datetime]:
    """Converte `(dia, hora_inicio, hora_fim)` locais em `(inicio_utc, fim_utc)`.

    Se `hora_fim <= hora_inicio`, considera que o bloco cruza a meia-noite
    e termina no dia seguinte.
    """
    tz = ZoneInfo(fuso_iana)
    inicio_local = datetime.combine(dia, hora_inicio, tzinfo=tz)
    dia_fim = dia if hora_fim > hora_inicio else dia + timedelta(days=1)
    fim_local = datetime.combine(dia_fim, hora_fim, tzinfo=tz)
    return inicio_local.astimezone(UTC), fim_local.astimezone(UTC)
