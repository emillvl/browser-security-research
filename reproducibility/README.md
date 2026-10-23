# Experiment source and selected recorded data

Supporting files for *Protecting proprietary website logic* by Emil Valiyev, available at https://doi.org/10.5281/zenodo.23599906.

This public supplement contains selected research source, protocols, and implementation examples. Recorded evidence, local metadata, and hardcoded experiment credentials have been excluded. It is not a complete archive. No experiments were rerun for this cleanup.

## Contents

| Folder | Contents |
| --- | --- |
| `research/lab`, `research/broker` | Phase I website, server, extension, and calculation source |
| `phase2/websites` | Phase II application workloads and local server source |
| `phase2/attacks`, `phase2/benchmarks` | Experiment and measurement entry points |
| `phase2/protections`, `phase2/browser` | Extension prototypes, custom browser modules, and preparation scripts |
| `phase2/binary` | Native/WebAssembly source, build scripts, and selected recovery records |
| `phase2/versions` | Earlier source versions with the same readability cleanup |

This is a selected public supplement, not the complete local archive.

## Setup and entry points

Keep the directory structure intact. Start with the protocols in `research/protocol.json` and `phase2/protocol.json`.

For a rerun, use a separate copy to preserve the recorded data. Obtain compatible Node.js, Python dependencies, browser distributions, drivers, compilers, Ghidra, and the external DoppelGNG project separately. Python drivers use Selenium and, where required, websocket-client. Native-code, browser-component, and enclave experiments require the relevant Windows tools and hardware. This package has not been tested as a portable installation.

Node.js is resolved from PATH, and Python subprocesses use the current interpreter. Set `DOPPELGNG_ROOT` to the external DoppelGNG checkout, or place that checkout at `reproducibility/.doppelgng`. Put geckodriver on PATH or set `GECKODRIVER` to its executable path. Other tool and browser locations remain relative to the research folders.

Preserved entry points include:

- Phase I: `research/lab/server.mjs`, `research/run_waterfox.py`, and `research/run_broker.py`.
- Phase II: `phase2/websites/suite.mjs`, `phase2/attacks/standard_web.py`, and `phase2/benchmarks/component_bench.py`.
- Other scripts remain in `phase2/attacks`, `phase2/browser`, and `phase2/binary` with their original arguments.

Recorded outputs describe the original runs. Formatting changes source bytes and may change payload sizes; these publication copies have no new performance measurements. The experimental services bind to loopback addresses. Run scripts only in an environment you own or are authorized to test.

## Publication boundaries

Recorded evidence files, credentials, original workspace hash metadata, and publication checksum manifests were removed from this repository. The original manuscript was not changed. Scripts relying on excluded configuration or evidence may require fresh local, non-committed inputs to run.
