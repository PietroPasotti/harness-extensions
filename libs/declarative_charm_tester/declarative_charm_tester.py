import typing
from abc import ABC

from ops.charm import CharmBase
from ops.framework import BoundEvent, EventBase
from ops.testing import Harness

OptionalYAML = typing.Optional[typing.Union[str, typing.TextIO]]


class _TestCharmABC(ABC, CharmBase):
    def get_calls(self, clear: bool = False) -> typing.List[typing.Any]: ...

    def run(self, fn: typing.Callable[[CharmBase], ...]) -> None: ...

    def listener(self, event: str) -> None: ...

    def register_listener(self, event: BoundEvent,
                          callback: typing.Callable[[CharmBase, BoundEvent], None]): ...


def charm_type_factory() -> typing.Type[CharmBase]:
    class InvokeEvent(EventBase):
        pass

    class TestCharm(CharmBase):
        def __init__(self, framework, key=None):
            super().__init__(framework, key)
            self._callback = None
            self.on.define_event('invoke', InvokeEvent)
            self.framework.observe(self.on.invoke, self._on_invoke)

            self._listeners = {}
            self._listener_calls = []

        def get_calls(self, clear=False):
            calls = self._listener_calls
            if clear:
                self._listener_calls = []
            return calls

        def run(self, fn: typing.Callable[[typing.Self], ...]):
            if self._callback:
                raise RuntimeError('already in a run scope')

            self._callback = fn
            self._invoke(self)
            self._callback = None

        def _invoke(self, *args):
            self.on.invoke.emit(*args)

        def _on_invoke(self, event):
            self._callback()

        def listener(self, event: str):
            def wrapper(callback):
                self.register_listener(event, callback)
                callback.called = False
                return callback

            return wrapper

        def register_listener(self, event: BoundEvent, callback):
            self._listeners[event.event_kind] = callback
            self.framework.observe(event, self._call_listener)

        def _call_listener(self, evt: EventBase):
            listener = self._listeners[evt.handle.kind]
            self._listener_calls.append(listener)
            listener.called = evt
            listener(evt)

    return TestCharm


def harness_factory(meta: OptionalYAML = None,
                    actions: OptionalYAML = None,
                    config: OptionalYAML = None) -> Harness[_TestCharmABC]:
    return Harness(charm_type_factory(), meta=meta, actions=actions, config=config)
