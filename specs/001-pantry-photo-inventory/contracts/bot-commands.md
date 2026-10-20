# Contract: bot messages and commands

All owner-facing text is Hebrew. `<item>` is any item name or alias after normalisation (final letters
folded, niqqud and punctuation removed, English lowercased). `<n>` is a non-negative integer. `<loc>` is
מקרר|fridge, מקפיא|freezer, מזווה|pantry.

## Photo

| Input | Effect | Reply |
|-------|--------|-------|
| photo, caption `<loc>` or none | detect, fallback on uncertain crops, merge into the session (highest count), upsert seen items | `במקרר:` then one line per item `ביצים ×6`, uncertain lines end with ` ?` and carry buttons |
| photo with no food found | nothing stored | `לא מצאתי מוצרים בתמונה.` |
| photo too dark or blurry (mean luminance or Laplacian variance below config) | nothing stored | `התמונה לא ברורה, אפשר לצלם שוב?` |
| fallback skipped (budget or error) for k items | items kept uncertain | extra line `k פריטים לא נבדקו שוב.` |

Every photo reply ends with the correction hint `לתיקון שלחו למשל "ביצים 4", "אין חלב" או "להוסיף חומוס", או לחצו ✓/✗.` and `כשסיימתם לצלם את כל ה<loc>, שלחו "סיימתי".`

Uncertain line buttons: `✓` (callback `confirm:<snapshot>:<key>`) and `✗` (callback
`remove:<snapshot>:<key>`).

## Corrections (FR-007)

| Pattern | Kind | Effect |
|---------|------|--------|
| `<item> <n>` or `<n> <item>` | count | set count to n |
| `אין <item>`, `no <item>` | false (if detected) or count | set count to 0 |
| `להוסיף <item> [<n>]`, `add <item> [<n>]` | missed | add, default n = 1 |
| callback `confirm:…` | confirm | clear uncertain |
| callback `remove:…` | false | set count to 0 |
| `סיימתי`, `done` | close | close the open session as full; unseen items of that location go to 0; reply lists them, or "שום דבר לא נגמר" |

A message may hold several corrections, one per line or separated by commas; each is applied, unreadable
lines are listed as `לא הבנתי: "<line>"`, and all unknown names share one yes/no question.

Reply: `עודכן: ביצים ×4`. Unknown `<item>`: `לא מכיר "<item>". להוסיף כסוג מוצר חדש?` with buttons
`כן` / `לא`; `כן` creates the item type and applies the correction.

## Queries (FR-006)

| Pattern | Reply |
|---------|-------|
| `מה יש לי` / `מה יש` | all locations with count > 0, grouped |
| `מה יש לי ב<loc>` / `מה יש ב<loc>` | that location |
| `יש <item>?` / `יש <item>` | `כן, ביצים ×4 במקרר` or `אין ביצים` |

Anything else: `לא הבנתי. אפשר לשלוח תמונה, לתקן ("ביצים 4", "אין חלב") או לשאול "מה יש לי?"`.

## Morning message (FR-010)

- Run-out found: `בוקר טוב. נגמרו מאתמול:` then one line per item with its location.
- Nothing ran out: `בוקר טוב, הכול בסדר.`
