"""The Autonomous Engine — De Waag's layered trading brain.

Ten layers, one direction of flow (see docs/AUTONOMOUS-ENGINE.html):

    L0/L1  perceive + understand      -> engine.signals (features)
    L2     regime          (weather)  -> auto.regime
    L3     alpha ensemble  (committee)-> auto.strategies
    L4     meta-allocator  (ML slot)  -> auto.allocator
    L5     construction    (architect)-> auto.construct
    L6     risk & constitution veto   -> engine.sizing.gate_order (reused)
    L7     execution                  -> portfolio.preview / engine.costs (reused)
    L8     autonomy loop + memory     -> auto.pipeline + jobs
    L9     approval gate              -> auto.proposals (+ portfolio.execute)

Nothing here can place an order. Every proposal stops at L9 and waits for
one human approval — by design, and enforced by portfolio.execute's gates.
"""
