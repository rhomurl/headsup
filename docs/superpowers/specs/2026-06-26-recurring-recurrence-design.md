# Recurring Recurrence Design

## Goal

Fix the recurring reminder flow so weekly reminders always choose a specific
weekday, and add both bi-weekly weekday-based reminders and fixed 14-day
interval reminders.

## Scope

- Change the recurring frequency picker so weekly scheduling is explicitly
  weekday-based.
- Add an every-other-week option that also requires a weekday selection.
- Add an every-14-days interval option anchored from the first scheduled fire.
- Update recurrence labels shown in prompts, confirmations, reminder lists, and
  fired reminder cards.
- Extend recurrence calculation tests, including restart recovery behavior.

## Approach Options

### Recommended

Model calendar-based and interval-based recurrence separately:

- `weekly:<weekday>` for weekly reminders on a chosen weekday
- `biweekly:<weekday>` for every-other-week reminders on a chosen weekday
- `every:14d` for fixed 14-day interval reminders

Trade-offs:

- Matches user expectations for "every week" versus "every 14 days".
- Preserves existing `every:<duration>` support for interval reminders.
- Requires one additional recurrence branch in parse and scheduling helpers.

### Alternative 1

Keep all weekly-style reminders as `every:<duration>` intervals and only update
the labels.

Trade-offs:

- Smaller change set.
- Does not solve the current UX bug because "every week" still would not be a
  weekday-based schedule.

### Alternative 2

Insert a new step that asks users to choose between calendar scheduling and
interval scheduling before showing frequencies.

Trade-offs:

- Explicit mental model.
- Adds friction to a flow that can stay clear with better button mapping and
  labels.

## Chosen Design

### Recurrence Model

Persist the following recurrence strings:

- `daily`
- `weekly:<weekday>`
- `biweekly:<weekday>`
- `every:<duration>`
- `monthly:<day>`

No data migration is needed because existing reminders already use supported
forms. The change only affects newly created reminders and the interpretation of
the new `biweekly:<weekday>` form.

### UI Flow

Update the recurring frequency keyboard in `headsup/handlers/reminders.py`:

- `Every day` keeps the existing behavior.
- `Every week` routes to weekday selection and stores `weekly:<weekday>`.
- `Every other week` routes to weekday selection and stores
  `biweekly:<weekday>`.
- `Every 3 days` remains an interval option.
- `Every 14 days` becomes a new interval option storing `every:14d`.
- `Monthly` keeps the existing day-of-month flow.

The existing weekday button layout can be reused for both weekly and bi-weekly
calendar schedules. The frequency prompt and time prompt must never show raw
values such as `7d` or `14d` when a user selected a calendar-based schedule.

### Labeling

Use natural-language labels throughout the flow:

- `every Monday`
- `every other Tuesday`
- `every 3 days`
- `every 14 days`
- `monthly on the 15th`

This applies to:

- the time-selection prompt
- the final creation confirmation
- the `/list` view
- fired recurring reminder text

### Scheduling Semantics

Calendar schedules and interval schedules intentionally behave differently:

- `weekly:<weekday>` always advances by 7 days at the same local wall-clock
  time.
- `biweekly:<weekday>` always advances by 14 days at the same local
  wall-clock time.
- `every:14d` advances by a strict 14-day duration from the previously
  scheduled fire time.

When creating the first occurrence:

- `weekly:<weekday>` schedules the next matching weekday at the chosen time,
  skipping to the following week if the current day/time has already passed.
- `biweekly:<weekday>` uses the same first-fire calculation as weekly because
  the two-week cadence begins once the first scheduled occurrence is chosen.
- `every:14d` schedules today at the chosen time if still in the future,
  otherwise tomorrow at that time, and subsequent occurrences repeat every 14
  days from that first fire.

When restoring after downtime:

- `weekly:<weekday>` should recover to the next intended weekday occurrence
  after the current time.
- `biweekly:<weekday>` should recover to the next intended two-week occurrence
  after the current time while preserving weekday and local time.
- `every:14d` should continue stepping in 14-day increments until the next
  occurrence after the current time.

### Code Areas

- `headsup/handlers/reminders.py`
  Update frequency button callbacks, add weekday-routing support for bi-weekly
  selection, and update user-facing frequency labels.
- `headsup/parse.py`
  Add `biweekly:<weekday>` support to `next_recurring()`,
  `next_recurring_after()`, and `format_recurrence()`.
- `tests/test_parse.py`
  Add recurrence unit tests for weekly, bi-weekly, and 14-day interval
  formatting and stepping.
- `tests/test_scheduler.py`
  Add restart-recovery tests proving weekly and bi-weekly preserve intended
  local schedule after missed fires.

### Error Handling

- Unknown recurrence strings should continue returning `None` from parse helpers
  rather than guessing.
- Existing reminders with supported recurrence strings remain untouched.
- Weekday-based labels should be generated from known weekday tokens only; if a
  token is invalid, fall back to a generic label instead of raising.

## Testing

- Extend unit coverage for `next_recurring()`:
  - `weekly:mon` advances 7 days
  - `biweekly:mon` advances 14 days
  - `every:14d` advances 14 days
- Extend recovery coverage for `next_recurring_after()`:
  - overdue weekly reminders recover to the next intended weekday
  - overdue bi-weekly reminders recover to the next intended bi-weekly weekday
  - overdue `every:14d` reminders recover by repeated 14-day interval stepping
- Add focused handler tests if the project already has a stable pattern for
  callback-driven conversation tests; otherwise keep coverage concentrated in
  parse and scheduler logic and manually verify the Telegram UI flow.
