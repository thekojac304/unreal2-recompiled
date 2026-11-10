# Renderer configuration diagnosis

This isolated package preserves the consumed attempt and corrects the measured
`UseTrilinear` raw field expectation from 1 to `0x20`. It never changes game
configuration or normalizes guest memory. Native D3D8 tuples and the existing
initial SetRes stop are unchanged.

`profile_gate.py` saves CPU/frame, identities, all declared fields and capability
words before evaluating the exact profile. Individual mismatches, invalid bases
and unreadable fields stop diagnostically. Unknown true encodings remain refused.

The observed field table is from the saved SetRes entry renderer dump. The old
later aggregate assertion did not save its field reads. The report distinguishes
these phases and does not invent failing-time measurements.

No preparation command launches the game. Consult the output REPORT.txt and
verified seal before the separately authorized one-shot owner procedure. Strict
x87, WNDPROC and native-x86 compatibility remain failed and separately preserved.
