from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.container_adoption import StreamingContainerAdoption

from .base_handler import DBBaseHandler


class DBContainerAdoptionsHandler(DBBaseHandler):
    @begin_session
    def get_adoption(
        self,
        container_key: str,
        session: Session = None,  # type: ignore
    ) -> StreamingContainerAdoption | None:
        return session.scalar(
            select(StreamingContainerAdoption)
            .filter_by(container_key=container_key)
            .limit(1)
        )

    @begin_session
    def add_adoption(
        self,
        container_key: str,
        outcome: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> StreamingContainerAdoption | None:
        """Returns None when another claim recorded the decision first. The
        unique constraint is the arbiter, not the earlier read."""
        adoption = StreamingContainerAdoption(
            container_key=container_key,
            outcome=outcome,
            decided_by_user_id=user_id,
        )
        try:
            session.add(adoption)
            session.flush()
        except IntegrityError:
            session.rollback()
            return None
        return adoption
