# Analysis feedback

Approved scope: independently confirm or challenge an analysis finding without changing existing sample reviews.

- Separate SQLite table keyed by sample and exact analysis digest; revision conflicts return 409.
- Four statuses: unreviewed, agree, disagree, needs_check; editable note and explicit save.
- Filter by saved status; agree/disagree count as complete, needs_check remains pending.
- Per-sample drafts survive sample/filter/tab navigation, with unload warning.
- Existing JSON export and SQLite backup include analysis feedback.
- Verify persistence, conflicts, isolation, browser navigation and old review preservation using a disposable database.
