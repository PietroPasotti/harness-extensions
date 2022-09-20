import dataclasses
import json
from dataclasses import dataclass
from functools import partial
from typing import Tuple, Any, Dict, Union, Iterable

import ops
import yaml
from ops.testing import CharmType

if __name__ == '__main__':
    pass  # to prevent isort from complaining about what follows

# from networking:
import logging
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from typing import Dict, List, Optional, TypedDict, Union, TextIO

from ops.model import Relation

network_logger = logging.getLogger("networking")
CharmMeta = Optional[Union[str, TextIO, dict]]


class NetworkingError(RuntimeError):
    """Base class for errors raised from this module."""


JUJU_INFO = {
    "bind-addresses": [
        {
            "mac-address": "",
            "interface-name": "",
            "interfacename": "",
            "addresses": [{"hostname": "", "value": "1.1.1.1", "cidr": ""}],
        }
    ],
    "bind-address": "1.1.1.1",
    "egress-subnets": ["1.1.1.2/32"],
    "ingress-addresses": ["1.1.1.2"],
}  # type: _Network

_Address = TypedDict("_Address", {"hostname": str, "value": str, "cidr": str})
_BindAddress = TypedDict(
    "_BindAddress",
    {
        "mac-address": str,
        "interface-name": str,
        "interfacename": str,  # ?
        "addresses": List[_Address],
    },
)
_Network = TypedDict(
    "_Network",
    {
        "bind-addresses": List[_BindAddress],
        "bind-address": str,
        "egress-subnets": List[str],
        "ingress-addresses": List[str],
    },
)


def activate(juju_info_network: "_Network" = JUJU_INFO):
    """Patches harness.backend.network_get and initializes the juju-info binding."""
    global PATCH_ACTIVE, _NETWORKS
    if PATCH_ACTIVE:
        raise NetworkingError("patch already active")
    assert not _NETWORKS  # type guard

    from ops.testing import _TestingModelBackend

    _NETWORKS = defaultdict(dict)
    _TestingModelBackend.network_get = _network_get  # type: ignore
    _NETWORKS["juju-info"][None] = juju_info_network

    PATCH_ACTIVE = True


def deactivate():
    """Undoes the patch."""
    global PATCH_ACTIVE, _NETWORKS
    assert PATCH_ACTIVE, "patch not active"

    PATCH_ACTIVE = False
    _NETWORKS = None  # type: ignore


_NETWORKS = None  # type: Optional[Dict[str, Dict[Optional[int], _Network]]]
PATCH_ACTIVE = False


def _network_get(_, endpoint_name, relation_id=None) -> _Network:
    if not PATCH_ACTIVE:
        raise NotImplementedError("network-get")
    assert _NETWORKS  # type guard

    try:
        endpoints = _NETWORKS[endpoint_name]
        network = endpoints.get(relation_id)
        if not network:
            # fall back to default binding for relation:
            return endpoints[None]
        return network
    except KeyError as e:
        raise NetworkingError(
            f"No network for {endpoint_name} -r {relation_id}; "
            f"try `add_network({endpoint_name}, {relation_id} | None, Network(...))`"
        ) from e


def add_network(
        endpoint_name: str,
        relation_id: Optional[int],
        network: _Network,
        make_default=False,
):
    """Add a network to the harness.

    - `endpoint_name`: the relation name this network belongs to
    - `relation_id`: ID of the relation this network belongs to. If None, this will
        be the default network for the relation.
    - `network`: network data.
    - `make_default`: Make this the default network for the endpoint.
       Equivalent to calling this again with `relation_id==None`.
    """
    if not PATCH_ACTIVE:
        raise NetworkingError("module not initialized; " "run activate() first.")
    assert _NETWORKS  # type guard

    if _NETWORKS[endpoint_name].get(relation_id):
        network_logger.warning(
            f"Endpoint {endpoint_name} is already bound "
            f"to a network for relation id {relation_id}."
            f"Overwriting..."
        )

    _NETWORKS[endpoint_name][relation_id] = network

    if relation_id and make_default:
        # make it default as well
        _NETWORKS[endpoint_name][None] = network


def remove_network(endpoint_name: str, relation_id: Optional[int]):
    """Remove a network from the harness."""
    if not PATCH_ACTIVE:
        raise NetworkingError("module not initialized; " "run activate() first.")
    assert _NETWORKS  # type guard

    _NETWORKS[endpoint_name].pop(relation_id)
    if not _NETWORKS[endpoint_name]:
        del _NETWORKS[endpoint_name]


def Network(
        private_address: str = "1.1.1.1",
        mac_address: str = "",
        hostname: str = "",
        cidr: str = "",
        interface_name: str = "",
        egress_subnets=("1.1.1.2/32",),
        ingress_addresses=("1.1.1.2",),
) -> _Network:
    """Construct a network object."""
    return {
        "bind-addresses": [
            {
                "mac-address": mac_address,
                "interface-name": interface_name,
                "interfacename": interface_name,
                "addresses": [
                    {"hostname": hostname, "value": private_address, "cidr": cidr}
                ],
            }
        ],
        "bind-address": private_address,
        "egress-subnets": list(egress_subnets),
        "ingress-addresses": list(ingress_addresses),
    }


_not_given = object()  # None is meaningful, but JUJU_INFO is mutable


@contextmanager
def networking(
        juju_info_network: Optional[_Network] = _not_given,  # type: ignore
        networks: Optional[Dict[Union[str, Relation], _Network]] = None,
        make_default: bool = False,
):
    """Context manager to activate/deactivate networking within a scope.

    Arguments:
        - `juju_info_network`: network assigned to the implicit 'juju-info' endpoint.
        - `networks`: mapping from endpoints (names, or relations) to networks.
        - `make_default`: whether the networks passed as relations should also
          be interpreted as default networks for the endpoint.

    Example usage:
    >>> with networking():
    >>>     assert charm.model.get_binding('juju-info').network.private_address

    >>> foo_relation = harness.model.get_relation('foo', 1)
    >>> bar_relation = harness.model.get_relation('bar', 2)
    >>> with networking(networks={
    ...         foo_relation: Network(private_address='42.42.42.42')}
    ...         'bar': Network(private_address='50.50.50.1')},
    ...         make_default=True,
    ...         ):
    >>>     assert charm.model.get_binding(foo_relation).network.private_address
    >>>     assert charm.model.get_binding('foo').network.private_address
    >>>     assert charm.model.get_binding('bar').network.private_address
    ...
    >>>     # this will raise an error! We only defined a default bar
    >>>     # network, not one specific to this relation ID.
    >>>     # assert charm.model.get_binding(bar_relation).network.private_address

    """
    global _NETWORKS
    old = deepcopy(_NETWORKS)
    patch_was_inactive = False

    if juju_info_network is _not_given:
        juju_info_network = JUJU_INFO

    if not PATCH_ACTIVE:
        patch_was_inactive = True
        activate(juju_info_network or JUJU_INFO)
    else:
        assert _NETWORKS  # type guard

        if juju_info_network:
            _NETWORKS["juju-info"][None] = juju_info_network

    for binding, network in networks.items() if networks else ():
        if isinstance(binding, str):
            name = binding
            bind_id = None
        elif isinstance(binding, Relation):
            name = binding.name
            bind_id = binding.id
        else:
            raise TypeError(binding)
        add_network(name, bind_id, network, make_default=make_default)

    yield

    _NETWORKS = old
    if patch_was_inactive:
        deactivate()


# from  HARNESS_CTX v0

import typing
from typing import Callable, Protocol, Type

from ops.charm import CharmBase, CharmEvents
from ops.framework import BoundEvent, Handle
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
            meta: Optional[CharmMeta] = None,
            actions: Optional[CharmMeta] = None,
            config: Optional[CharmMeta] = None,
            event_args: Tuple[Any, ...] = (),
            event_kwargs: Dict[str, Any] = None
    ):
        self.charm_cls = charm
        self.emitter = emitter
        self.event_name = event_name.replace("-", "_")
        self.event_args = event_args
        self.event_kwargs = event_kwargs or {}

        def _to_yaml(obj):
            if isinstance(obj, str):
                return obj
            elif not obj:
                return None
            return yaml.safe_dump(obj)

        self.harness_kwargs = {
            'meta': _to_yaml(meta),
            'actions': _to_yaml(actions),
            'config': _to_yaml(config)
        }

    def __enter__(self):
        self._harness = harness = Harness(self.charm_cls, **self.harness_kwargs)
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
            return typing.cast(BoundEvent, event)

        self._emitter = bound_ctx = Emitter(harness, _emit)
        return bound_ctx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._emitter.emitted:
            self._emitter.emit()
        self._harness.framework.on.commit.emit()  # type: ignore


# from show-relation!
@dataclass
class Metadata:
    endpoint: str
    interface: str
    app_name: str
    relation_id: int

    scale: int = 1
    units: Tuple[int, ...] = (0, )
    leader_id: int = 0

    @classmethod
    def from_dict(cls, obj):
        return cls(**obj)


@dataclass
class AppRelationData:
    meta: Metadata
    application_data: dict = dataclasses.field(default_factory=dict)
    units_data: Dict[int, dict] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_dict(cls, obj):
        meta = Metadata.from_dict(obj.pop('meta'))
        return cls(meta=meta, **obj)

    def copy(self):
        return dataclasses.replace()

# ACTUAL LIBRARY CODE. Dependencies above.

logger = logging.getLogger('evt-sequences')

ATTACH_ALL_STORAGES = "ATTACH_ALL_STORAGES"
CREATE_ALL_RELATIONS = "CREATE_ALL_RELATIONS"
BREAK_ALL_RELATIONS = "BREAK_ALL_RELATIONS"
DETACH_ALL_STORAGES = "DETACH_ALL_STORAGES"
META_EVENTS = {
    "ATTACH_ALL_STORAGES",
    "CREATE_ALL_RELATIONS",
    "BREAK_ALL_RELATIONS",
    "DETACH_ALL_STORAGES",
}


@dataclass
class Event:
    name: str
    args: Tuple[Any] = ()
    kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def is_meta(self):
        return self.name in META_EVENTS

    @classmethod
    def from_dict(cls, obj):
        return cls(**obj)


@dataclass
class NetworkSpec:
    name: str
    bind_id: int
    network: _Network
    is_default: bool = False

    @classmethod
    def from_dict(cls, obj):
        return cls(**obj)


@dataclass
class Context:
    config: Dict[str, Union[str, int, float, bool]] = None
    relations: Tuple[AppRelationData] = ()
    networks: Tuple[NetworkSpec] = ()
    leader: bool = False

    # todo: add pebble stuff, unit/app status, etc...

    @classmethod
    def from_dict(cls, obj):
        return cls(
            config=obj['config'],
            relations=tuple(AppRelationData.from_dict(raw_ard) for raw_ard in obj['relations']),
            networks=tuple(NetworkSpec.from_dict(raw_ns) for raw_ns in obj['networks']),
            leader=obj['leader']
        )


null_context = Context()


@dataclass
class Scene:
    event: Event
    context: Context = None
    name: str = ""

    def __iter__(self):
        yield from [self.context, self.event]

    @classmethod
    def from_dict(cls, obj):
        evt = obj['event']
        return cls(
            event=Event(evt) if isinstance(evt, str) else Event.from_dict(evt),
            context=Context.from_dict(obj['context']) if obj['context'] is not None else None,
            name=obj['name'],
        )


class _Builtins:
    def __init__(self):
        self.STARTUP_LEADER = Scenario.from_events(
            (
                'start',
                'leader-elected',
                'config-changed',
                'install',
            )
        )

        self.STARTUP_FOLLOWER = Scenario.from_events(
            (
                ATTACH_ALL_STORAGES,
                'install',
                CREATE_ALL_RELATIONS,
                'leader-settings-changed',
                'config-changed',
                'start',
            )
        )

        self.TEARDOWN = Scenario.from_events(
            (
                BREAK_ALL_RELATIONS,
                DETACH_ALL_STORAGES,
                'stop',
                'remove'
            )
        )


class Playbook:
    def __init__(self, scenes: Tuple[Scene, ...]):
        self._scenes = list(scenes)
        self._cursor = 0

    @property
    def is_done(self):
        return self._cursor < (len(self._scenes) - 1)

    def add(self, scene: Scene):
        self._scenes.append(scene)

    def next(self):
        self.scroll(1)
        return self._scenes[self._cursor]

    def scroll(self, n):
        if not 0 <= self._cursor + n <= len(self._scenes):
            raise RuntimeError(f"Cursor out of bounds: can't scroll ({self}) by {n}.")
        self._cursor += n

    def restart(self):
        self._cursor = 0

    def __repr__(self):
        return f"<Playbook {self._cursor}/{len(self._scenes)}>"

    def __iter__(self):
        yield from self._scenes

    def __next__(self):
        return self.next()

    def dump(self) -> str:
        """Serialize."""
        obj = {'scenes': [dataclasses.asdict(scene) for scene in self._scenes]}
        return json.dumps(obj, indent=2)

    @staticmethod
    def load(s: str) -> 'Playbook':
        obj = json.loads(s)
        scenes = tuple(Scene.from_dict(raw_scene) for raw_scene in obj['scenes'])
        return Playbook(scenes=scenes)


class _UnboundScenario:
    def __init__(self,
                 playbook: Playbook = Playbook(()),
                 ):
        self._playbook = playbook

    @property
    def playbook(self):
        return self._playbook

    def __call__(self, charm_type: CharmType,
                 meta: Optional[CharmMeta] = None,
                 actions: Optional[CharmMeta] = None,
                 config: Optional[CharmMeta] = None):
        return Scenario(charm_type=charm_type,
                        playbook=self.playbook,
                        meta=meta,
                        actions=actions,
                        config=config)


class Scenario:
    if typing.TYPE_CHECKING:
        builtins: _Builtins

    def __init__(self, charm_type: CharmType,
                 playbook: Playbook = Playbook(()),
                 meta: Optional[CharmMeta] = None,
                 actions: Optional[CharmMeta] = None,
                 config: Optional[CharmMeta] = None):
        self._playbook = playbook
        self._charm_type = charm_type
        self._meta = meta
        self._actions = actions
        self._config = config

    @staticmethod
    def from_scenes(
            playbook: Union[Scene, Iterable[Scene]]
    ) -> _UnboundScenario:
        _scenes = (playbook,) if isinstance(playbook, Scene) else tuple(playbook)
        for i, scene in enumerate(_scenes):
            if not scene.name:
                scene.name = f"<Scene {i}>"
        return _UnboundScenario(playbook=Playbook(_scenes))

    @staticmethod
    def from_events(
            events: typing.Sequence[Union[str, Event]]
    ) -> Callable[[CharmType], 'Scenario']:

        def _to_event(obj):
            if isinstance(obj, str):
                return Event(obj)
            elif isinstance(obj, Event):
                return obj
            else:
                raise TypeError(obj)

        return Scenario.from_scenes(map(Scene, map(_to_event, events)))

    @property
    def playbook(self) -> Playbook:
        return self._playbook

    def __enter__(self):
        self._entered = True
        activate()
        return self

    def __exit__(self, *exc_info):
        self._playbook.restart()
        deactivate()
        self._entered = False
        if exc_info:
            exc_type, exc, tb = exc_info
            raise exc
        return self

    def _setup_context(self, harness: Harness, context: Context):
        be: ops.testing._TestingModelBackend = harness._backend

        # relation data
        # FIXME: the harness will fire relation events!
        for relation in context.relations:
            remote_app_name = relation.meta.app_name
            r_id = harness.add_relation(relation.meta.endpoint, remote_app_name)
            if remote_app_name != harness.charm.app.name:
                if relation.application_data:
                    harness.update_relation_data(r_id, remote_app_name,
                                                 relation.application_data)
                for unit_n, unit_data in relation.units_data.items():
                    unit_name = f"{remote_app_name}/{unit_n}"
                    harness.add_relation_unit(r_id, unit_name)
                    harness.update_relation_data(r_id, unit_name, unit_data)
            else:
                if relation.application_data:
                    harness.update_relation_data(r_id, harness.charm.app.name,
                                                 relation.application_data)
                if relation.units_data:
                    if not tuple(relation.units_data) == (0,):
                        raise RuntimeError('Only one local unit is supported.')
                    harness.update_relation_data(r_id, harness.charm.unit.name,
                                                 relation.units_data[0])
        # leadership:
        harness.set_leader(context.leader)

        # networking
        for network in context.networks:
            add_network(endpoint_name=network.name,
                        relation_id=network.bind_id,
                        network=network.network,
                        make_default=network.is_default)

    def _cleanup_context(self, harness: Harness, context: Context):
        # Harness will be reinitialized, so nothing to clean up there;
        # however:
        for network in context.networks:
            remove_network(endpoint_name=network.name,
                           relation_id=network.bind_id)

    def _play_meta(self, event: Event,
                   context: Context = None,
                   add_to_playbook: bool = False):
        # decompose the meta event
        events = []

        if event.name == ATTACH_ALL_STORAGES:
            logger.warning(f"meta-event {event.name} not supported yet")
            return

        elif event.name == DETACH_ALL_STORAGES:
            logger.warning(f"meta-event {event.name} not supported yet")
            return

        elif event.name == CREATE_ALL_RELATIONS:
            if context:
                for relation in context.relations:
                    evt = Event(f"{relation.endpoint}-relation-created")
                    events.append(evt)

        elif event.name == BREAK_ALL_RELATIONS:
            if context:
                for relation in context.relations:
                    evt = Event(f"{relation.endpoint}-relation-broken")
                    events.append(evt)
                    # todo should ensure there's no relation data in this context?

        else:
            raise RuntimeError(f'unknown meta-event {event.name}')

        logger.debug(f"decomposed meta {event.name} into {events}")
        for event in events:
            self.play(event, context, add_to_playbook=add_to_playbook)

    def play(self, evt: Union[Event, str],
             context: Context = None,
             add_to_playbook: bool = False):
        if not self._entered:
            raise RuntimeError("Scenario.play() should be only called "
                               "within the Scenario's context.")
        event = Event(evt) if isinstance(evt, str) else evt

        if event.is_meta:
            return self._play_meta(event, context,
                                   add_to_playbook=add_to_playbook)

        with HarnessCtx(self._charm_type,
                        event_name=event.name,
                        event_args=event.args,
                        event_kwargs=event.kwargs,
                        meta=self._meta,
                        actions=self._actions,
                        config=self._config) as ctx:
            if context:
                self._setup_context(ctx.harness, context)
            evt = ctx.emit()
            if context:
                self._cleanup_context(ctx.harness, context)

        if add_to_playbook:
            # so we can later export it
            self._playbook.add(Scene(context=context, event=event))
        return evt

    def play_next(self):
        next_scene: Scene = self._playbook.next()
        self.play(*next_scene)

    def play_until_complete(self):
        with self:
            for context, event in self._playbook:
                self.play(evt=event, context=context)


Scenario.builtins = _Builtins()
