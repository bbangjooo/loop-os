"""Starting policy: finish each order before beginning the next one."""


def schedule(orders):
    plan = []
    t = 0
    for order in sorted(orders, key=lambda o: (o["arrival"], o["id"])):
        t = max(t, order["arrival"])
        for kind in ("prep", "brew", "serve"):
            plan.append({"kind": kind, "orders": [order["id"]], "start": t})
            t += order[kind]
    return plan
