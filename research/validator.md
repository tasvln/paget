Runs a "validation" task: an independent, second-pass check that a
component's saved code is real, runnable Python — not whether its logic
is correct. No LLM involved here; this is purely mechanical, which is
the point — it's a check on whether the specialist produced actual code
versus prose/a truncated response/markdown leftovers, done by something
other than the agent grading its own work.

If the user has written their own test file alongside a component
(output/<component>/test_<component>.py), it gets run too. If it
doesn't exist, that step is silently skipped — this is the hook for
"the user can add test code themselves" without the validator ever
generating tests on its own.

On failure, this just reports validation_errors back through the
existing /agent/task/complete endpoint. The coordinator already knows
how to turn that into a refinement task pointed at component_id — see
coordinator.py's complete_task. This file doesn't create refinement
tasks itself and doesn't talk to a manager; it only flags and stops.