"""Simulate the QSA pending ring under speculative verify (3-Oct-2026, daniel-draft).

Mirrors the slot arithmetic of build_pending_ring_slots / build_group_ring_slots / the graph row kernel (orig: ring =
ratio; patched: ring = R) and the order a paged forward runs in: store every window token's key, then compress each
group a window token completes from the ring. One request; random acceptance; checks that every group's FINAL
compressed key (from the last forward that compressed it) was built from the accepted keys of its 4 members.
  python sim_ring.py
"""
import random

RATIO = 4
REQ = 3  # request pool slot (slot 0 is the dump)


def run(ring, D, iters=4000, seed=0):
    rnd = random.Random(seed)
    store = {}                      # ring slot -> (position, writer forward)
    final_key = {}                  # position -> writer forward of its accepted token
    group_used = {}                 # group end -> list of (position, writer) read at its last compression
    # prefill: extend of L0 tokens; complete groups compress from the chunk itself; the pending tail goes to the ring
    L0 = rnd.randrange(64, 200)
    for x in range(L0):
        final_key[x] = 0
        if x >= (L0 // RATIO) * RATIO:
            store[REQ * ring + x % ring] = (x, 0)
    for e in range(RATIO - 1, (L0 // RATIO) * RATIO, RATIO):
        group_used[e] = [(m, 0) for m in range(e - RATIO + 1, e + 1)]
    p, fwd = L0, 0
    for _ in range(iters):
        fwd += 1
        window = range(p, p + D)
        for x in window:                                  # 1) store all keys of this forward
            store[REQ * ring + x % ring] = (x, fwd)
        for x in window:                                  # 2) compress groups completed in this forward
            if (x + 1) % RATIO == 0:
                group_used[x] = [store.get(REQ * ring + m % ring) for m in range(x - RATIO + 1, x + 1)]
        a = rnd.randint(1, D)                             # tokens kept (root + accepted drafts)
        for x in range(p, p + a):
            final_key[x] = fwd
        p += a
    bad = 0
    for e, used in group_used.items():
        if e + 1 > p:                                     # group not complete in the committed sequence
            continue
        want = [(m, final_key[m]) for m in range(e - RATIO + 1, e + 1)]
        bad += used != want
    total = sum(1 for e in group_used if e + 1 <= p)
    return bad, total


if __name__ == "__main__":
    print(f"{'ring':>4s} {'D':>3s} {'bad groups':>11s}  (cap: D <= ratio if ring == ratio, else D <= ring - ratio + 1)")
    for ring, D in [(4, 1), (4, 2), (4, 3), (4, 4), (8, 4), (8, 5), (8, 6), (12, 8), (12, 9), (12, 10), (16, 13),
                    (20, 16), (20, 17), (20, 18)]:
        bad, total = run(ring, D)
        print(f"{ring:4d} {D:3d} {bad:6d}/{total:<6d} {'OK' if bad == 0 else 'CORRUPT'}")
