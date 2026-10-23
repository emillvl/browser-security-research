<div align="center">

# Protecting Proprietary Website Logic

**An experimental study of what browsers can recover, what servers can protect, and what outputs can reveal.**

**Emil Valiyev**

[**Read the manuscript**](Protecting_proprietary_website_logic_Emil_Valiyev.pdf) · [**Zenodo record**](https://zenodo.org/records/23599906) · [**Supporting experiments**](reproducibility/README.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23599906.svg)](https://doi.org/10.5281/zenodo.23599906)

</div>

---

## At a glance

When a website sends code to a browser, how much of that logic can really be kept private?

This study tests different places to put a program and different ways to restrict access to it. The experiments cover browser-delivered code, encrypted delivery, server-side execution, extensions, separate browser components, and an attempted protected-execution environment. It also looks at a related problem: what someone might learn from a system's answers without ever seeing its implementation.

| Area | What the experiments found |
| --- | --- |
| **Code delivered to a client** | Programs remained recoverable in the tested cases, including when delivery was encrypted. |
| **Separate browser components** | Some page-level observers could not see the program, but browser-owner access recovered it. |
| **Server-side controls** | The tested unauthorized, modified, expired, and duplicate requests were rejected; legitimate access and saved outputs remained separate concerns. |
| **Learning from outputs** | A simple arithmetic function was learned successfully; the tested methods were inaccurate on a more complex decision model. |
| **Protected execution** | The attempt stopped at program loading. Hardware-backed protection was not verified. |

These are findings from the tested setups, **not** a claim that every implementation of a technique behaves identically.

## Paper and publication

**[Read the full PDF →](Protecting_proprietary_website_logic_Emil_Valiyev.pdf)**

- **Author:** Emil Valiyev
- **Preprint:** [Zenodo](https://zenodo.org/records/23599906)
- **DOI:** [10.5281/zenodo.23599906](https://doi.org/10.5281/zenodo.23599906)
- **Journal status:** Submitted to *Computers & Security* on **23 October 2026**, through the subscription publishing route.

Submission is confirmed. **Peer review and acceptance are not implied.**

## Abstract

Keeping a website's private calculations on an authorized server gave the strongest demonstrated protection for its source code in this study. I compared programs sent to a browser, encrypted program delivery, server execution, browser extensions, separate browser components, and an attempted protected-execution environment. Each experiment asked what could be copied, which operations remained allowed, and what the returned answers revealed. Programs delivered to the user's device remained recoverable in the tested cases. Preventing a secret key from being exported did not prevent recovery of the program decrypted with that key. Separate browser components hid programs from selected observers inside the page, but browser-owner access recovered them. Server checks rejected tested unauthorized requests, changed inputs, expired requests, and duplicates. A copied interface could still use a legitimate account, and saved answers remained available after the service stopped. Learning the calculation from its answers succeeded for a simple arithmetic function but remained inaccurate for a more complex decision model under the tested methods. The protected-execution attempt stopped at program loading, so hardware protection remained unverified. These results support keeping sensitive implementations on the server where practical, while evaluating permitted use, visible copying, and disclosure through answers separately.

## Reproducibility materials

The [experiment supplement](reproducibility/README.md) retains selected research source, protocols, and implementation examples. The current version excludes original run evidence, local execution metadata, and run-specific credentials. Its setup instructions explain how to create fresh local inputs and which scripts still require unavailable original inputs. This is a selected source release; the original observations cannot all be reconstructed from this package alone. No experiments were rerun for publication or cleanup.

---

<div align="center">

**[Manuscript](Protecting_proprietary_website_logic_Emil_Valiyev.pdf) · [Reproducibility notes](reproducibility/README.md) · [Zenodo](https://zenodo.org/records/23599906)**

</div>
