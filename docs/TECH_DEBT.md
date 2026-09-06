# Technical debt register

## Addressed in this consolidation

| Debt | Resolution | Verification |
| --- | --- | --- |
| Arbitrary image proxies could forward credentials | Exact service origins, path checks for Jellyfin artwork, redirect revalidation, domain-scoped TPDb cookies, bounded raster downloads | Security tests |
| Refresh/sort/upload discarded selections | Owner-wide SQLite selections and search queue; in-place image updates | Unit and real-browser smoke tests |
| Partial success hid failed seasons or primary artwork | Independent target outcomes; only successful targets consumed from selections | Workflow tests, browser smoke |
| Retries searched for a different poster | Retry tasks snapshot failed target IDs and original URLs; unknown old selections require review | Workflow tests |
| Cancellation omitted an upload already performed | Persist each target outcome before checking cancellation again | Cancellation/resume tests |
| Jobs vanished after restart | Durable checkpoints; interrupted jobs wait for explicit resume | Recovery tests |
| Separate auto/manual/retry/legacy upload loops | One service and single worker; legacy routes are adapters | Workflow/API tests |
| Unlocked JSON read-modify-write state | SQLite transactions and idempotent legacy import; originals retained | Concurrent writes and migration tests |
| Wildcard imports exposed stale Selenium state | Module-qualified integration access; lazy startup through app factory | Health/API paths |
| Fuzzy automatic matches and mixed season sets | Exact candidate or explicit saved correction; missing set coverage requires review | Matching/service tests |
| Unbounded binding by default | Loopback default, origin/Host checks, one-process worker lock | API security tests |
| Cache setting also disabled corrected TPDb mapping | Corrections independent of disposable picker cache | API regression test |
| Claimed conversion only changed filename | Decode and convert downloaded artwork to JPEG | Image conversion test |
| Almost no regression safety net | Backend/frontend tests, browser smoke script, CI | See README commands |

## Remaining priorities

1. **Validate against live services before large batches.** Tests mock Jellyfin/TPDb. Jellyfin 12 auth/base64 compatibility changes were preserved, but this work did not upload to a real server. Start with one manually reviewed item, then a small automatic batch.
2. **Dependency maintenance.** Existing dependency pins are old and Pillow is unbounded. Audit advisories and update in a separate tested change; no claim is made that current versions are vulnerability-free. `webdriver-manager` appears unused by current Selenium startup.
3. **Scraper fixtures and decomposition.** `search_tpdb_for_poster_groups` remains a large, selector-dependent integration function. Add saved, sanitized HTML fixtures for real movie/series/set/specials/challenge pages before separating navigation from parsing. A dead ChromeDriver session still needs stronger recovery handling.
4. **Measure library-scale behavior.** Library loading is not paginated, the grid renders all items, and history/job queries currently read full local records. Benchmark representative library and batch sizes before choosing pagination or retention policies. No performance improvement percentage has been measured.
5. **Long-lived storage maintenance.** Expired picker entries stop being served but remain until cache cleanup. Diagnostic logs and durable jobs/outcomes do not yet have automatic rotation/retention. Interrupted temporary files can remain after an abrupt process kill.
6. **Browser-state cleanup.** `static/js/app.js` still has substantial picker/manual-review state and some now-unused legacy progress helpers. Most upload orchestration moved to `jobs.js`; further splitting should be driven by browser regression coverage, not file size alone. Other tabs reconcile selections through queue changes or page reload rather than a dedicated live synchronization channel.
7. **Recovery limits.** There is no distributed transaction with Jellyfin. A crash between a successful external upload and its SQLite checkpoint can cause that target to be attempted again after explicit resume. Cancellation does not undo artwork. No poster-backup/rollback feature was added.

## Intentionally out of scope

- Framework migration, new infrastructure, multi-user authentication, or public hosting.
- Automatic continuation of interrupted uploads.
- Deleting original migration files or blindly treating incomplete legacy history as success.
- Removing legacy endpoints without knowing their external consumers.
