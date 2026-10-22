---
name: ui-component-review
description: "Review UI component APIs, composition, reuse, and fit with a repository's design system, including shadcn-style components. Use for component-design reviews and as a design check during requested UI implementation. Complements functional code review; visual styling or browser QA alone does not require this skill."
---

# UI component review

Decide whether a component has the right responsibilities and a predictable API. Compare it with the project's actual design system and the contracts of its underlying primitives. Explain what should stay, what should change, and the evidence behind each decision.

## Scope

- A review request produces a report. It does not authorize edits, commits, pushing, or posting a review. During an already authorized implementation, use these checks to guide that work without adding a new approval gate.
- Record the requested component or PR, exact base/head or working-tree changes, and the review's scope. Preserve unrelated work. Ask one question only if missing intent prevents a useful review.
- Identify the role: low-level primitive, reusable composition, or feature-specific component. Judge reuse against real callers and known planned uses. Neither one caller nor a location under `ui/` settles the right abstraction.
- Separate construction, interaction, and visual fidelity. State which were assessed. A screenshot alone does not establish API quality; source inspection alone does not establish rendered correctness.

## Find the comparison points

Read the relevant evidence before recommending a design:

1. Project instructions and the guides for frontend architecture, component styling, accessibility, and testing. Follow the project's guide index rather than treating nearby old code as policy.
2. The target's complete implementation, tests, stories, imports, and callers, including consumers outside the diff. Trace changed props, exports, and behaviour through those consumers.
3. The closest existing primitives and shipped compositions. Open their implementations and representative usage: what they already handle matters more than matching names.
4. The theme/token definitions and variant helpers touched by the concern. Inspect the design reference when one was supplied and visual fidelity is in scope. Record unavailable references instead of guessing their requirements.
5. Official upstream docs or source for the specific primitive contract or pattern being questioned. Identify the installed family and version first; shadcn projects can use different underlying libraries. Compare with the project's copied source, which may intentionally differ from today's registry. Do not migrate libraries as part of a review.

Keep a small evidence ledger: exact file/path or URL, what was inspected, and which decision it informs. Distinguish **project rule**, **upstream contract**, and **design recommendation**. A local styling preference does not cancel an accessibility or behavioural contract; explain the conflict when they differ.

Project guides can be stale, contradictory, or overbroad. For advice that affects the verdict, check the problem it was meant to prevent against the current component, supported library version, and intended use. Separate a convention mismatch from a demonstrated defect; "the guide says so" alone does not establish a design flaw. Report questionable guidance with the exact rule, the concrete cost or contradiction, and a supported alternative. Respect applicable session instructions and explicit constraints; explain conflicts rather than silently ignoring them. Reviewing a component does not authorize rewriting its project guides.

For shadcn projects, start with the applicable component's official composition examples at https://ui.shadcn.com/docs. Follow the matching primitive documentation for behaviour, such as Radix composition at https://www.radix-ui.com/primitives/docs/guides/composition. Use the relevant WAI-ARIA pattern at https://www.w3.org/WAI/ARIA/apg/patterns/ when assessing custom interaction semantics. Read only the pages needed for the component under review.

## Evaluate the boundaries

| Area | Question to resolve |
|---|---|
| Composition | Does an existing primitive or variant already own this behaviour? Does using it preserve the required design with less duplicated logic? |
| Props and DOM | Which element receives `className`, refs, native attributes, event handlers, labels, and test IDs? Are that target and the exposed types consistent? For multiple interactive elements, which props affect one segment and which affect the whole control? |
| Slots and children | Can callers supply the content they actually need without bypassing semantics or growing a new option for every row? Check prop/event/ref composition when using `asChild` or an equivalent mechanism. |
| State and events | Who owns open, selected, loading, and disabled state? Do supported controlled and uncontrolled paths work? Trace selection, dismissal, callback ordering, and focus restoration. |
| Dependencies | Are application routes, permissions, analytics, data fetching, or business decisions in the appropriate layer? Is a provider dependency intentional for this component's role, or an avoidable obstacle to its intended reuse? |
| Styling | Are tokens and existing variants used consistently? Are shared styles defined once? Trace overrides to an actual drift risk or behaviour loss before reporting them as a problem. |
| Access and layout | Do the rendered elements have the right semantics, names, focus behaviour, and disabled/loading behaviour? Do supported viewport/container sizes, long labels, and relevant theme states hold up? |

Prioritize the questions that apply. A simple button does not need every possible state or a full accessibility audit. Apply the project's required checks regardless of component size.

## Make the smallest justified recommendation

- Prefer the existing primitive when it fits. A native element is valid when implementing a primitive; wrapping everything in a shared component is not automatically an improvement.
- Keep a useful convenience component. Split it only when responsibilities or demonstrated variation warrant separate parts. Do not create a generic component family for speculative future callers.
- JSX slots, item arrays, variants, and compound components are alternatives. Choose based on actual consumers and the complexity each exposes. CVA, a particular export shape, or `forwardRef` is not a universal shadcn requirement; follow the project's React version and composition contracts.
- Treat repeated CSS overrides as a signal to inspect ownership, not proof of bad code. Name the concrete change that would drift or the shared behaviour being lost. Compare the smallest alternative, including leaving it alone.
- Preserve deliberate dependencies. A theme provider can belong to the design system; feature-specific analytics can belong to a feature component. Name the dependency and the actual reuse constraint rather than applying a blanket provider-free rule.
- Try to disprove each finding using callers, tests, documented intent, and the upstream contract. Distinguish a reproducible defect from a maintenance recommendation or an unresolved question. Missing evidence is not itself a defect.

## Gather proportionate proof

Use source evidence for ownership and API-design conclusions. For a behavioural claim, use the smallest decisive test or real interaction that exercises the concern; do not treat snapshots, test counts, or green CI as proof of everything.

When implementation is authorized, update affected consumers and verify the change using the project's verification workflow. Use available `verify`/`verify-ui` skills when applicable, or the host's equivalent tools. Cover the changed contract: native/slot prop forwarding, state transitions, keyboard/focus, disabled behaviour, or responsive rendering as relevant. A layout claim needs a browser screenshot or snapshot and an overflow measurement at supported narrow sizes. Inspect settled styles after transitions before diagnosing a screenshot difference.

A review can finish with construction assessed and interaction or visual fidelity explicitly unverified. Do not boot an unrelated stack or claim Figma fidelity to fill a report. Missing docs or browser access limits the affected conclusions; report what remains supported.

## Report the decision

Lead with the verdict and the component's role. Scale detail to the request; skip empty categories.

1. **Findings:** ordered by impact. Each gives a source location, concrete scenario or maintenance consequence, basis (project rule / upstream contract / recommendation), evidence, and the smallest fix. Mark inference explicitly. Reserve must-fix language for demonstrated defects or required contracts, not stylistic preferences.
2. **What stays:** name the sound design choices and why. Include a rejected alternative when it explains an important tradeoff.
3. **Where I looked:** a compact source-to-decision table with exact paths/links and the reviewed revision. List only sources actually read; do not dump every import.
4. **Verification and limits:** what was run and observed, what was inspected only, and what remains unknown. State whether the visual reference was checked.

Do not invent findings to justify the review. A clear "keep this design" with evidence is a complete outcome. The report remains local unless publication was authorized.
