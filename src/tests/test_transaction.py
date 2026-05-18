import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import declarative_base

from ioc import ApplicationContext, Component
from ioc.ext.data import DatabaseFactory, get_current_session, transactional

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)


@pytest.mark.asyncio
async def test_transaction_commit(config_file):
    ApplicationContext.initialize(config_file)

    @Component
    class UserDao:
        @transactional
        async def create_user(self, name: str) -> int:
            session = get_current_session()
            user = User(name=name)
            session.add(user)
            await session.flush()
            return user.id

        @transactional
        async def get_user(self, user_id: int):
            session = get_current_session()
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    await ApplicationContext.refresh()

    factory = ApplicationContext.get_bean(DatabaseFactory)
    async with factory.get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dao = ApplicationContext.get_bean(UserDao)
    uid = await dao.create_user("Alice")
    user = await dao.get_user(uid)
    assert user.name == "Alice"

    await ApplicationContext.close()


@pytest.mark.asyncio
async def test_transaction_rollback(config_file):
    ApplicationContext.initialize(config_file)

    @Component
    class RollbackDao:
        @transactional
        async def delate_all(self):
            session = get_current_session()
            await session.execute(User.__table__.delete())

        @transactional
        async def create_and_fail(self, name: str):
            session = get_current_session()
            user = User(name=name)
            session.add(user)
            await session.flush()
            raise ValueError("rollback")

        @transactional
        async def count_users(self) -> int:
            session = get_current_session()
            result = await session.execute(select(User))
            return len(result.scalars().all())

    await ApplicationContext.refresh()

    factory = ApplicationContext.get_bean(DatabaseFactory)
    async with factory.get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    dao = ApplicationContext.get_bean(RollbackDao)
    await dao.delate_all()
    with pytest.raises(ValueError):
        await dao.create_and_fail("Bob")
    count = await dao.count_users()
    assert count == 0

    await ApplicationContext.close()
