---
name: visually
description: >
  Use when explaining to the user how something works or how it fits together
  — a system, a piece of code, a set of research findings, an option space
  being brainstormed, an unfamiliar concept, or the reasoning behind a
  conclusion — or when the user asks for something "narrative",
  "human-readable", or "in plain terms". Produces plain language and ASCII
  diagrams instead of prose walls. Not for questions asked of the user,
  explanations of a decision already made, clarification requests, or
  tool/status output.
argument-hint: "[what to explain — omit to redo the previous answer]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/diagrams.py" *)
---

# Explain visually

Explain with plain language and diagrams. Follow the routing graph, then read
only the selected mode reference. DOT graphs are instructions for choosing an
answer format; they are not the diagrams to show the user.

## Choose a mode

```dot
digraph choose_mode {
    start [label="Prepare the final answer", shape=ellipse];
    excluded [label="Question, clarification, tool/status report,\nor explanation of an action you took?", shape=diamond];
    applies [label="Flow, hierarchy, comparison, cause-and-effect,\nmore than three explanatory sentences,\nor an explicit request to use this skill?", shape=diamond];
    format [label="Honor the user's requested format.\nChoose a mode for anything left unspecified.", shape=box];
    named [label="User explicitly named a mode or shape?", shape=diamond];
    selected [label="Read every requested mode's reference:\n1 / 1A–1F: references/mode-1-structural.md\n2 / 2A–2C: references/mode-2-narrative.md\nboth modes: read both files", shape=box];
    both [label="Need both a technical mechanism\nand a version for non-specialists?", shape=diamond];
    mixed [label="Read both references; follow Using both modes", shape=box];
    plain [label="Reader outside the specialty, or request\nfor narrative, human-readable, or plain terms?", shape=diamond];
    narrative [label="Read references/mode-2-narrative.md", shape=box];
    structural [label="Read references/mode-1-structural.md", shape=box];
    normal [label="Answer normally", shape=box];

    start -> excluded;
    excluded -> normal [label="yes"];
    excluded -> applies [label="no"];
    applies -> normal [label="no"];
    applies -> format [label="yes"];
    format -> named;
    named -> selected [label="yes"];
    named -> both [label="no"];
    both -> mixed [label="yes"];
    both -> plain [label="no"];
    plain -> narrative [label="yes"];
    plain -> structural [label="no"];
}
```

The references are [Structural](references/mode-1-structural.md) and
[Narrative](references/mode-2-narrative.md). A request for plain terms alone
needs only Narrative; use both when the technical mechanism is also required.

With no argument, reissue your whole previous answer using this skill, keeping
its meaning and caveats. If it was only an excluded response, keep its normal
format. If there is no previous answer, ask what to explain.

## Shared rules

- The user's requested format overrides diagram and layout requirements,
  including those in the references. Follow the remaining content rules.
- Otherwise, draw relationships even in short answers. Restructure more than
  three explanatory prose sentences into a shape with brief supporting text.
- Open with one sentence of context, then show the relationship the user asked
  about. Ground claims in the available code, evidence, or stated scenario;
  distinguish inference from observation. Do not invent facts or branches.
- Explain unfamiliar domain terms inline with a dash or parentheses. Keep the
  term when useful, and skip definitions the reader already knows. Familiarity
  depends on the audience, not a fixed list of technical words.
- Keep unknown, assumed, and disputed points visible. Structural uses `(?)`,
  `(assumed)`, and `(disputed)`; Narrative states the uncertainty in words.
- End when the explanation is complete, without a summary that repeats it.
  These layout rules govern the final answer; required host progress messages
  can precede it.

## Using both modes

Show the mechanism first in a Structural shape, then its meaning for the reader
in a Narrative shape. Give each a short heading and choose their shapes
independently. Each part follows its mode's rules; avoid repeating details
that add nothing for the second audience.

## Rendering and examples

Read [diagram tooling](references/diagram-tooling.md) before drawing boxes or
columns. It covers [the renderer](scripts/diagrams.py), absolute paths,
validation limits, and the Python-unavailable fallback. Use the host's execution
and approval mechanism; Claude's `allowed-tools` metadata is not a permission
grant in another host.

[Worked examples](../../EXAMPLES.md) show every shape and both modes together.
Read the relevant example when a shape's compact pattern is not enough.
