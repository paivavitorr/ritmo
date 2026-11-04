"""cria usuario e sessao_refresh

Revision ID: 20261104_0001
Revises:
Create Date: 2026-11-04 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261104_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("senha_hash", sa.Text(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("fuso", sa.String(length=64), nullable=False),
        sa.Column("inicio_semana", sa.SmallInteger(), nullable=False),
        sa.Column("antecedencia_padrao_min", sa.SmallInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default="1", nullable=False),
        sa.Column("excluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
    )
    op.create_index(op.f("ix_usuario_email"), "usuario", ["email"], unique=True)

    op.create_table(
        "sessao_refresh",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("familia_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("substituido_por_id", sa.Uuid(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_sessao_refresh_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessao_refresh")),
    )
    op.create_index(
        op.f("ix_sessao_refresh_familia_id"),
        "sessao_refresh",
        ["familia_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sessao_refresh_token_hash"),
        "sessao_refresh",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_sessao_refresh_usuario_id"),
        "sessao_refresh",
        ["usuario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sessao_refresh_usuario_id"), table_name="sessao_refresh")
    op.drop_index(op.f("ix_sessao_refresh_token_hash"), table_name="sessao_refresh")
    op.drop_index(op.f("ix_sessao_refresh_familia_id"), table_name="sessao_refresh")
    op.drop_table("sessao_refresh")
    op.drop_index(op.f("ix_usuario_email"), table_name="usuario")
    op.drop_table("usuario")
