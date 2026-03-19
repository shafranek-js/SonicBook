**Phase 2 UX/UI Implementation Brief**

### 1. Objective
Phase 2 improves the product from a good utility UI into a polished desktop audiobook application. The focus is not new platform capability, but consistency, hierarchy, perceived quality, and better day-to-day usability.

The main principle for this phase:
- Prioritize high-impact, low-risk UX improvements first.
- Defer expensive or speculative visual features until the core interface is fully coherent.
- Do not introduce UI polish that makes the app slower, noisier, or harder to maintain.

### 2. Product Goal
Make the entire application feel as refined as the current player area.

Today, the player already feels premium, while some utility surfaces still feel functional rather than finished. Phase 2 closes that gap.

### 3. Success Criteria
This phase is successful if:
- The top area, library, and chapter panel feel visually consistent with the player.
- Users can scan large libraries faster and understand current state with less effort.
- Loading and hover states feel intentional rather than default.
- No added interaction noticeably reduces rendering or scrolling performance.
- The app remains compact, desktop-first, and visually calm.

### 4. Priorities

#### P1: Ship First
These items are high-value and low-risk. They should define Phase 2A.

- Top panel simplification.
The URL input and save-path area should become less visually dominant when the user is in playback or browsing mode.

- Visual consistency system.
Establish and apply one radius scale, one shadow scale, one spacing scale, and one hover-state language across the app.

- Monospaced time displays.
All playback and chapter time values should use monospaced numerals to prevent visual jumping.

- Gradient scroll masks.
Library and chapter panels should gain subtle top/bottom fade masks so long lists feel softer and more premium.

- Skeleton loading states.
Replace generic empty/loading states in library and chapter lists with compact skeleton layouts.

- Contextual hover actions.
Library items should reveal quick actions on hover, but only the most important ones. Start with `Play` and one secondary action at most.

#### P2: Ship After P1 Is Stable
These items are useful, but require more design discipline or supporting logic.

- Dynamic library grouping.
Add lightweight groupings such as `Now Listening`, `Completed`, and `Unfinished` if the grouping logic can remain simple and predictable.

- Context-aware top tools behavior.
The top functional area may collapse, compress, or visually recede when the user is actively playing from the library.

- Improved drag-and-drop affordance.
When dragging a file into the app, show a clear overlay or frame state that confirms the drop target without visually overwhelming the UI.

- Stronger list hierarchy.
Refine metadata display, spacing, and row emphasis in library and chapter panels so primary information is easier to scan.

#### P3: Explore, Do Not Commit Upfront
These are optional, high-cost, or uncertain-value ideas. They should only be implemented if earlier phases are complete and performance remains strong.

- Interactive waveform in the player timeline.
This is visually attractive, but not automatically high-value for audiobooks. It should only ship if it improves navigation without making seek behavior noisier or heavier.

- Advanced hover action sets.
Do not add multiple hover buttons unless the list remains calm and readable.

- Additional decorative depth effects.
Any extra glass, blur, glow, or motion should be treated as optional polish, not core scope.

### 5. In-Scope Deliverables

#### 5.1 Layout and Information Architecture
- Refine the top functional area so it supports the flow without dominating the screen.
- Improve library scanning for large collections.
- Reduce repeated low-value text where possible.
- Keep the center panel as the primary visual anchor.

#### 5.2 Visual System
- Standardize corner radii across cards, controls, inputs, pills, and overlays.
- Standardize shadows and border treatment.
- Standardize hover, active, and selected states.
- Standardize spacing between controls, sections, and panel edges.
- Use monospaced numerals for all time-related values.

#### 5.3 Interaction Design
- Add skeleton states for loading surfaces.
- Add restrained contextual hover actions.
- Improve drag-and-drop feedback.
- Preserve current click targets and keyboard usability.

#### 5.4 Player
- Maintain the player as the visual quality benchmark.
- Strengthen audiobook-first controls such as skip backward and skip forward.
- Only replace the current progress bar with a waveform if the result is clearly better in usability and performance.

### 6. Out of Scope
- New media formats.
- Cloud sync.
- Social or sharing systems.
- Major backend rearchitecture.
- A full redesign of the app layout.
- Light theme expansion.
- Any feature that requires disproportionate engineering cost for marginal UX gain.

### 7. UX Rules
These rules should guide implementation.

- Calm over flashy.
The app should feel premium through restraint, not ornament.

- One visual language.
New controls must inherit the same spacing, radius, border, and interaction patterns as existing polished player controls.

- Dense but breathable.
The app should remain compact, but never cramped.

- Utility first.
Every visual upgrade must help scanning, clarity, or confidence.

- Performance is a feature.
Do not add effects that degrade list scrolling, playback responsiveness, or startup time.

### 8. Technical Constraints
- Favor CSS-first solutions where possible.
- Avoid heavy animation libraries for small UX polish tasks.
- Treat list performance as critical.
- If waveform rendering is explored, validate memory and CPU cost before productizing it.
- Any new UI state should degrade gracefully when metadata is missing.

### 9. Delivery Plan

#### Phase 2A
- Top panel simplification
- Visual consistency system
- Monospaced timecodes
- Gradient scroll masks
- Skeleton states
- Minimal hover actions

#### Phase 2B
- Dynamic grouping
- Context-aware top tools behavior
- Better drag-and-drop feedback
- Stronger list hierarchy polish

#### Phase 2C
- Waveform prototype
- Optional advanced polish if justified by performance and UX outcome

### 10. Acceptance Criteria
A feature in this phase is done only if:
- It is visually consistent with the rest of the app.
- It improves clarity or speed of use.
- It does not create visual clutter.
- It does not introduce obvious performance regressions.
- It works cleanly in the desktop layout and remains acceptable on narrower widths.

### 11. Primary Risks
- Too many "nice ideas" shipping at once and diluting focus.
- Over-designed hover actions making lists noisy.
- Waveform work consuming large effort for low audiobook value.
- Visual polish being added inconsistently across surfaces.

### 12. Final Recommendation
Ship P1 first and treat it as the real Phase 2.

Do not start waveform work until the top area, library, chapter panel, loading states, and hover interactions are already coherent.
