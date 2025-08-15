import psycopg2
from psycopg2 import sql
from contextlib import contextmanager
from supabase import SessionLocal
from sqlalchemy import text

class MemoryManager:
    def __init__(self, db_session_factory):
        """
        db_session_factory: a callable like SessionLocal that returns a SQLAlchemy session
        """
        self.db_session_factory = db_session_factory
    
    @classmethod
    def from_supabase(cls):
        # This way you can just call MemoryManager.from_supabase()
        return cls(SessionLocal)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.db_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # @contextmanager
    # def cursor(self):
    #     """Provide a cursor for database operations."""
    #     with self.connection() as conn:
    #         cursor = conn.cursor()
    #         try:
    #             yield cursor
    #         finally:
    #             cursor.close()
    
    def delete_by_thread_id(self, thread_id: str) -> None:
        """Delete all checkpoints for a given thread_id."""
        with self.session_scope() as session:
            session.execute(
                text("DELETE FROM checkpoints WHERE thread_id = :tid"),
                {"tid": thread_id}
            )
    
    def count_checkpoints_by_thread_id(self) -> None:
        """Count the number of checkpoints for each thread_id."""
        with self.session_scope() as session:
            results = session.execute(
                text("SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id ORDER BY thread_id;")
            ).fetchall()

            print("Checkpoint counts by thread_id:")
            for row in results:
                print(f"Thread ID: {row[0]}, Count: {row[1]}")
    
    def delete_all(self) -> None:
        """Delete all checkpoints."""
        with self.session_scope() as session:
            session.execute(text("DELETE FROM checkpoints;"))