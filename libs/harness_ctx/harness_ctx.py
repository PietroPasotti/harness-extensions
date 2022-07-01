from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
from typing import Callable, Protocol, Type, Tuple, cast, TypedDict, Dict, \
    Literal, TypeVar, List, Any, Generator, Optional, Union, ContextManager

import yaml
from ops.charm import CharmBase, CharmEvents
from ops.framework import BoundEvent, Handle
from ops.model import Relation
from ops.testing import Harness


class _HasOn(Protocol):
    @property
    def on(self) -> CharmEvents:
        ...


def _DefaultEmitter(charm: CharmBase, harness: Harness):
    return charm


class Emitter:
    """Event emitter."""

    def __init__(self, harness: Harness, emit: Callable[[], BoundEvent]):
        self.harness = harness
        self._emit = emit
        self.event = None
        self._emitted = False

    @property
    def emitted(self):
        """Has the event been emitted already?"""  # noqa
        return self._emitted

    def emit(self):
        """Emit the event.

        Will get called automatically when HarnessCtx exits if you didn't call it already.
        """
        assert not self._emitted, "already emitted; should not emit twice"
        self.event = self._emit()
        self._emitted = True
        return self.event


class HarnessCtx:
    """Harness-based context for emitting a single event.

    Example usage:
    >>> class MyCharm(CharmBase):
    >>>     def __init__(self, framework: Framework, key: typing.Optional = None):
    >>>         super().__init__(framework, key)
    >>>         self.framework.observe(self.on.update_status, self._listen)
    >>>         self.framework.observe(self.framework.on.commit, self._listen)
    >>>
    >>>     def _listen(self, e):
    >>>         self.event = e
    >>>
    >>> with HarnessCtx(MyCharm, "update-status") as h:
    >>>     event = h.emit()
    >>>     assert event.handle.kind == "update_status"
    >>>
    >>> assert h.harness.charm.event.handle.kind == "commit"
    """

    def __init__(
            self,
            charm: Type[CharmBase],
            event_name: str,
            emitter: Callable[[CharmBase, Harness], _HasOn] = _DefaultEmitter,
            *args,
            **kwargs
    ):
        self.charm_cls = charm
        self.emitter = emitter
        self.event_name = event_name.replace("-", "_")
        self.event_args = args
        self.event_kwargs = kwargs

    def __enter__(self):
        self._harness = harness = Harness(self.charm_cls)
        harness.begin()

        emitter = self.emitter(harness.charm, harness)
        events = getattr(emitter, "on")
        event_source: BoundEvent = getattr(events, self.event_name)

        def _emit() -> BoundEvent:
            # we don't call event_source.emit()
            # because we want to grab the event
            framework = event_source.emitter.framework
            key = framework._next_event_key()
            handle = Handle(event_source.emitter, event_source.event_kind, key)
            event = event_source.event_type(
                handle, *self.event_args, **self.event_kwargs
            )
            event.framework = framework
            framework._emit(event)  # type: ignore
            return cast(BoundEvent, event)

        self._emitter = bound_ctx = Emitter(harness, _emit)
        return bound_ctx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._emitter.emitted:
            self._emitter.emit()
        self._harness.framework.on.commit.emit()  # type: ignore


DataBag = Dict[str, str]


class Remote(TypedDict):
    name: str
    units: Dict[int, DataBag]
    app_data: DataBag


_T = TypeVar("_T", bound=Type[CharmBase])


class EndpointCtx:
    def __init__(self,
                 charm_cls: _T,
                 relation_name: str,
                 interface: str,
                 role: Literal['provides', 'requires'] = 'requires',
                 # remotes: Tuple[Remote, ...] = ()
                 ):
        self._role = role
        self._charm_cls = charm_cls
        self._relation_name = relation_name
        self._interface = interface
        self._relation_ctxs: Dict[str, RelationCtx] = {}
        self._begun = False
        self._harness = None
        # self._remotes: List[Remote] = []
        #
        # if remotes:
        #     self.setup()
        #     for remote in remotes:
        #         self.add_remote(remote)

    @property
    def harness(self) -> Harness[_T]:
        if not self._begun:
            raise RuntimeError('enter the context first')
        return self._harness

    def setup(self):
        if self._begun:
            return
        self._begun = True

        meta = {
            self._role: {
                self._relation_name: {
                    'interface': self._interface
                }
            }
        }
        harness = Harness(self._charm_cls,  # type: ignore
                          meta=yaml.safe_dump(meta))
        harness.begin()
        self._harness = harness

    def __enter__(self):
        self.setup()
        # self._exit_stack = exstck = ExitStack()
        # exstck.__enter__()
        return self

    def __exit__(self, *exc):
        self._harness.cleanup()
        # for remote in self._remotes:
        #     self.remove_remote(remote)
        # self._exit_stack.__exit__(*exc)

    # def add_remote(self, remote: Remote):
    #     """Adds all the remotes and populates the databags."""
    #     child_ctx_mgr = next(self.relation(remote))
    #     self._exit_stack.enter_context(child_ctx_mgr)
    #     self._relation_ctxs[remote['name']] = child_ctx_mgr
    #     self._remotes.append(remote)
    #
    # def remove_remote(self, remote: Remote):
    #     """Clear the databags, remove the remote."""
    #     child_ctx = self._relation_ctxs.pop(remote['name'])
    #     child_ctx.__exit__()
    #     self._remotes.remove(remote)

    @contextmanager
    def relation(self, remote: Union[str, Remote]) -> ContextManager[
        'RelationCtx']:
        """remote: a Remote or the name of an existing remote."""
        # if isinstance(remote, str):
        #     try:
        #         remote = next(r for r in self._remotes if r['name'] == remote)
        #     except IndexError:
        #         raise ValueError(f'remote {remote!r} not found')
        #
        # existing_ctx = self._relations.get(remote['name'])
        # if existing_ctx:
        #     yield existing_ctx
        #     return
        #
        # if remote not in self._remotes:
        #     self.add_remote(remote)
        ctx = RelationCtx(self, remote)
        self._relation_ctxs[remote['name']] = ctx
        with ctx:
            yield ctx
        del self._relation_ctxs[remote['name']]
        # self.remove_remote(remote)

    def get_relation(self, remote_name: str):
        return self._relation_ctxs[remote_name].relation

    def update_remote(self, remote_name: str,
                      app_data: DataBag = None,
                      units: Dict[int, DataBag] = None):
        self._relation_ctxs[remote_name].update(app_data, units)


class RelationCtx:
    def __init__(self, endpoint: EndpointCtx, remote: Remote):
        self._endpoint = endpoint
        self.remote = remote
        self.relation: Optional[Relation] = None
        self.units = []

    def __enter__(self):
        ep = self._endpoint
        remote = self.remote
        harness = ep.harness
        relation_name = ep._relation_name

        r_id = harness.add_relation(relation_name, remote['name'])
        self.relation = harness.model.get_relation(relation_name, r_id)
        self._sync_remote()
        return self

    def update(self, app_data: DataBag = None,
               units: Dict[int, DataBag] = None):
        """Updates the remote with this data and syncs with harness."""
        if not self.relation:
            raise RuntimeError('enter the context first')

        # sync remote
        remote = self.remote
        if app_data is not None:
            remote['app_data'] = app_data
        if units is not None:
            remote['units'] = units
        self._sync_remote()

    def _sync_remote(self):
        remote_name = self.remote['name']
        app_data = self.remote['app_data']
        units = self.remote['units']

        harness = self._endpoint.harness

        # app data
        harness.update_relation_data(self.relation.id, remote_name, app_data)
        # remote units and their data
        for unit in units.keys():
            # create unit if it doesn't exist yet:
            unit_name = f"{self.remote['name']}/{unit}"
            if unit_name not in harness._backend._relation_app_and_units[self.relation.id]['units']:
                self.add_unit(unit, units[unit])

        for unit in self.units:
            if unit not in units:
                self.remove_unit(unit)

    def add_unit(self, unit: int, data: DataBag):
        remote = self.remote
        r_id = self.relation.id
        harness = self._endpoint.harness
        self.units.append(unit)

        remote['units'][unit] = data

        unit_name = f"{remote['name']}/{unit}"
        harness.add_relation_unit(r_id, unit_name)
        harness.update_relation_data(r_id, unit_name, data)

    def remove_unit(self, unit: int):
        unit_name = f"{self.remote['name']}/{unit}"
        self._endpoint.harness.remove_relation_unit(self.relation.id, unit_name)

    def __exit__(self, *exc):
        self._endpoint.harness.remove_relation(self.relation.id)
        self.relation = None
        self.units = []
