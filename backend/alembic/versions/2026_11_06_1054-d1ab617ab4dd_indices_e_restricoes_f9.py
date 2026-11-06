"""indices e restricoes f9

Revision ID: d1ab617ab4dd
Revises: 7fe645757403
Create Date: 2026-11-06 10:54:11.048430

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1ab617ab4dd"
down_revision: str | Sequence[str] | None = "7fe645757403"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EM_ANDAMENTO = sa.text("status = 'em_andamento' AND excluido_em IS NULL")
PENDENTE = sa.text("status = 'pendente'")

# Índices simples em `usuario_id` cobertos como prefixo por compostos (usuario_id, ...).
REDUNDANTES = (
    ("ix_execucao_usuario_id", "execucao"),
    ("ix_bloco_usuario_id", "bloco"),
    ("ix_categoria_usuario_id", "categoria"),
    ("ix_modelo_bloco_usuario_id", "modelo_bloco"),
)


def upgrade() -> None:
    # Antes do índice único: mantém só o cronômetro mais recente de cada usuário.
    op.execute(
        """
        UPDATE execucao SET status = 'parcial', fim = inicio + interval '1 second'
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY usuario_id ORDER BY inicio DESC, id DESC
                ) AS posicao
                FROM execucao
                WHERE status = 'em_andamento' AND excluido_em IS NULL
            ) abertas
            WHERE posicao > 1
        )
        """
    )

    op.add_column("lembrete", sa.Column("tentativa_em", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "uq_execucao_usuario_em_andamento",
        "execucao",
        ["usuario_id"],
        unique=True,
        postgresql_where=EM_ANDAMENTO,
    )
    op.create_index("ix_execucao_usuario_inicio", "execucao", ["usuario_id", "inicio"])
    op.create_index(
        "ix_lembrete_disparar_em_pendente",
        "lembrete",
        ["disparar_em"],
        postgresql_where=PENDENTE,
    )
    for tabela in ("bloco", "execucao", "categoria", "modelo_bloco"):
        op.create_index(
            f"ix_{tabela}_usuario_atualizado_em", tabela, ["usuario_id", "atualizado_em"]
        )

    for nome, tabela in REDUNDANTES:
        op.drop_index(nome, table_name=tabela)


def downgrade() -> None:
    for nome, tabela in REDUNDANTES:
        op.create_index(nome, tabela, ["usuario_id"])

    for tabela in ("modelo_bloco", "categoria", "execucao", "bloco"):
        op.drop_index(f"ix_{tabela}_usuario_atualizado_em", table_name=tabela)
    op.drop_index(
        "ix_lembrete_disparar_em_pendente", table_name="lembrete", postgresql_where=PENDENTE
    )
    op.drop_index("ix_execucao_usuario_inicio", table_name="execucao")
    op.drop_index(
        "uq_execucao_usuario_em_andamento", table_name="execucao", postgresql_where=EM_ANDAMENTO
    )
    op.drop_column("lembrete", "tentativa_em")
