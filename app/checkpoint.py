import psycopg2
from psycopg2 import sql
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from typing import Any, Optional, Iterator, AsyncIterator, Sequence
from datetime import datetime, timezone
from contextlib import contextmanager
from sqlalchemy import text
from .supabase import SessionLocal


class SupabaseCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory

    @classmethod
    def from_conn_string(cls, conn_string: str):
        return cls(SessionLocal)

    @contextmanager
    def session_scope(self):
        session = self.db_session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def setup(self) -> None:
        with self.session_scope() as session:
            # Consolidated checkpoints — one row per completed super-step
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    thread_ts TEXT NOT NULL,
                    parent_ts TEXT,
                    checkpoint BYTEA,
                    metadata BYTEA,
                    PRIMARY KEY (thread_id, thread_ts)
                );
            """))
            # Pending channel writes — one row per (task, channel) BEFORE
            # they're folded into a checkpoint. This is what put_writes()
            # should be writing to, never the checkpoints table.
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS checkpoint_writes (
                    thread_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_path TEXT,
                    idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    value BYTEA,
                    PRIMARY KEY (thread_id, task_id, idx)
                );
            """))

    def get_latest_timestamp(self, thread_id: str) -> str:
        with self.session_scope() as session:
            result = session.execute(
                text("SELECT thread_ts FROM checkpoints WHERE thread_id = :tid ORDER BY thread_ts DESC LIMIT 1"),
                {"tid": thread_id}
            ).fetchone()
            return result[0] if result else None

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get(
            "thread_ts", self.get_latest_timestamp(thread_id)
        )

        with self.session_scope() as session:
            result = session.execute(
                text("SELECT checkpoint, metadata, parent_ts FROM checkpoints WHERE thread_id = :tid AND thread_ts = :tts"),
                {"tid": thread_id, "tts": thread_ts}
            ).fetchone()
            if result:
                checkpoint, metadata, parent_ts = result
                return CheckpointTuple(
                    config,
                    self.serde.loads(bytes(checkpoint)),
                    self.serde.loads(bytes(metadata)) if metadata else {},
                    (
                        {"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}}
                        if parent_ts else None
                    ),
                )
        return None

    def list(self, config: RunnableConfig, *, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        query = "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata FROM checkpoints WHERE thread_id = :tid"
        params = {"tid": thread_id}
        if before:
            query += " AND thread_ts < :bts"
            params["bts"] = before["configurable"]["thread_ts"]
        query += " ORDER BY thread_ts DESC"
        if limit:
            query += " LIMIT :lim"
            params["lim"] = limit

        with self.session_scope() as session:
            results = session.execute(text(query), params).fetchall()
            for tid, tts, parent_ts, checkpoint, metadata in results:
                yield CheckpointTuple(
                    {"configurable": {"thread_id": tid, "thread_ts": tts}},
                    self.serde.loads(bytes(checkpoint)),
                    self.serde.loads(bytes(metadata)) if metadata else {},
                    {"configurable": {"thread_id": tid, "thread_ts": parent_ts}} if parent_ts else None
                )

    def put(self, config: RunnableConfig, checkpoint: dict, metadata: dict, new_versions: dict) -> RunnableConfig:
        """
        Signature must match BaseCheckpointSaver.put exactly:
        (self, config, checkpoint, metadata, new_versions) -> RunnableConfig
        No config_modifier — that was never part of the real interface.
        """
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["id"]  # use LangGraph's own checkpoint id, not a fresh timestamp
        parent_ts = config["configurable"].get("thread_ts")

        with self.session_scope() as session:
            session.execute(text("""
                INSERT INTO checkpoints (thread_id, thread_ts, parent_ts, checkpoint, metadata)
                VALUES (:tid, :tts, :pts, :cp, :md)
                ON CONFLICT (thread_id, thread_ts) DO UPDATE
                SET parent_ts = EXCLUDED.parent_ts,
                    checkpoint = EXCLUDED.checkpoint,
                    metadata = EXCLUDED.metadata
            """), {
                "tid": thread_id,
                "tts": thread_ts,
                "pts": parent_ts,
                "cp": self.serde.dumps(checkpoint),
                "md": self.serde.dumps(metadata),
            })

        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": thread_ts,
            }
        }

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        """
        `writes` is a sequence of (channel, value) pairs — pending updates to
        individual state channels for this task, NOT (checkpoint, metadata)
        pairs. These get folded into a real checkpoint later by put().
        This must NOT write into the `checkpoints` table.
        Also: per the base class, put_writes returns None, not a config.
        """
        thread_id = config["configurable"]["thread_id"]

        with self.session_scope() as session:
            for idx, (channel, value) in enumerate(writes):
                session.execute(text("""
                    INSERT INTO checkpoint_writes (thread_id, task_id, task_path, idx, channel, value)
                    VALUES (:tid, :task_id, :task_path, :idx, :channel, :value)
                    ON CONFLICT (thread_id, task_id, idx) DO UPDATE
                    SET channel = EXCLUDED.channel,
                        value = EXCLUDED.value
                """), {
                    "tid": thread_id,
                    "task_id": task_id,
                    "task_path": task_path,
                    "idx": idx,
                    "channel": channel,
                    "value": self.serde.dumps(value),
                })

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    async def alist(self, config: RunnableConfig, *, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        for checkpoint_tuple in self.list(config, before=before, limit=limit):
            yield checkpoint_tuple

    async def aput(self, config: RunnableConfig, checkpoint: dict, metadata: dict, new_versions: dict) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        return self.put_writes(config, writes, task_id, task_path)

    def close(self):
        # No persistent connection is held open by this class — sessions
        # are opened/closed per-call in session_scope(). Nothing to close.
        pass

    def delete_by_thread_id(self, thread_id: str) -> None:
        with self.session_scope() as session:
            session.execute(text("DELETE FROM checkpoints WHERE thread_id = :tid"), {"tid": thread_id})
            session.execute(text("DELETE FROM checkpoint_writes WHERE thread_id = :tid"), {"tid": thread_id})

    def count_checkpoints_by_thread_id(self) -> None:
        with self.session_scope() as session:
            results = session.execute(
                text("SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id ORDER BY thread_id;")
            ).fetchall()
            print("Checkpoint counts by thread_id:")
            for row in results:
                print(f"Thread ID: {row[0]}, Count: {row[1]}")

    def delete_all(self) -> None:
        with self.session_scope() as session:
            session.execute(text("DELETE FROM checkpoints;"))
            session.execute(text("DELETE FROM checkpoint_writes;"))