from decorators.database import begin_session
from models.assets import State
from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBStatesHandler(DBBaseHandler):
    @begin_session
    def add_state(self, state: State, session: Session = None) -> State:
        return session.merge(state)

    @begin_session
    def get_state(self, id: int, session: Session = None) -> State:
        return session.get(State, id)

    @begin_session
    def get_state_by_filename(
        self, rom_id: int, user_id: int, file_name: str, session: Session = None
    ) -> State | None:
        return session.scalars(
            select(State)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def update_state(self, id: int, data: dict, session: Session = None) -> State:
        return session.execute(
            update(State)
            .where(State.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_state(self, id: int, session: Session = None) -> None:
        return session.execute(
            delete(State)
            .where(State.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_states(
        self, rom_id: int, user_id: int, states: list[str], session: Session = None
    ) -> None:
        return session.execute(
            delete(State)
            .where(
                and_(
                    State.rom_id == rom_id,
                    State.user_id == user_id,
                    State.file_name.not_in(states),
                )
            )
            .execution_options(synchronize_session="evaluate")
        )
