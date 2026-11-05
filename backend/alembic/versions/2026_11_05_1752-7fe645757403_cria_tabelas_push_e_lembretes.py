"""cria_tabelas_push_e_lembretes

Revision ID: 7fe645757403
Revises: 40a38cf0d901
Create Date: 2026-11-05 17:52:23.771616

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7fe645757403"
down_revision: str | None = "40a38cf0d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "push_assinatura",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.String(length=100), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_push_assinatura_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_assinatura")),
    )
    op.create_index(
        op.f("ix_push_assinatura_endpoint"), "push_assinatura", ["endpoint"], unique=True
    )
    op.create_index(
        op.f("ix_push_assinatura_usuario_id"), "push_assinatura", ["usuario_id"], unique=False
    )
    op.create_table(
        "lembrete",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("bloco_id", sa.Uuid(), nullable=False),
        sa.Column("disparar_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("antecedencia_min", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=True),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("versao", sa.Integer(), server_default="1", nullable=False),
        sa.Column("excluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bloco_id"],
            ["bloco.id"],
            name=op.f("fk_lembrete_bloco_id_bloco"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_lembrete_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lembrete")),
    )
    op.create_index(op.f("ix_lembrete_bloco_id"), "lembrete", ["bloco_id"], unique=False)
    op.create_index(op.f("ix_lembrete_disparar_em"), "lembrete", ["disparar_em"], unique=False)
    op.create_index(op.f("ix_lembrete_status"), "lembrete", ["status"], unique=False)
    op.create_index(op.f("ix_lembrete_usuario_id"), "lembrete", ["usuario_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_lembrete_usuario_id"), table_name="lembrete")
    op.drop_index(op.f("ix_lembrete_status"), table_name="lembrete")
    op.drop_index(op.f("ix_lembrete_disparar_em"), table_name="lembrete")
    op.drop_index(op.f("ix_lembrete_bloco_id"), table_name="lembrete")
    op.drop_table("lembrete")
    op.drop_index(op.f("ix_push_assinatura_usuario_id"), table_name="push_assinatura")
    op.drop_index(op.f("ix_push_assinatura_endpoint"), table_name="push_assinatura")
    op.drop_table("push_assinatura")
