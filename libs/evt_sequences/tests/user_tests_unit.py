"""How we'd like user code to look like.
This is a "real" scenario.
"""
from ops.charm import CharmBase


def scenario_test():
    class CharmType(CharmBase):
        pass

    EvtSequence.builtins.STARTUP.play(CharmType)

    with EvtSequence.builtins.TEARDOWN(CharmType) as seq:
        seq.next()
        seq.next()
        seq.next()
        seq.next()
        seq.next()  # error

    with EvtSequence(CharmType) as seq:
        seq.fire(EventType)
        seq.fire(EventType)
        seq.fire(EventType)
        seq.fire(EventType)
