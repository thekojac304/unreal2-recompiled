# DirectInput mouse creation works; execution held on compiler instability

2026-10-23, US Eastern. Starting HEAD was clean at
`75b215317b55dd463183ad3a8f06872ca74962b1`. No work was reset or discarded.

The genuine translated client now passes `IDirectInput8W::CreateDevice` for `GUID_SysMouse`,
the seven-object mouse data format and both required property calls. The next executed fatal
is loading **U2AI.dll**, which exists in the verified snapshot but was absent from that client.
CS_Intro LoadMap again returns `0x12f52800`. **No selected-world tick completed.**

Further compiler/game execution is held after unexplained MSVC C1001 failures moved between
Engine_032, unchanged ParticleSystems_001 and unchanged Unreal2_000; the last build also reported
D8040 child-process communication failure. An isolated `/O1` ParticleSystems build passed.
No protected-input hash difference was detected. These observations do not establish the cause,
hardware health, or that a compiler flag fixes the instability.

[Detailed checkpoint and continuation boundary](DIRECTINPUT_DEVICE.md).
[Structured evidence](results/compare/input_device_resume.json).

| Requested translated milestone | Verified state |
|---|---|
| T1: selected CS_Intro LoadMap returns non-null | Yes, fresh run, world `0x12f52800` |
| T2: selected-world actor lifecycle completed | Unverified; direct-call observer remains unaccepted |
| T3: UGameEngine::Init returns | No |
| T4: selected ULevel::Tick enters | No |
| T5: selected tick returns to its caller | No |
| T6: bounded selected-world tick sequence | No |
| Translated D3D device / Present | None / none |

The interrupted DirectMusic regression sweep is now freshly complete against its preserved binary.
After the DirectInput change, the focused seven-positive/six-negative differential passes; the complete
post-change integration sweep was **not** run after the compiler stop. Preserve that distinction.

Pending, uncommitted experimental source includes U2AI linkage, Engine direct-call observers,
their build/identity changes and milestone summarization. A compiled/hash-checked world-observer
client exists, but it was **never executed or regression accepted**. Do not promote it to a runnable
accepted checkpoint or infer its world milestones from compilation.
