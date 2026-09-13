# Explain visually: worked examples

These illustrative business scenarios show the two modes and all nine shapes.
The prompts supply the facts; the answers explain them without adding measured
results or claims about real companies. In Claude Code, prefix a prompt with
`/explain:visually`; in Codex, select `$explain:visually`.

Structural examples retain useful technical labels. Narrative examples explain
what happens in everyday language. You can request a shape explicitly or let
the skill choose one.

## 1A: Linear flow

**Prompt:** Show an article's publication flow. An author drafts it, an editor
reviews it, approved copy is scheduled, and the scheduler publishes it.

**Answer:** An article passes through editorial review before it reaches readers.

```text
Author drafts -> Editor reviews -(approved)-> Copy scheduled -> Scheduler publishes
```

## 1B: Branching list

**Prompt:** Show what TicketIntake does. It checks the sender, assigns a topic,
asks for a screenshot for display problems, and puts the ticket in the matching
team's queue. Use a branching list.

**Answer:** TicketIntake prepares each support request for the team that handles it.

```text
TicketIntake
  -> checks the sender
  -> assigns a topic
  -> if the problem concerns the display: requests a screenshot
  -> adds the ticket to the matching team's queue
```

## 1C: Cause-and-effect cascade

**Prompt:** Our warehouse printer stopped, so labels cannot print and
parcels cannot leave without them. Staff are moving unlabeled parcels into a holding area.
We do not yet know whether any delivery promises will be missed. Show the effects.

**Answer:** The printer outage blocks dispatch and creates temporary storage work.

```text
Printer stops
  -> labels cannot print
     -> parcels cannot leave
        -> delivery promises missed? (?)
     -> staff move unlabeled parcels to the holding area
```

## 1D: Nested hierarchy

**Prompt:** Show the structure of our inventory service. It contains stock
records and their locations. This is containment, not an execution sequence.

**Answer:** Stock records and locations belong to the inventory service.

```text
┌─────────────────────────┐
│ Inventory service       │
│                         │
│   ┌───────────────────┐ │
│   │ Stock records     │ │
│   │ Locations         │ │
│   └───────────────────┘ │
└─────────────────────────┘
```

## 1E: Comparison

**Prompt:** Compare manual and scheduled stock checks. Manual checks happen on
request and require staff to check each item. Scheduled checks run nightly and
staff review exceptions. We have not measured time per manual check or changes
missed between nightly runs.

**Answer:** The two approaches differ in timing and the work staff perform.

```text
                 Manual checks         Scheduled checks
                 ─────────────         ────────────────
When             On request            Every night
Staff effort     Check each item       Review exceptions
Main unknown     Time per check        Missed changes
```

## 1F: Decision flowchart

**Prompt:** Draw a flowchart: when an order arrives, check stock. If the item is
available, end with the order ready to dispatch. Otherwise, end with a backorder
queued. A backorder waits for stock to arrive.

**Answer:** Stock availability determines whether the order can proceed to dispatch.

```text
              ╭───────────────────╮
              │  Order received   │
              ╰───────────────────╯
                        │
                        ▼
              ┌───────────────────┐
              │    Check stock    │
              └───────────────────┘
                        │
                        ▼
                   .---------.
                  < In stock? >
                   '---------'
                        │
          ┌─────────────┴─────────────┐
          │                           │
         YES                         NO
          ▼                           ▼
╭───────────────────╮       ╭───────────────────╮
│ Ready to dispatch │       │ Backorder queued  │
╰───────────────────╯       ╰───────────────────╯
```

Backorder — an order waiting for stock to arrive.

## 2A: Branching tree

**Prompt:** Explain appointment availability to our reception team. We check the
requested time. If it is available, we reserve it and send confirmation. If it
is unavailable, we offer the next free time and wait for the visitor's choice.

**Answer:** We confirm an appointment only after finding a time the visitor can use.

```text
┌─ We check the requested time.
│
├─ If it is available, we reserve it.
│   └─ We send the visitor a confirmation.
│
└─ If it is unavailable, we offer the next free time.
    └─ We wait for the visitor to accept or choose another time.
```

## 2B: Consequence chain

**Prompt:** Explain the effect of a supplier delay to our operations team. The
parts will arrive Thursday instead of Tuesday. Assembly needs those parts and
can begin only when they arrive. We think Friday dispatch is still possible,
but have not checked assembly capacity. The next step is to check that capacity.

**Answer:** The late parts move the earliest assembly start to Thursday.

```text
  because      Assembly cannot begin until the parts arrive.
  which means  The team has less time before Friday dispatch.
  we think     Friday dispatch may still be possible.
  but          We have not checked how much assembly work fits into that time.

What we do next
  Check assembly capacity before confirming a dispatch date.
```

## 2C: Before and after

**Prompt:** Explain a proposal to send appointment reminders automatically.
Today staff call each visitor the day before and record replies in a shared
list. Under the proposal, the system sends the reminder, but staff keep the
same reply list. We do not know how many visitors will read the messages.

**Answer:** Automatic reminders would replace the calls while keeping reply handling the same.

```text
Today                                If we send reminders
─────                                ────────────────────

Staff call each visitor the day      The system sends a reminder the
before.                              day before.

Staff record replies in a shared     Staff still record replies in
list.                                that list.
```

**What would not change**

Staff would still record replies in the shared list.

**What we still do not know**

We have not measured how many visitors would read the messages.

## Both modes together

**Prompt:** Explain our article scheduler to developers and editors. It reads
approved drafts with a publication time, publishes them when that time arrives,
and returns failed publications to the editor's queue. Use a Structural branching list for developers and a Narrative
branching tree for editors.

**Answer:** The scheduler publishes approved articles at their assigned times.

### Mechanism

```text
Scheduler
  -> reads approved drafts with a publication time
  -> when that time arrives: attempts publication
  -> if publication fails: returns the draft to the editor's queue
```

### For editors

```text
┌─ The article waits until its publication time.
│
├─ If publication succeeds, readers can see it.
│
└─ If publication fails, it returns to your queue for attention.
```

## Redo the previous answer

**Previous answer:** An author drafts the article. An editor reviews it.
Approved copy is scheduled and then published.

**Prompt:** `/explain:visually` in Claude Code, or `$explain:visually` in Codex,
with no additional text.

**Answer:** Editorial review comes before scheduling and publication.

```text
Author drafts -> Editor reviews -(approved)-> Copy scheduled -> Article published
```

Without a previous answer, the skill asks what you want explained.
