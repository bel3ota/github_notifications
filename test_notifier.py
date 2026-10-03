"""Self-check against live public GitHub data (no token needed). Run: python3 test_notifier.py"""
import notifier as n

out = []
n.post = out.append

# real public events format without crashing
for e in n.gh("/users/torvalds/events/public?per_page=30") + n.gh("/repos/python/cpython/events?per_page=30"):
    assert n.fmt_event(e)
print(n.fmt_event(e))

# run state machine: first seen in_progress -> "started"; queued->in_progress no repost; completed -> result once
run = dict(n.gh("/repos/python/cpython/actions/runs?per_page=1")["workflow_runs"][0])
n.gh = lambda path: [{"full_name": "x/y"}] if path.startswith("/user/repos") else ([] if "events" in path else {"workflow_runs": [run]})
state = {"events": [], "runs": {}}
for status in ("queued", "in_progress", "completed", "completed"):
    run["status"] = status
    n.poll(state, quiet=False)
assert len(out) == 2 and "started" in out[0] and "Build" in out[1], out
print(*out, sep="\n")

# quiet seeding posts nothing
out.clear(); run["id"] += 1
n.poll({"events": [], "runs": {}}, quiet=True)
assert out == []
print("ok")
