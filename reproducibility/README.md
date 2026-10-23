# Research source supplement

Supporting source for *Protecting proprietary website logic* by Emil Valiyev, available at https://doi.org/10.5281/zenodo.23599906.

This version contains selected source, protocols, synthetic workloads, and implementation examples. Original experiment evidence, run credentials, local execution metadata, and publication hash manifests are excluded. The manuscript is unchanged. No research experiments or benchmarks were rerun during publication or this cleanup.

## What readers can use

| Folder | Contents |
| --- | --- |
| `research/lab`, `research/broker` | Phase I local websites, server, extension, and calculation source |
| `phase2/websites` | Phase II synthetic workloads and local services |
| `phase2/attacks`, `phase2/benchmarks` | Experiment and measurement drivers |
| `phase2/protections`, `phase2/browser` | Extension prototypes, browser-module templates, and preparation scripts |
| `phase2/binary` | Native/WebAssembly source, build scripts, and selected static recovery examples |
| `phase2/versions` | Earlier source snapshots for comparison |

Start with `research/protocol.json` and `phase2/protocol.json`. Algorithms, model generators, and the synthetic Alice/Bob login fixtures are retained. Those fixture passwords apply only to the included local demonstration accounts.

The original run records are unavailable in this release. Readers can inspect the methods and create new local runs after supplying the dependencies below. New results must be described as new runs; this source package alone does not let a reviewer independently audit every reported original observation. Earlier snapshots are reference source, with placeholders replacing their provisioning values. They are not standalone runnable packages: some depend on files and paths from the original workspace.

## Prepare a separate local copy

Use a separate checkout for reruns. From its `reproducibility` directory:

```powershell
python prepare_local.py
python -m pip install -r requirements.txt
```

`prepare_local.py` creates the two private output directories and a fresh Phase II v1 provisioning configuration if none exists. It preserves an existing configuration and does not start a server, browser, or experiment. Generated configurations, evidence, profiles, logs, and build outputs are excluded by `.gitignore`. Git can still include ignored files if explicitly forced; review any future publication separately.

Python dependency versions are not locked in this supplement, and compatibility with a new installation has not been verified. Obtain the following separately:

- Node.js on PATH and Python with the dependencies in `requirements.txt`. Node services use standard library modules. Python subprocesses use the current interpreter.
- The external DoppelGNG project for Phase I browser drivers and capture scripts. Set `DOPPELGNG_ROOT` to its checkout, or put it in `.doppelgng` beside these folders. Its own browser setup is also required.
- Waterfox and geckodriver for the Selenium/component drivers. Put geckodriver on PATH or set `GECKODRIVER` to its executable. The component workflow expects a pristine distribution at `phase2/browser/waterfox-pristine/waterfox.exe`, including its `defaults/pref` folder.
- Chrome for Testing at `phase2/browser/chrome-win64/chrome.exe` for CDP drivers. `phase2/browser/get_cft.ps1` downloads the current official release; that may differ from the study's browser version.
- Windows native tools for the binary experiments. The build scripts specify Visual Studio 2022 Build Tools, MSVC `14.44.35207`, and Windows SDK `10.0.26100.0`; adjust tool paths to an equivalent installed toolchain and record the change. `run_ghidra.ps1` expects `tools/jdk-21.0.12.1+1` and `tools/ghidra_12.1.4_PUBLIC` under this directory. Enclave work also requires compatible Windows features and hardware; the reported attempt did not verify hardware protection.

## Entry points and startup order

Run the setup helper before any Python driver. Commands below are relative to `reproducibility`. Servers use loopback ports; Phase II variants share `45911` and `45912`, so run one variant at a time. CDP drivers additionally use `45915`.

| Workflow | Startup order |
| --- | --- |
| Phase I local website | Start `node research/lab/server.mjs`, then open `http://127.0.0.1:4381/` or run `python research/run_waterfox.py` with DoppelGNG configured. |
| Phase I extension broker | Start `node research/broker/server.mjs` first and leave it running. It creates a fresh extension config before `python research/run_broker.py` packages the extension. |
| Phase II standard web fixture | Run `python phase2/attacks/standard_web.py guarded`; the driver starts its own suite service and disposable Chrome instance. `baseline` selects the comparison variant. |
| Phase II recipient approval | Run `python phase2/attacks/provisioning_test.py`; the driver generates its administrator token, starts its provider, and packages the newly generated extension config. Do not start a competing Phase II service first. |
| Phase II browser component | Follow the preparation sequence below, then select a component driver. |

The loopback services and drivers create new request records, environment details, capsules, and profiles locally. These outputs are private working material unless deliberately reviewed for another release. Stop services when a workflow finishes.

### Browser component preparation

Several older drivers read `phase2/evidence/ground-truth.json`, which is deliberately absent from this release. To supply a new input from the retained generator:

1. Run `node phase2/websites/server.mjs`. Startup creates a fresh v1 credential config and a timestamped `phase2/evidence/ground-truth-*.json` file. Once the service is listening, stop it with Ctrl+C.
2. Select that newly created file explicitly and run `python prepare_local.py --ground-truth phase2/evidence/ground-truth-<timestamp>.json`, replacing `<timestamp>` with its filename. The helper copies its bytes to the older driver's expected name and refuses to overwrite an existing reference. This is a fresh synthetic input, not recovered original evidence.
3. With the pristine Waterfox distribution installed, run the commands below in order:

```powershell
python phase2/browser/prepare_waterfox.py
python phase2/browser/prepare_component_v2.py
python phase2/browser/prepare_component_v3.py
```

These scripts modify a dedicated `waterfox-broker` distribution. Their source transformations check the expected template anchors before writing. For the separate browser-owner countertest, also run `python phase2/browser/prepare_owner_copy.py`. Only that extra `waterfox-owner` copy removes the custom guards and permits program export.

The prepared modules contain the current local credential. Do not publish those generated browser folders. `component_test.py` and `component_bench.py` read the same config and pass it to their own model-server process. Starting `server.mjs` manually again without that override rotates the config; repeat preparation before using an existing browser copy with a changed credential.

`python phase2/benchmarks/component_bench.py` starts its own service for a matched timing comparison. It deliberately enables a plaintext control model. `python phase2/attacks/component_test.py guarded` exercises the component, and `owner` selects its separate countertest copy. The component test also visits `https://emilvaliyev.com/` for a live compatibility observation; it is not an entirely offline workflow. `research/run_doppel.py` likewise defaults to that live website. Review their targets before running them and use only systems you own or are authorized to test.

## Inputs that remain unavailable

- Replay, evidence-audit, proxy, and some learning scripts refer to removed captures or original result directories. They require compatible records from a separate run or authorized archive; those records cannot be recovered from this version.
- `phase2/protocol.py` reads the original report DOCX, which is not included. Read the retained `protocol.json` instead of running that generator.
- Native recovery helpers require locally built `forest.dll` and generated `recovered-rdata.bin`. Build/recovery tools and their outputs are separate prerequisites. Some build scripts overwrite generated source or static recovery examples, which is another reason to use a disposable rerun copy.
- Archived `phase2/versions` scripts retain historical path assumptions. Use the current entry points for new runs rather than copying the placeholder-bearing archived modules into a browser.

## Changes in this version

Two archived browser-module credentials were replaced with explicit placeholders, and the private report checksum was omitted from the public protocol copy. The five removed configuration files, original evidence, and metadata were not restored. Browser preparation now matches the formatted source and rejects missing or duplicate anchors; current services create their output directory before writing. The setup helper supplies fresh private inputs, and the dependency list and startup order are documented.

Source formatting and setup changes affect bytes and may affect payload sizes. This release supplies no new performance measurements. It has passed static syntax and preparation checks, but a full browser, native-tool, or scientific rerun has not been performed for publication.

Use the current release or the clean revision provided with reviewer correspondence. Older Git commits predate this cleanup and can still contain removed material; updating the current branch does not erase repository history.
