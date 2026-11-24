"""initial schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

J = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("gutenberg_id", sa.Integer, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.Text),
        sa.Column("year", sa.Integer),
        sa.Column("subjects", J, nullable=False),
        sa.Column("n_tokens", sa.Integer, nullable=False),
        sa.Column("n_chunks", sa.Integer, nullable=False),
        sa.Column("ingest_status", sa.String(16), nullable=False),
        sa.Column("sha256", sa.String(64)),
    )
    op.create_table(
        "chapters",
        sa.Column("book_id", sa.Integer, sa.ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idx", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
    )
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("n_requested", sa.Integer, nullable=False),
        sa.Column("n_done", sa.Integer, nullable=False),
        sa.Column("params", J, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("finished_at", TS),
    )
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("method_config", J, nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("n_questions", sa.Integer, nullable=False),
        sa.Column("metrics", J, nullable=False),
        sa.Column("git_sha", sa.String(40)),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "eval_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(128), nullable=False),
        sa.Column("gold", J, nullable=False),
        sa.Column("prediction", J),
        sa.Column("metrics", J, nullable=False),
        sa.Column("routed_book_ids", J, nullable=False),
        sa.Column("evidence_ids", J, nullable=False),
        sa.Column("latency_ms", sa.Float),
        sa.Column("tokens_in", sa.Integer, nullable=False),
        sa.Column("tokens_out", sa.Integer, nullable=False),
        sa.Column("failure_label", sa.String(32)),
    )
    op.create_index("ix_eval_results_run_question", "eval_results", ["run_id", "question_id"])


def downgrade() -> None:
    for t in ("eval_results", "eval_runs", "ingest_jobs", "chapters", "books"):
        op.drop_table(t)
