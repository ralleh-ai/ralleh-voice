# Ralleh Voice Control Room — UX / IA Spec (unbranded)

## Purpose

This document defines the information architecture, content hierarchy, layout behavior, and semantic structure for the Ralleh Voice Control Room before branding.

The goal is to avoid generic AI-dashboard clutter and create a clean, premium, self-hosted agent voice cockpit focused on:

1. who the user is talking to
2. what is happening right now
3. what the user can do next
4. what was said and replied
5. where to inspect or tune the system if needed

Branding, visual identity, illustration, and color exploration happen later. This spec is structure-first.

---

## Design principles

- Clean, calm, premium, trustworthy
- Structure first, branding later
- One dominant primary area: the live conversation
- Secondary controls must support the conversation, not compete with it
- Diagnostics must be available without overwhelming the main flow
- Use semantic HTML5, not div soup
- Control text width with truncation, wrapping, and scroll containers deliberately
- Do not expose fake controls for features that do not exist
- Keep spacing rhythm consistent and tokenized

---

## The five questions the UI must answer immediately

Within 3 seconds, the user should understand:

1. **Who am I talking to?**
2. **Who is speaking right now?**
3. **What can I do next?**
4. **What mode is this session in?**
5. **Is the system healthy/connected?**

If any layout does not answer those five quickly, it is wrong.

---

## Core layout

### Desktop

Use a 3-panel layout.

- **Left rail**: session setup and identity
- **Center stage**: live conversation
- **Right rail**: diagnostics and tuning

### Mobile

Do not compress the desktop layout.

Use a stacked mobile order:

1. header/status strip
2. center stage
3. primary controls
4. live captions / transcript
5. bottom-sheet or tabbed controls for setup / tune / debug

---

## Content hierarchy

### Tier 1 — must dominate

Center stage only:
- active state (listening / thinking / speaking / reconnecting)
- who the current agent is
- primary actions (start, stop, cancel)
- live caption / transcript
- latest reply

### Tier 2 — secondary, but always accessible

Left rail:
- agent
- voice
- conversation mode
- performance mode
- barge-in
- session/auth

### Tier 3 — tertiary / operator-level

Right rail:
- latency
- system status
- debug events
- advanced tuning

---

## Panel definitions

## 1. Header strip

### Purpose
Show global app/session state without stealing focus.

### Required content
- product name: `Ralleh Voice Control Room`
- environment badge (`dev`, `staging`, `prod`)
- connection badge (`connected`, `reconnecting`, `offline`)
- auth badge (`off`, `shared-secret`, `signed-token`)
- short session id
- optional current agent chip

### Rules
- compact horizontal strip
- single-line metadata
- all long values truncate with ellipsis
- no multi-row clutter

---

## 2. Left rail — Session Setup

### Purpose
Configure who/what/how for the current conversation.

### Sections

#### A. Agent
- agent name
- short role subtitle
- agent selector
- optional tools/capabilities summary

#### B. Voice
- voice profile selector
- voice preview action (only if supported honestly)
- style summary

#### C. Mode
- conversation mode selector (`command`, `balanced`, `companion`, `debug`)
- performance mode selector (`eco`, `balanced`, `low-latency`)

#### D. Barge-in
- preset or slider
- helper text
- advanced controls hidden behind disclosure

#### E. Session / Auth
- connect/disconnect
- reconnect toggle
- auth/token setup hidden in advanced area
- processing mode (`buffered`, `streaming`)

### Rules
- keep this rail calm and scannable
- no huge cards
- consistent card structure
- helper text must be short
- use truncation on one-line metadata
- no debug data here

---

## 3. Center stage — Live Conversation

### Purpose
This is the hero and must answer the user’s live question: what is happening right now?

### Sections

#### A. Speaking status hero
- large status orb or equivalent focal element
- state label (`Listening`, `Thinking`, `Speaking`, `Reconnecting`)
- secondary sentence explaining current state

#### B. Agent identity block
- explicit statement: `You are talking to Carmack`
- role subtitle
- voice profile summary

#### C. Primary actions
- Start mic
- Stop mic
- Cancel / barge-in
- optional reconnect or repeat reply

#### D. Live captions
- current partial transcript
- transition to final transcript once turn closes

#### E. Conversation timeline
- chronological cards
- `You said`
- `Agent replied`
- `System note`

### Rules
- the center stage must dominate visually
- no more than one or two hero concepts competing at once
- the user should never wonder where to look first
- timeline must be readable, not log-like
- use generous line-height
- allow transcript/reply text to wrap normally

---

## 4. Right rail — Diagnostics / Tuning

### Purpose
Show system confidence and advanced inspection without distracting from the conversation.

### Sections

#### A. Latency
Use metric cards or a definition list for:
- mic → STT
- STT → agent
- agent → TTS
- total turn time

#### B. System status
- auth mode
- rate limiter backend
- bridge status
- adapter readiness
- processing mode

#### C. Debug stream
- protocol events
- recent errors
- reconnect notes

#### D. Advanced variables
- chunk size
- streaming settings
- barge-in sensitivity details
- debug toggles

### Rules
- this rail should feel secondary
- collapsible sections are allowed
- event stream must live in its own scroll container
- no panel should expand the page height uncontrollably
- metrics use compact typography and stable widths

---

## Semantic HTML requirements

Use semantic elements wherever possible:

- `header`
- `main`
- `aside`
- `section`
- `article`
- `nav`
- `footer`
- `details` / `summary`
- `ul` / `li`
- `dl` / `dt` / `dd`
- `button`, `label`, `input`, `select`

Avoid generic wrappers when a semantic element fits.

### Suggested structure

```html
<header>
  ...status strip...
</header>

<main>
  <aside aria-label="Session setup">
    <section>Agent</section>
    <section>Voice</section>
    <section>Mode</section>
    <section>Barge-in</section>
    <section>Session</section>
  </aside>

  <section aria-label="Live conversation">
    <section>Speaking status</section>
    <section>Primary controls</section>
    <section>Live captions</section>
    <section>Conversation timeline</section>
  </section>

  <aside aria-label="Diagnostics and tuning">
    <section>Latency</section>
    <section>System</section>
    <section>Debug</section>
    <section>Advanced variables</section>
  </aside>
</main>
```

---

## Typography rules

Use a restrained type scale.

- App title: 24–28px
- Section headings: 16–18px
- Card/body text: 14–15px
- Timeline text: 15–16px
- Labels/metadata: 12–13px
- Debug monospace: 12–13px

### Line-height
- labels: 1.2–1.3
- body: 1.45–1.6
- transcript/reply text: 1.5–1.6

Avoid tiny text except for low-priority metadata.

---

## Spacing rules

Use only a tokenized spacing scale.

Suggested spacing rhythm:
- 4
- 8
- 12
- 16
- 20
- 24
- 32

### Rules
- section-to-section spacing > intra-section spacing
- card padding must be consistent
- controls in a group are tightly spaced
- rails align to the same rhythm
- avoid arbitrary margin values

---

## Overflow and truncation rules

### Must truncate
Single-line metadata should truncate with ellipsis:
- session id
- environment/auth badges
- agent subtitle
- tool chips row if needed
- small status values
- long bridge/backend labels

### Must wrap
Multi-line content should wrap normally:
- transcript text
- reply text
- helper copy
- system note cards

### Must scroll
Constrained scroll regions:
- debug/protocol event stream
- long diagnostics blocks
- transcript/timeline when necessary in limited-height panels

### Must never break layout
- long auth/debug strings
- long session keys
- oversized error messages
- event payloads

---

## Interaction rules

### Default emphasis
- center stage is primary
- setup rail is stable and predictable
- diagnostics are available but visually quieter

### Default open/closed suggestions
- diagnostics sections can be partially collapsed
- auth advanced settings collapsed by default
- debug stream collapsed or lower on mobile

### No fake controls
If a feature is not implemented, either:
- omit it, or
- show it disabled with clear future-ready wording

Do not imply real playback controls if output audio playback is not implemented.

---

## Motion / live-update contract

This product is a voice control room, so the UI must make change over time obvious.

The interface should clearly communicate:
- what is currently active
- what just changed
- what is still in progress
- what completed
- what failed

### Motion principles

- Motion must communicate state, not decorate empty space
- Prefer subtle transitions over flashy looping animation
- Only the most important live surface should move prominently at any given moment
- Persistent motion should be limited to genuinely live systems (meter, active-state pulse, reconnect countdown if shown)
- Use `prefers-reduced-motion` and reduce non-essential animation

### What should visibly update in the 3-panel layout

#### Header strip
- connection badge changes immediately on connect/reconnect/disconnect
- auth badge updates on `session.ready`
- short session id updates when continuity changes
- environment/transport metadata remains stable unless configuration changes

#### Left rail
- selected values update instantly as the operator changes them
- helper copy can update when a preset changes (for example chunk profile or barge-in preset)
- advanced/future controls stay visibly disabled if not wired
- this rail should not pulse, shimmer, or compete with the live stage

#### Center stage
- speaking/listening status hero is the primary live indicator
- state orb/hero animates subtly on state change
- live caption updates as partial transcript / timeline state changes
- transcript timeline appends new entries in chronological order
- newest entry auto-scrolls into view when the operator is already near the bottom
- start/stop/cancel control affordances change immediately with session state
- microphone meter animates continuously only while capture is active

#### Right rail
- latency and throughput counters update as turn milestones arrive
- reconnect attempts and continuity metadata update on transport changes
- debug stream appends new protocol events in real time
- advanced variables update when the underlying values change
- this rail should feel operational, not theatrical

### Motion implementation guidance

- state transitions: 120–220ms
- panel expand/collapse: 160–220ms
- numeric/status transitions: subtle fade or count change only when meaningful
- waveform/meter: real-time while recording; frozen or reset when idle
- avoid skeleton screens when real empty-state copy is clearer

### Reduced motion

When `prefers-reduced-motion` is enabled:
- remove non-essential pulsing
- keep color/state swaps instant or near-instant
- preserve functional updates (text, counters, timeline entries, meters where necessary)

---

## Visual tone (pre-branding)

- dark neutral base acceptable
- calm contrast
- premium spacing
- restrained use of accent color
- no neon/gamer style
- no decorative blobs or gimmicks
- no consumer-chat toy vibe

The UI should feel like a self-hosted AI operations cockpit.

---

## Anti-slop rules

Reject designs that:
- look like a random dashboard with equally weighted cards
- require the user to hunt for the main action
- over-explain every section with long paragraphs
- use too many card variants
- use inconsistent padding or font sizing
- expose raw logs as the primary visual element
- bury the active state under setup controls
- feel like a developer harness instead of a product

---

## Success criteria

A user opening the screen should immediately know:
- I am talking to **this agent**
- The system is currently **listening / thinking / speaking**
- I can **start / stop / cancel** right here
- My words and the agent’s replies live **here**
- If something is wrong, diagnostics live **there**

If those are not obvious, the layout is not done.
