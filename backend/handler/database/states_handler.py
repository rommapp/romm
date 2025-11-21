from collections.abc import Sequence

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.assets import State
from models.rom import Rom

from .base_handler import DBBaseHandler


class DBStatesHandler(DBBaseHandler):
    @begin_session
    def add_state(self, state: State, session: Session = None) -> State:
        return session.merge(state)

    @begin_session
    def get_state(self, user_id: int, id: int, session: Session = None) -> State | None:
        return session.scalar(select(State).filter_by(user_id=user_id, id=id).limit(1))

    @begin_session
    def get_state_by_filename(
        self, user_id: int, rom_id: int, file_name: str, session: Session = None
    ) -> State | None:
        return session.scalar(
            select(State)
            .filter_by(rom_id=rom_id, user_id=user_id, file_name=file_name)
            .limit(1)
        )

    @begin_session
    def get_states(
        self,
        user_id: int,
        rom_id: int | None = None,
        platform_id: int | None = None,
        session: Session = None,
    ) -> Sequence[State]:
        query = select(State).filter_by(user_id=user_id)

        if rom_id:
            query = query.filter_by(rom_id=rom_id)

        if platform_id:
            query = query.join(Rom, State.rom_id == Rom.id).filter(
                Rom.platform_id == platform_id
            )

        return session.scalars(query).all()

    @begin_session
    def update_state(self, id: int, data: dict, session: Session = None) -> State:
        session.execute(
            update(State)
            .where(State.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(State).filter_by(id=id).one()

    @begin_session
    def delete_state(self, id: int, session: Session = None) -> None:
        session.execute(
            delete(State)
            .where(State.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def mark_missing_states(
        self,
        rom_id: int,
        user_id: int,
        states_to_keep: list[str],
        session: Session = None,
    ) -> Sequence[State]:
        missing_states = session.scalars(
            select(State).filter(
                and_(
                    State.rom_id == rom_id,
                    State.user_id == user_id,
                    State.file_name.not_in(states_to_keep),
                )
            )
        ).all()

        session.execute(
            update(State)
            .where(
                and_(
                    State.rom_id == rom_id,
                    State.user_id == user_id,
                    State.file_name.not_in(states_to_keep),
                )
            )
            .values(**{"missing_from_fs": True})
            .execution_options(synchronize_session="evaluate")
        )

        return missing_states
