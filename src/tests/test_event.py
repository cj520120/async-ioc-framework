import pytest
import logging
from ioc import ApplicationContext, Component, Event, EventListener, EventPublisher

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class UserCreated(Event):
    def __init__(self, user_id):
        self.user_id = user_id


@pytest.mark.asyncio
async def test_event_listener(config_file):
    @Component
    class PublisherService:
        def __init__(self, publisher: EventPublisher):
            self.publisher = publisher

        async def emit(self, user_id):
            logger.info("Publishing UserCreated(%s)", user_id)
            await self.publisher.publish(UserCreated(user_id))

    @Component
    class Listener:
        def __init__(self):
            self.received = None

        @EventListener(UserCreated)
        async def handle(self, event):
            logger.info("Listener.handle called with %s", event.user_id)
            self.received = event.user_id

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()

    # 检查 EventPublisher 内部状态
    pub_bean = ApplicationContext.get_bean(EventPublisher)
    logger.info("EventPublisher listeners: %s", getattr(pub_bean, '_listeners', 'N/A'))

    pub = ApplicationContext.get_bean(PublisherService)
    listener = ApplicationContext.get_bean(Listener)
    await pub.emit(42)
    assert listener.received == 42
    await ApplicationContext.close()


@pytest.mark.asyncio
async def test_multiple_listeners(config_file):
    results = []

    @Component
    class MultiPublisher:
        def __init__(self, publisher: EventPublisher):
            self.publisher = publisher

        async def fire(self):
            logger.info("Publishing UserCreated(1)")
            await self.publisher.publish(UserCreated(1))

    @Component
    class ListenerA:
        @EventListener(UserCreated)
        async def handle(self, event):
            logger.info("ListenerA.handle called")
            results.append("A")

    @Component
    class ListenerB:
        @EventListener(UserCreated)
        async def handle(self, event):
            logger.info("ListenerB.handle called")
            results.append("B")

    ApplicationContext.initialize(config_file)
    await ApplicationContext.refresh()

    pub_bean = ApplicationContext.get_bean(EventPublisher)
    logger.info("EventPublisher listeners: %s", getattr(pub_bean, '_listeners', 'N/A'))

    pub = ApplicationContext.get_bean(MultiPublisher)
    await pub.fire()
    logger.info("Results: %s", results)
    assert results == ["A", "B"]
    await ApplicationContext.close()
