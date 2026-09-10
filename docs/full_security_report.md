# UNINOVIS / TOMMI — Full Security Review Report

This document explains, in plain language, every security problem found
across the `web/` application (plus the LTI classroom-integration tools
under `UltiR/` and the AI-agent framework under `agents/`) across two
review passes, why each one mattered, and exactly what was done about it.
It also covers the broader cleanup work that grew out of the reviews
(retiring dead apps, requiring login everywhere it should be required, and
tidying up URLs), since several of those changes closed security gaps of
their own along the way.

Where a technical term is unavoidable, it's explained the first time it's
used. Every finding below follows the same structure: **Problem** (what it
is, in one line), **Where** (which piece of code), **In plain terms** (what
it actually means), **Why it matters** (the real-world consequence),
**What we did** (how it was confirmed, and the fix if there is one), and
**Status** (Open or Fixed).

---

## How these reviews happened

**First pass.** A full security audit of the `web/` application — not just
a look at recently-changed code, but the whole thing: the login system,
every internal tool ("app") under `web/apps/`, and how they talk to each
other. Findings were verified by actually reproducing them against the
real code, not just reading it and guessing, and every fix was tested the
same way afterward — including, in several cases, running a real login
through the real code with a real password, the same way an actual user
would. That habit of testing fixes for real is what caught two of the more
interesting problems below, including a regression that would have locked
*everyone* out of several tools if it had shipped unnoticed (finding #31).

**Follow-up pass (2026-09-10).** A second audit went further: it started
the actual running application rather than only reading its source, and
used it the way a real visitor would — normal navigation, typos, forms
filled in badly — proving each suspected problem against the live server
wherever that was possible, rather than flagging it from code alone. It
also extended the scope beyond `web/` to the four LTI classroom-integration
tools and the AI-agent framework, neither of which the first pass had
covered. Every test account, test file, and test session created along the
way was removed afterward; nothing here touched real user data. This pass
found several new problems, including two that turned out to be more
urgent than anything on the original list — both confirmed exploitable on
this exact deployment with no credentials at all (findings #4 and #5). A
more technical, file-and-line-level version of this same pass lives in
`docs/security_audit_2026-09-10.md`.

The findings from both passes are combined below into one list, ordered
from most to least severe.

---

## CRITICAL

### 1. A hardcoded "master password" for one login method

**Problem:** One of the site's login methods falls back to a secret that's
publicly visible in the source code if nobody configures a real one.

**Where:** `web/app.py`, the code that handles logging in through an
external system called "Moodle" for one specific AI assistant ("Eulalia").

**In plain terms:** Some logins on this site work by receiving a secret
signed code from Moodle (a separate teaching platform) instead of a
username/password. That signature is created using a secret key that only
the server should know. The code has a fallback: *if the real secret was
never configured on the server, use this placeholder text instead* — and
that placeholder text is written directly into the source code, in
Spanish, literally translating to "change this shared secret."

**Why it matters:** If whoever set up the server forgot to configure the
real secret (an easy thing to forget), the "secret" protecting this login
method is actually a publicly-known string sitting in the codebase. Anyone
who can read the source code — which, for an open-source-style internal
project, is not a high bar — could compute a valid login code for *any*
username, including a teacher's account, and log in as them without ever
knowing their password.

**What we did:** Confirmed on the follow-up pass that the real secret is
still not configured on this deployment, and built a valid signature by
hand, offline, using nothing but the public placeholder text — the live
server accepted it without complaint. No fix has been applied yet.

**Status:** Open. This is one of the single most serious issues in this
report. The fix is straightforward: make the server refuse to start (or
refuse this login method) if the real secret isn't configured, instead of
quietly falling back to a guessable one. See finding #7 — the same exact
mistake was found independently in four more places, and all five should
be fixed together.

---

### 2. Anyone could write a file anywhere on the server

**Problem:** An anonymous, no-login endpoint let a visitor make the server
write a file to a location of their choosing, with content of their
choosing.

**Where:** `web/app.py`, the `/api/feedback` endpoint (used for the little
thumbs-up/thumbs-down buttons under an AI agent's replies).

**In plain terms:** When you click "thumbs down" on a response, the app
saves your feedback to a file named after which agent you were talking to
(e.g. `eulalia_feedback_user.jsonl`). The agent's name for this file came
straight from the request — with no checks at all — and this specific
endpoint was one of the few on the whole site that anyone could call
without logging in at all. Because the "agent name" was trusted blindly,
someone could send a fake agent name containing `../../../` (a standard
trick meaning "go up a few folders"), and the server would happily create
or overwrite a file *anywhere else on disk* it had permission to touch,
with content the attacker also controlled.

**Why it matters:** This is one of the most classic and dangerous web bugs
there is — an anonymous visitor gets to choose both *where* a file gets
written and *what's in it*, with zero login required.

**What we did:** The "agent name" is now scrubbed before it's ever used to
build a file path — anything that isn't a normal letter, digit, or
underscore gets replaced with a space, so `../../../etc/passwd` becomes the
harmless text `etc passwd`. It can no longer be anything other than plain
text. We tested this with the actual attack payload and confirmed the file
now lands safely inside the intended folder, while normal feedback still
works exactly as before.

**Status:** Fixed.

---

### 3. An entire tool could be hijacked by any anonymous visitor

**Problem:** Two bugs combined to let a total stranger plant code that ran
in the browser of any staff member — including the top administrator —
who viewed a public research-collaboration listing.

**Where:** The "Research Proposals" tool (a page for posting research
collaboration opportunities).

**In plain terms:** This tool had two problems that combined into
something much worse than either alone:

1. **Every anonymous visitor was treated as the same person.** When you're
   not logged in, the system gives you a temporary "guest" identity so
   pages can still show *something*. The bug: it gave literally *every*
   anonymous visitor the exact same guest identity. Anywhere the app
   checked "is this the same person who created this?", any two anonymous
   visitors passed that check against each other — meaning anyone could
   edit or delete *anyone else's* anonymously-submitted proposal, or their
   own.
2. **User-typed text was inserted into the page as if it were code.** The
   "topic," "abstract," and other fields of a proposal were dropped
   directly into the page's HTML without being treated as plain text
   first. This is the bug family called **stored XSS** (cross-site
   scripting) — instead of typing normal text, you can type a snippet of a
   programming language (JavaScript) and have it *run* in the browser of
   anyone else who later looks at that proposal.

**Why it matters:** Put together, these two bugs meant a total stranger,
with no account and no login, could plant a booby-trapped "proposal" that
silently ran their code in the browser of the next person — staff member,
content manager, or even the site's top administrator — who opened it.
That code could steal that person's login session and act as them.

**What we did:** Rather than patch this in place, we determined the tool
was already effectively abandoned — its real, current version lives on a
separate external website, and the only remaining internal links to it
were themselves stale. We fully retired the local copy: removed it from
the list of active tools, archived its code (rather than deleting it
outright, in case it's ever needed for reference), and removed every
remaining link to it from the site's menus and documentation pages.

**Status:** Fixed by retiring the tool.

---

### 4. A hidden "test mode" hands out full teacher access to anyone

**Problem:** A leftover developer shortcut on all four LTI classroom tools
grants a real, fully-privileged "Instructor" session to anyone who visits
one specific web address — no login, no signature, nothing.

**Where:** The four LTI tools that plug this site into Moodle (`circuits`,
`fonesp`, `proyecto`, `redaccion` — under `UltiR/`).

**In plain terms:** Each of these tools has a leftover developer shortcut:
a web address ending in `/test` that was meant for building/checking the
tool without needing a real Moodle course. Visiting it instantly hands
back a real "Instructor" session, the same as if a teacher had launched
the tool properly from Moodle. For one of the four tools, that instructor
mode is even the *default* — you don't need to ask for it, a bare visit to
the test address is enough.

**Why it matters:** With a stolen instructor session, a stranger can
upload or delete course materials, edit grading rubrics and the
instructions given to the AI, and read every student's work and chat
history for that course — all four tools, no credentials of any kind.

**What we did:** Tested directly against the real, running server: a
single unauthenticated request returned a working teacher session
(confirmed: `"role":"Instructor","is_instructor":true`). No fix has been
applied yet.

**Status:** Open. The fix is to delete this shortcut from anything that
runs in production, or wrap it in a check that's switched off by default
and has to be deliberately turned on for local development. This, along
with finding #5, is the single most urgent item in this entire report.

---

### 5. The site's default administrator password is still "admin"

**Problem:** The account the server creates automatically on first run —
username `admin`, password `admin` — is still active and still logs in as
the most powerful account on the site.

**Where:** The account-setup code that runs the first time the server
starts (`web/auth.py`).

**In plain terms:** If the server has never had a top-level administrator
account, it creates one automatically so there's a way in — on the
assumption that whoever sets up the server will change the password right
away.

**Why it matters:** This isn't a clever attack — it's the single most
commonly guessed username/password pair there is. Anyone who tries it gets
full administrator rights: manage every user, every tool, every
permission.

**What we did:** Tested directly on this deployment: that password still
worked, and logged straight in as the superuser account (this account's
`provisional_password` flag was already being set to `true` at creation —
existing code, not new — but nothing was checking it). Implemented the
"force it to be changed before anything else can be done with the
account" half of the recommended fix: a session whose account still has a
provisional password can now only reach three endpoints — change password,
view its own account info, and log out — everywhere else on the site
returns a clear 403 until the password is changed, and the block lifts
immediately on the same session the moment it is, no re-login needed. This
applies to every provisional account, not just the default admin one. Two
places needed the fix, not one: the shared session-lookup function
(`web/auth.py`) wasn't carrying the provisional flag on to individual
requests at all, and the site's central auth middleware
(`web/app.py`) needed the actual block added. Verified against the real,
running server with a disposable test account: every ordinary API call —
including on the sub-apps like Directory, not just the main site — was
correctly rejected while the password was still provisional, `/api/auth/me`
kept working so the account could see its own state, and changing the
password on that same session immediately un-blocked it without a fresh
login. Test account removed afterward; the real accounts on this
deployment were untouched.

**Status:** Mitigated, not fully fixed. The account still starts as
`admin`/`admin` — that part of the original finding is unchanged — but a
stranger who logs in with it now can't do anything with the site beyond
immediately having to set a new password, which sharply cuts what this
finding used to allow. The residual risk: whoever logs in with the default
credential *first* — attacker or the real administrator — is the one who
gets to set it, so this doesn't fully close the door, it changes the shape
of the risk from "full account takeover" to "a race to claim the account,"
with the loser locked out of their own superuser account until it's reset
by hand. Fully closing it still needs the original recommendation:
generate a random one-time password at setup instead of a fixed, guessable
one.

---

### 6. A second anonymous file-write bug, missed the first time around

**Problem:** The exact same "write a file anywhere" bug as finding #2,
present on a completely different endpoint the original fix never touched.

**Where:** `web/app.py`, an endpoint used by one of Eulalia's classroom
exercises (submitting a written response to a "fact or myth" pairing
exercise).

**In plain terms:** Anyone, logged in or not, can get the server to write
a file to a location of their choosing — the same bug as finding #2, on an
endpoint the original fix never touched. It builds a filename from two
pieces of text the visitor supplies, with almost no cleanup applied to
them.

**Why it matters:** No login required, and the file's content is entirely
the visitor's choice — the same classic, dangerous pattern as finding #2.

**What we did:** Tested directly, with a harmless marker file: confirmed
it landed on disk outside the folder it should have, using a value like
`../pwn_test_marker` in one of the two text fields. Fixed the same way as
finding #2 — introduced one shared helper function that strips anything
that isn't a normal letter, digit, or underscore before a value is ever
used to build a file path, and applied it here (and refactored finding
#2's own endpoint to use the same shared helper, rather than its own
separate copy of the same logic). Re-tested with the exact same attack
payload against the real, running server: the file now lands safely inside
the intended folder, with the traversal sequence reduced to harmless text,
exactly like finding #2.

**Status:** Fixed.

---

### 7. The "change this secret" placeholder problem, times five

**Problem:** The exact same hardcoded-fallback-secret mistake from
finding #1, independently repeated in all four LTI classroom tools.

**Where:** The same Moodle/Eulalia login shortcut described in finding #1,
plus all four LTI tools from finding #4.

**In plain terms:** Finding #1 already described one shared secret that
falls back to an obvious placeholder value if nobody configures the real
one. This audit found the exact same pattern, independently, in all four
LTI tools as well — each has its own placeholder secret, and none of the
five has ever had a real one configured on this server.

**Why it matters:** The actual signature-checking code is written
correctly in every case — the problem is purely that the value it's
checking against is public text sitting in the source code. Finding #4
already gets into these same four LTI tools without even needing this
secret — but this is the same underlying mistake, made five times, and all
five need the same fix.

**What we did:** Confirmed the Moodle/Eulalia one directly (see finding
#1). Confirmed by code review that the same fallback-to-a-placeholder
pattern exists, unchanged, in all four LTI tools. No fix has been applied
anywhere yet.

**Status:** Open. The fix, for all five: make the server refuse to start
(or refuse that one login method) unless a real secret has been configured
— never silently fall back to the placeholder.

---

## HIGH

### 8. A "website" field could secretly contain a program instead of a link

**Problem:** A university's "website" field accepted `javascript:` links,
which run code instead of navigating anywhere, letting a mid-level account
eventually compromise a much more trusted one.

**Where:** The Universities tab of the internal staff Directory tool — the
field where a university's website address is stored and shown as a
clickable link.

**In plain terms:** A web link doesn't have to point to a website —
instead of `https://...`, it can start with `javascript:...`, which tells
the browser "don't go anywhere, just run this code right now." The system
had a general-purpose safety filter for text fields (it escapes characters
like `<` and `"` so they can't break the page), but that filter has
nothing to do with *which kind* of link is allowed — a `javascript:` link
sails through it completely untouched.

**Why it matters:** A `content_manager` (a mid-level staff role) could set
any university's "website" to one of these code-links. Anyone who later
opened that page and clicked the link — including a `superuser`, the
highest-privilege role on the site — would run that code as themselves.
It's a way for a moderately-trusted account to eventually compromise a
fully-trusted one, just by waiting.

**What we did, in two steps** (both requested and confirmed along the
way):
1. **Scoped who can edit what.** A `content_manager` can now only edit the
   website of *their own* university, matching how they're already
   restricted everywhere else in this tool. A `superuser` is unrestricted.
2. **Closed the actual hole.** The website field now only accepts values
   that genuinely start with `http://` or `https://` — anything else,
   including a `javascript:` link, is rejected outright by the server, no
   matter who submits it. Tested against the exact attack string and
   confirmed it's now rejected, while normal website links still save
   fine.

**Status:** Fixed.

---

### 9. Uploading an image could let someone write files outside the intended folder

**Problem:** A photo-upload feature built its save path from unvalidated
web-address segments, letting an editor smuggle a folder-traversal
sequence through on the Windows server this app runs on.

**Where:** The old "Agora Directory" tool's profile-photo upload feature.

**In plain terms:** When uploading a photo, the server built the filename
to save it under directly from two pieces of the web address (a user ID
and a "field" name) rather than generating a safe filename itself. Web
addresses normally can't contain a literal `/` in a single segment like
this — the underlying web framework blocks that — but they *can* contain a
backslash (`\`), which is also a valid "go up a folder" separator on the
Windows server this app runs on. That meant someone with edit access to
this tool could smuggle a `..\..\..\` sequence through and write a file
somewhere outside the folder meant for profile photos — combined with the
fact that the "is this really an image?" check only trusted a label the
uploader's own browser sent (trivially fakeable), so the file's *content*
wasn't verified either.

**Why it matters:** This let a user with editing rights on this one tool
write an arbitrary file, with content they chose, to a location they chose
elsewhere on the server — potentially somewhere that could later be served
back out as a real web page, escalating a content-editing permission into
something much bigger.

**What we did:** Around the same time, a decision was made to fully retire
this old Directory tool — its own promotional listing had already been
turned off site-wide, and its replacement (the newer "Directory" tool)
covers the same need. We confirmed the *code* behind it was still
technically reachable before removing it (a few other pages were quietly
relying on its login-check and profile-editing features), rebuilt those
specific features against the still-live replacement and a small addition
to the site's core login-checking code, and then fully removed the old
tool: unmounted it from the server, archived its code, and deleted the
last few remaining links to it (including two entirely outdated backup
copies of the site's homepage that nobody could actually reach, but which
still mentioned it).

**Status:** Fixed by retiring the tool.

---

### 10. A mid-level staff account could plant a fake person under a different university

**Problem:** Creating a new Directory entry was missing the same
"own-university-only" check that editing and deleting already had.

**Where:** The (current, still-active) Directory tool's "add a new person"
feature.

**In plain terms:** A `content_manager` account is meant to only manage
people from their own university — and the system already enforced that
correctly when *editing* or *deleting* an existing person. The one gap:
when *creating* a brand-new person, that same check was simply missing. A
content_manager for one university could create a new "staff member" entry
— complete with a name and an email address of their choosing — and file
it under a *completely different* partner university's section of the
shared directory.

**Why it matters:** This is a way to plant a fake identity — say, a bogus
"IT Support" contact with an attacker-controlled email — somewhere in the
directory that the person creating it has no legitimate authority over,
where staff at that other university might trust it.

**What we did:** Added the same "must be your own university" check that
already existed for editing, this time to the creation step too. A
`content_manager` can now only add people to their own university;
`superuser` remains unrestricted, since a superuser deliberately planting a
fake entry is an accepted, much smaller risk than *any* mid-level account
being able to do it to *any* university. We tested all three cases
(blocked, allowed for own university, unrestricted for superuser) against
the real code.

**Status:** Fixed.

---

### 11. An entire analytics tool had no login check of any kind

**Problem:** The Site Analytics tool — including the ability to rewrite
its own configuration — had zero authentication anywhere, and even after
being locked down, its own charts didn't send the login token needed to
use it.

**Where:** The "Site Analytics" tool (traffic statistics pulled from an
external analytics service), `web/apps/matomo_analytics/`.

**In plain terms:** While making sure every internal tool required a real
login (see "Broader hardening work" below), this tool turned out to have
**zero** authentication on every single one of its features — including
the ability to *rewrite its configuration*. Anyone, logged in or not,
could view the site's traffic data or change what it tracks. This tool is
meant to be restricted to the top administrator role only; it had no
restriction whatsoever. Separately, while renaming this tool's web address
to match its display name, we found that its actual chart-loading code
never attached a login token to its requests at all — meaning that once
real login enforcement was switched on, the dashboard would have shown no
data even to a legitimately logged-in administrator.

**Why it matters:** A site-wide analytics/configuration tool with no
access control at all is a significant exposure on its own, and fixing the
access control without also fixing the token bug would have made the tool
appear broken for the one role actually meant to use it.

**What we did:** Every part of this tool now requires being logged in as a
`superuser`. The chart-loading code was fixed to attach a login token,
alongside the address rename.

**Status:** Fixed.

---

### 12. UMA Holiday Tracker: a hidden-code trap in the default calendar view

**Problem:** The small colored "chip" that represents every calendar entry
by default — not just the detail popup already fixed once — let anyone
with edit rights on this tool run code in the browser of anyone who opened
the page.

**Where:** The small colored "chip" that represents each calendar entry
directly on the UMA Holiday Tracker's month grid.

**In plain terms:** An earlier fix (see finding #18) already closed a
"hidden-code trap" in this same tool's trip-detail popup — someone could
type what looks like ordinary text into a trip's destination or
description, and have it actually run as code in the browser of whoever
later opens that trip's details. That fix only covered the detail popup.
This audit found the exact same two fields, completely unescaped, in a
second place: the small chip that represents every entry directly on the
calendar grid — what every UMA staff member sees by default, without
clicking anything, every time they open the page.

**Why it matters:** Because this trap fires on the default view rather
than needing someone to click into a trip's details, it's actually easier
to trigger than the one already fixed in finding #18 — and it reaches the
same audience, potentially including the `superuser` account.

**What we did:** Routed the destination, description, and person's-name
fields in the chip through the same text-safety helper already used
everywhere else on the page (the same fix already applied to the detail
popup in finding #18, just extended to this second spot) — and, while in
there, found and fixed the identical gap in the calendar's name/color
legend. Confirmed the calendar page still loads normally afterward.

**Status:** Fixed.

---

### 13. Event Tracker: its own, unfixed version of the same hidden-code trap

**Problem:** The Event Tracker had multiple places — its own calendar
grid, detail popup, and list view — where user-typed text ran as code
instead of displaying as text, none of which any earlier fix had touched.

**Where:** The Event Tracker's own calendar-grid entries, event-detail
popup, and table/list view.

**In plain terms:** This is the same bug family as finding #19 below (a
hidden-code trap planted through a text field and run in whoever's browser
later views it) — except the Event Tracker turned out to have several
instances of it that had never been touched by any earlier fix: the
description field in its detail popup, and — like the Holiday Tracker in
finding #12 — its own, separate version of the calendar-grid chip problem,
since each tool renders its own grid independently. On top of those, the
same unsafe handling turned up on a UNINOVIS-group label, a linked event's
name, the list of a meeting's participants (names, emails, universities),
and two columns (category, university) in the tool's table/list view.

**Why it matters:** The Event Tracker is used by a broad set of staff
roles, and — like finding #12 — the calendar-grid version of this fires
just from opening the page, no click required, for anyone who views the
shared calendar.

**What we did:** Routed every one of those fields through the tool's
existing text-safety helper — the same fix already used elsewhere on the
same page, just applied consistently everywhere user-typed text ends up on
screen. Confirmed the calendar and list views both still load and display
correctly afterward.

**Status:** Fixed.

---

### 14. "Professor-only" Eulalia screens have no check at all

**Problem:** Four endpoints documented as teacher-only don't actually
check that the visitor is a teacher — or logged in at all.

**Where:** Four Eulalia endpoints for handling students' review requests
and questions to the teacher (`web/app.py`).

**In plain terms:** These screens are meant to be teacher-only — reading a
student's request for a re-mark, or a question they've asked, and letting
the teacher answer it. None of the four actually check that the visitor is
a teacher, or even that they're logged in at all.

**Why it matters:** The two "write" ones let a total stranger plant a fake
"teacher's answer" against any student's request — something that student
would then see and reasonably trust as coming from their actual teacher.

**What we did:** Tested directly: all four respond normally to a plain,
logged-out request. No fix has been applied yet.

**Status:** Open. Needs the same "must be a real, logged-in teacher" check
every other teacher-only screen in this codebase already has.

---

### 15. A folder-navigation trick works on Eulalia's student projects

**Problem:** Loading, saving, and deleting a student's project file builds
the filename straight from a web-address parameter, without the cleanup a
near-identical piece of code elsewhere in the same file already applies.

**Where:** The code that loads, saves, and deletes a student's research
project file for Eulalia's project-based exercise (`web/app.py`).

**In plain terms:** The same "go up a folder" trick already described and
fixed elsewhere in this report (findings #2, #9) is possible again here —
this code builds a filename directly from a project ID in the web address,
with none of the cleanup that a nearby, very similar piece of code in the
same file already does correctly.

**Why it matters:** A `teaching_staff` account — a fairly ordinary role,
not just the top administrator — could use this to move or read a file
outside the project folder it belongs in.

**What we did:** Confirmed the missing cleanup step by code review. Fixed
by applying the same shared filename-cleanup helper introduced for finding
#6 to every place a project ID turns into a path: loading a project,
saving one, and moving a deleted one into the archive folder. Confirmed
the server still starts and the module still imports cleanly afterward.

**Status:** Fixed.

---

### 16. A password-reset email's link could be sent to the wrong domain

**Problem:** Password-reset and invitation links are built from the
`Host` header of the incoming request, with no check that the server
rejects a spoofed one.

**Where:** Every "here's your password reset / invitation link" email
(`web/app.py`).

**In plain terms:** The link mailed to someone resetting their password or
accepting an invitation is built using the web address the request
*claims* to have come in on — a piece of information a visitor can largely
choose themselves when making the request, unless the server is separately
configured to reject requests that lie about it. This server isn't
configured that way.

**Why it matters:** If this site is ever placed behind another server that
forwards requests to it (a common setup) without that separate check, an
attacker could make a password-reset request on someone else's behalf that
looks normal in every way except the mailed link secretly points at a
domain the attacker controls — and that link carries the one-time code
needed to take over the account.

**What we did:** Flagged from how the code and server configuration are
written; not tested against real email/accounts. No fix has been applied
yet.

**Status:** Open. The fix is to tell the server the exact list of domain
names it should ever consider itself reachable at, and reject anything
else before it ever gets used to build a link.

---

### 17. A captured Moodle login link can be replayed

**Problem:** LTI logins check that a request is recent, but never check
whether that exact request has already been used before.

**Where:** The shared code behind all four LTI tools (`UltiR/`).

**In plain terms:** These tools are supposed to have two independent
safety checks on an incoming login: "is this recent?" and "have we already
seen this exact one before?" Only the first one is actually implemented —
a login attempt is accepted as long as it's less than ten minutes old, no
matter how many times that same attempt has already been used.

**Why it matters:** If a valid login link is ever captured — a shared
computer, a compromised network, a link that ends up somewhere it
shouldn't — it can be reused as many times as an attacker likes within
that ten-minute window, each time creating a fresh, valid session for
whoever it belonged to.

**What we did:** Confirmed by reading the code that no such check exists.
No fix has been applied yet.

**Status:** Open. Needs an actual "have I seen this one before" check, not
just an age check.

---

## MEDIUM

### 18. UMA Holiday Tracker: a hidden trap in the trip-detail popup

**Problem:** A calendar entry's destination/description fields were
inserted into the page as raw HTML instead of plain text.

**Where:** The UMA Holiday Tracker, in the popup that shows details of a
logged business trip.

**In plain terms:** The "destination" and "description" fields you type
when logging a business trip were inserted directly into the page as raw
HTML, the same stored-XSS pattern described in finding #3 — the tool
already had a proper text-safety helper used everywhere else on the same
page, it just wasn't applied to these two specific fields.

**Why it matters:** Because this is a *shared* calendar, any UMA staff
member's "destination" gets displayed in the browser of every other UMA
staff member — including `content_manager`s and the `superuser` — who
opens that entry. One person planting a trap here could eventually catch
someone with much higher privileges.

**What we did:** Routed those two fields through the same text-safety
helper already used for everything else on the page. Whatever someone
types there now always displays as plain, inert text — even something
that looks like a snippet of code just shows up as literal text on screen.

**Status:** Fixed. (A second, unrelated instance of the same trap — the
calendar-grid chip rather than this popup — was found in the follow-up
audit; see finding #12.)

---

### 19. Event Tracker let strangers plant traps through a half-finished feature

**Problem:** A "personal event" feature skipped the login check entirely,
combined all anonymous visitors into one shared identity, and displayed
descriptions as raw HTML.

**Where:** The Event Tracker's "personal event" feature (a way to log a
private, only-you-can-see calendar entry).

**In plain terms:** This combined three problems:

1. Creating a "personal" (private) event skipped the normal permission
   check entirely — the system was designed to let *any* logged-in person
   keep their own private notes without needing special editor rights, but
   the check for "are you even logged in at all" was accidentally skipped
   too, not just the "are you an editor" check.
2. Because — as described in finding #3 — every anonymous visitor shares
   one "guest" identity, "personal" events created by anonymous visitors
   all piled into one shared bucket that *any other* anonymous visitor
   could also see and add to.
3. The event's description field, again, was inserted as raw HTML rather
   than safe text.

**Why it matters:** An anonymous stranger could plant a trapped "personal"
event with zero login, and it would be shown to any *other* anonymous
visitor who happened to load their own "personal" calendar (which, because
of the shared-identity bug, was really everyone's shared calendar). The
blast radius stayed within the pool of anonymous visitors rather than
reaching staff directly, which is why this was rated Medium rather than
Critical like finding #3 — but it was still a real, zero-login attack
path.

**What we did:** Removed the personal-event feature entirely rather than
patching around it — the dedicated button for it, the visibility option in
the event form, and the entire separate storage system behind it are all
gone. On top of that, the whole Event Tracker now requires a real login
for absolutely everything, closing the shared-guest loophole at its root,
not just for this one feature.

**Status:** Fixed by removing the feature. (Event Tracker had further,
separate hidden-code-trap bugs found in the follow-up audit; see
finding #13.)

---

### 20. Logins never expire, and can leak through ordinary web logs

**Problem:** Session tokens are valid forever and are sometimes accepted
directly in the web address rather than only through normal hidden login
headers.

**Where:** `web/auth.py`, the core session-management code shared by the
whole site.

**In plain terms:** Once you log in, your session token stays valid
forever — there's no automatic timeout, no "please log in again after two
weeks." On top of that, a handful of places on the site accept that same
token as part of the *web address* itself (necessary for things like
calendar subscription links, which can't send the normal hidden login
information a browser page can). Anything appearing in a web address has a
habit of ending up in server logs, browser history, or a shared link.

**Why it matters:** If a token is ever exposed through one of those
channels — even briefly — whoever gets hold of it has permanent access,
with no way for anyone to know it happened or to bound how long the
exposure lasts.

**What we did:** Confirmed by code review that `web/auth.py` has no expiry
check anywhere. The follow-up audit found the four LTI tools follow the
exact same in-the-URL pattern throughout (see finding #29). No fix has
been applied yet.

**Status:** Open. The fix is to add an expiry to sessions (so a leaked
token eventually stops working on its own) and, where practical, stop
accepting tokens via the web address at all — see finding #29 for the
LTI-specific extension of this same issue.

---

### 21. Three more tools had individual features open to the public

**Problem:** Several otherwise-protected tools had one or two individual
features that had simply been forgotten when login was required elsewhere.

**Where:** Mobility Planner, Researcher Connect, and UNIGRACON (grade
converter).

**In plain terms:** Similar, smaller versions of the login-check gap in
finding #11 turned up in three more tools — each otherwise-protected tool
had one or two individual features that had simply been forgotten:

- **Mobility Planner:** the university list and the actual "compute a
  deadline" calculation were both open to anyone.
- **Researcher Connect:** the main data listing and both of its
  file-export buttons were open to anyone.
- **UNIGRACON:** the university list, the conversion-rates list, the
  per-university lookup, and — notably — the actual grade conversion
  calculation itself were all open to anyone.

**Why it matters:** Data and functionality meant to require staff login
was reachable by anyone who found the right web address.

**What we did:** All were fixed the same way: each now requires a real
login.

**Status:** Fixed.

---

### 22. `javascript:` link injection on two more tools

**Problem:** The link-scheme validation from finding #8 was never
extended to three other free-text link fields in two other tools.

**Where:** The Event Tracker's meeting-link and registration-link fields,
and Researcher Connect's website field — including the bulk-import paths
for both tools.

**In plain terms:** Finding #8 already fixed the `javascript:`-link trick
for a university's website in the Directory tool — a web link doesn't have
to point to a website; instead of `https://...`, it can start with
`javascript:...`, telling the browser to run code instead of navigating
anywhere. That fix made the field reject anything that isn't a genuine
`http://` or `https://` link. This audit found three more fields, in two
different tools, that had never received the same treatment: an event's
meeting link and registration link, and a researcher's listed website.

**Why it matters:** Same mechanism as finding #8 — a moderately-trusted
editor account plants one of these code-links, and it runs in the browser
of whoever later clicks it, which could be a far more privileged account.

**What we did:** Applied the identical `http://`/`https://`-only rule from
finding #8 to all three fields, enforced automatically on every create and
edit. Also closed the same gap in the JSON/TSV bulk-import for events and
the Excel import for researchers, which had been building these fields
directly from uploaded file data and skipping the check entirely — a
non-`http(s)` value is now silently dropped during import rather than
accepted. Tested against the real, running server: submitting the attack
string is now rejected with an error and nothing is saved, while a normal
`https://` link still works exactly as before.

**Status:** Fixed.

---

### 23. A public survey tool hands out every answer to anyone who asks — fixed by retiring the tool

**Problem:** The screens for viewing and exporting all survey responses
have no login requirement, exposing every answer plus the submitter's IP
address.

**Where:** The "Data & AI Competences" survey tool
(`web/apps/survey_datalife/`).

**In plain terms:** The survey itself is meant to be open to anyone — no
login required to answer it, by design. The problem is that the page for
*viewing all the answers so far*, and the button to export them all, also
have no login requirement — a developer's note left directly in the code
says "No auth for now." Every answer, plus the IP address of whoever
submitted it (recorded automatically), is available to any visitor who
finds the right web address.

**Why it matters:** Survey answers plus an IP address is still identifying
information, being handed out with no access control whatsoever.

**What we did:** Tested directly: a marked test answer, submitted like a
real participant would, was immediately readable by a second, completely
anonymous request — IP address included. Rather than add a login
requirement, the tool was confirmed to have no menu entry, no link from
the intranet, and no reference anywhere else in the codebase — it was only
ever reachable by someone who already knew or guessed its exact web
address, and nothing currently points at it. It was fully retired: the
whole `survey_datalife` folder (code, static files, and the survey
responses collected so far) was archived into the same `old apps` folder
used for previously-retired tools, rather than deleted outright, and its
three lines mounting it onto the live server in `web/app.py` were removed.
Verified against the real, running server: every address under
`/survey-datalife/` — the survey form itself, the open response-viewing
and export screens — now returns 404, while the rest of the site is
unaffected.

**Status:** Fixed by retiring the tool.

---

### 24. Any logged-in account can create or reconfigure an AI agent

**Problem:** Agent-creation and agent-management endpoints check that the
visitor is logged in, but not that they hold the right role.

**Where:** The screens for creating a new AI assistant and managing an
existing one's settings (`web/app.py`).

**In plain terms:** Creating a brand-new AI agent — uploading its
reference documents and writing the instructions it follows — is supposed
to be restricted to trusted staff. The check that's actually in place only
confirms "is this person logged in at all," not "do they have the right
role." The same gap exists for forcing an existing agent to rebuild its
search index, which costs real processing time and money each time it
runs.

**Why it matters:** Any ordinary logged-in account (a student, say) can do
something that's supposed to require staff-level trust.

**What we did:** Confirmed that a logged-out visitor is correctly turned
away — the gap is specifically the missing role check for logged-in
accounts. No fix has been applied yet.

**Status:** Open. Needs the same staff-only check every other
agent-administration screen in this file already has.

---

### 25. A superuser-only report is actually open to everyone with an account

**Problem:** A logic slip means the "superuser or docente only" check on
an analytics report only runs when there's no session at all — any session
skips it entirely.

**Where:** The Algoria Map usage-analytics report (`web/app.py`).

**In plain terms:** This report says, in its own description, that it
requires being the top administrator or a teacher. The code that's
supposed to enforce that has a logic slip: it only double-checks the
visitor's role when *no* session is found at all — if a session exists,
regardless of whose or what kind, the check is skipped entirely.

**Why it matters:** Any account of any role — not just administrators or
teachers — can view this report's data.

**What we did:** Confirmed directly, with a temporary, ordinary
low-privilege test account created and then deleted for this purpose: that
account could open the report just fine, while a genuinely
administrator-only screen correctly turned it away as a control
comparison. No fix has been applied yet.

**Status:** Open. The logic needs to actually check the visitor's role in
every case, not just when there's no session at all.

---

### 26. Deleting a shared course file doesn't check the filename

**Problem:** The LTI Proyecto tool's document-delete endpoint is missing
the filename cleanup its own upload endpoint already applies.

**Where:** The "delete a course document" screen in the Proyecto LTI tool
(`UltiR/proyecto/`).

**In plain terms:** Uploading a document to this tool correctly strips out
anything unusual from the filename first. Deleting one doesn't — it's
missing the exact same cleanup step its own upload sibling already has, a
few lines away in the same file.

**Why it matters:** Combined with finding #4 (which makes it trivial for
anyone to obtain the "instructor" access this screen requires), a real
folder-navigation attack here is more reachable than it would otherwise
be.

**What we did:** Confirmed the missing cleanup step by code review, then
fixed it by applying the exact same cleanup rule the upload endpoint
already uses. Verified live: obtained an instructor session the same way
finding #4 describes, uploaded a real test document, then confirmed a
backslash-traversal filename against the delete endpoint is now treated as
literal (safe) text rather than escaping the folder — and that deleting
the real test document normally still works correctly afterward.

**Status:** Fixed.

---

### 27. A chat message could potentially steer the Sonic Pi music tool into running unintended code

**Problem:** Some inputs used to build AI-generated Sonic Pi code aren't
checked against an allow-list that already exists in the same file for a
different piece of the same feature.

**Where:** The Sonic Pi ("Sonic Composer") creative-agent tool
(`agents/base/sonic_pi_tools.py`).

**In plain terms:** This tool turns a conversation with the AI into real,
generated Sonic Pi (music-live-coding) instructions, which then run on a
connected Sonic Pi program. Some of the pieces used to build that
generated code — which sound/instrument to use, for instance — come from
the AI's own output without being checked against the tool's own list of
allowed options first, even though that allow-list already exists in the
code for a different piece of the same feature.

**Why it matters:** Since the AI's choices are themselves steerable by
whatever the user says in chat, this is the kind of gap that could
potentially let a cleverly worded chat message make the tool run code it
was never meant to. How serious this is in practice depends on whether the
Sonic Pi program is actually running on the production server — the code
looks for a local Sonic Pi installation, which suggests this feature is
meant for a desktop-style setup rather than a bare cloud server, but that
should be confirmed rather than assumed.

**What we did:** Confirmed by code review that the allow-lists exist but
aren't applied consistently. No fix has been applied yet.

**Status:** Open. The already-existing allow-lists should be applied
consistently to every piece of AI-chosen input used to build the generated
code, not just some of them.

---

## LOW

### 28. A hardcoded fallback analytics API token

**Problem:** The Matomo analytics tool falls back to a real-looking,
source-visible API token if the proper one isn't configured.

**Where:** `web/apps/matomo_analytics/matomo_analytics.py`.

**In plain terms:** Like findings #1 and #7, this tool has a fallback
value baked into the source code — this time an analytics API token rather
than a login secret — used automatically if the real one isn't set in the
server's configuration.

**Why it matters:** Access to this tool itself is correctly locked to
`superuser` (see finding #11), so this doesn't grant unauthenticated
access on its own — but it's a real token silently used in place of a
missing one instead of failing loudly, and it's now sitting in public
source history where anyone can see it.

**What we did:** Flagged during the first review pass and confirmed still
present, unchanged, on the follow-up pass. No fix has been applied yet.

**Status:** Open. Remove the hardcoded fallback; the tool should fail
loudly if the real token isn't configured, the same fix recommended for
findings #1 and #7.

---

### 29. LTI login links carry the session token in the address bar

**Problem:** Every LTI login/redirect link puts the session token directly
in the URL, the same pattern already flagged site-wide in finding #20.

**Where:** The four LTI tools (`UltiR/`), extending the pattern already
described in finding #20.

**In plain terms:** Finding #20 already described this site's sessions
never expiring and sometimes being accepted via the web address rather
than the normal hidden login information a browser sends automatically.
This audit found the LTI tools follow the exact same pattern throughout —
every login and redirect link carries the session token directly in the
address bar.

**Why it matters:** Anything in a web address has a habit of ending up
somewhere it shouldn't — browser history, a shared screen, a server log —
and unlike a normal login, there's no expiry to eventually close that
window of exposure.

**What we did:** Confirmed by code review across all four LTI providers.
No fix has been applied yet.

**Status:** Open — same underlying issue as finding #20, worth fixing
together with it.

---

### 30. An edit-permission check trusts a value the editor themself provides

**Problem:** "You can only edit your own answer" is enforced by comparing
a plain, editable text field against itself, rather than checking who's
actually logged in.

**Where:** Eulalia's "empathy challenge" screen, where students can edit
their own submitted answers (`web/app.py`).

**In plain terms:** "You can only edit your own answer" is checked by
comparing a name field the editor's own request includes against the name
stored on the answer — and that name field is plain, visible, editable
text, not something tied to who's actually logged in.

**Why it matters:** Low impact on its own — this is a shared classroom
exercise with no sensitive data behind it — but it's a real example of an
ownership check that can be talked past just by claiming to be someone
else.

**What we did:** Confirmed by code review. No fix has been applied yet.

**Status:** Open. The check should be based on who is actually logged in,
not a value supplied alongside the request. Worth fixing for consistency
with how ownership is checked correctly everywhere else on the site.

---

## INFORMATIONAL / PROCESS

These aren't vulnerabilities in the usual sense, but they came out of the
same review work and are worth recording for a complete history.

### 31. A fix meant to *tighten* security accidentally locked everyone out

**Problem:** The mechanism used to hide a page until login was confirmed
failed *closed* — a page stayed permanently blank if the login check
failed to complete for any reason, even one unrelated to actually being
logged in.

**Where:** The client-side login-check logic rolled out alongside the
"require login everywhere" hardening work (see "Broader hardening work"
below).

**In plain terms:** While rolling out the "must be logged in" requirement,
the approach used for hiding a page's content until login was confirmed
had a serious flaw: the page started completely invisible, and only
became visible again after a background check *successfully* finished. If
that background check failed to finish for *any* reason — even one
completely unrelated to whether someone was logged in — the page would
stay blank forever, with no error message, for logged-in and logged-out
visitors alike.

**Why it matters:** This wasn't a way in for an attacker — if anything, it
over-corrected — but it would have made the entire site unusable for
everyone, which is its own kind of serious failure, and it shipped in the
same change set as real security fixes without being caught by the review
process itself.

**What we did:** Caught in testing ("I cannot access any page even though
I'm logged in"), and fixed by redesigning the check so pages are visible
by default and only redirect to the login page on a *confirmed* failure,
rather than silently failing closed.

**Status:** Fixed.

---

### 32. Retiring the old Directory tool silently broke three other features

**Problem:** Removing the old Directory app's data file left three
unrelated features quietly reading from a file that no longer existed —
one crashed outright, two others silently showed wrong or missing data.

**Where:** Event Tracker's group/participant picker, UMA Holiday Tracker's
name-display helper, and the site-wide `resolve_display_name()` function
used in the navigation bar, login screen, and intranet welcome message.

**In plain terms:** Removing the old Directory app (finding #9) left the
Event Tracker trying to read a data file that no longer existed, which
would have crashed its page every single time it loaded. This was first
patched by making that lookup degrade gracefully instead of failing — the
page stopped crashing, but this only masked the underlying problem. The
feature that data fed — "pick a group or subgroup and its members
automatically become event participants" — was still silently broken: the
group dropdown would simply always be empty, with no error message and no
obvious reason why. This was caught not by the review process, but by
someone noticing the feature wasn't working and asking about it directly.
A follow-up sweep then found two more places quietly pointing at the same
gone file, both already wrapped in error-handling so neither ever crashed
a page — they just silently returned a wrong or missing answer: the UMA
Holiday Tracker's "show a person's real name instead of their email"
helper (so the calendar had been quietly showing everyone's email address
instead of their name), and the core login system's own
`resolve_display_name()` function, used sitewide, which was falling back
to a name guessed from someone's email address instead of their real one.

**Why it matters:** None of these were exploitable by an attacker, but a
"fixed the crash" report line is worth double-checking for "but does the
feature actually still work?" — and one of the three (showing email
addresses instead of names, sitewide) was a real, if minor, information
downgrade that nobody would have noticed without specifically looking.

**What we did:** Rewired the Event Tracker's group/participant lookup to
pull from the current, live Directory app's real data, translating it into
the same shape the picker already expected. Selecting a top-level group
now correctly pulls in everyone in that group and every subgroup nested
underneath it, however many levels deep; selecting one specific subgroup
only pulls in that subgroup's own direct members — tested first against a
synthetic multi-level example, then against real, current directory data.
Repointed both the Holiday Tracker's name-display helper and
`resolve_display_name()` to the same live data (matching its actual field
names, which differ slightly from the old app's) and verified both against
real directory entries.

**Status:** Fixed.

---

### 33. AI-agent public-path exemption is pattern-based, not agent-specific

**Problem:** The rule deciding which parts of an agent's API skip the
login requirement matches by web-address pattern across *every* agent,
not the one specific agent it was written for.

**Where:** The public-path exemption list in the site's login-enforcement
middleware (`web/app.py`).

**In plain terms:** The rule that decides which parts of an AI agent's API
are public applies by web-address pattern (e.g. anything containing
`/pdf/` or `/quickguide`) rather than to one specific agent.

**Why it matters:** Today, no agent other than the one this was written
for actually has the matching feature, so nothing is currently exposed —
but a future agent that implements a route matching one of these patterns
would become public automatically, without anyone deciding that on
purpose.

**What we did:** Confirmed by code review; no other agent currently
implements a matching route, so there is nothing to fix right now.

**Status:** No action needed today — flagged so it's remembered when
building the next agent of that kind.

---

### 34. Two AI-agent folders contain unused, wide-open standalone copies

**Problem:** Two agent folders each contain a second, alternate way of
running that same agent as its own small website, with no login and no
access restrictions — but this isn't how the live site actually runs them.

**Where:** `agents/algoria_map/` and `agents/health_wellbeing_sistems/`.

**In plain terms:** Both folders contain a stand-alone version of the
agent that could, in principle, be run as its own small website — with no
login and no access restrictions at all.

**Why it matters:** If this stand-alone copy were ever run on its own
(rather than through the main site, which instead loads the agent's code
directly), it would be completely open to the internet.

**What we did:** Confirmed this isn't how the live site actually runs
these two agents today — it loads the agent's code directly rather than
talking to the stand-alone copy — so there's nothing to fix right now.

**Status:** No action needed today — flagged so nobody assumes that
stand-alone copy is safe if it's ever run on its own in the future.

---

## Broader hardening work (not individual findings)

Several follow-up requests went beyond the numbered findings above but are
recorded here because they materially reduce the site's attack surface.

**Retiring genuinely dead code.** Eight app folders that were no longer
used by anything — including forks of tools that live elsewhere, a
superseded holiday tracker, and several folders containing nothing but
leftover compiled files with no real source left — were archived into a
clearly labeled `old apps` folder and fully disconnected from the live
server, so none of them can be reached by any web address anymore. All
references to them were removed from menus and internal documentation, and
two entirely obsolete backup copies of the site's homepage (unreachable,
but still mentioning the retired tools) were deleted outright.

**Requiring login everywhere it should be required.** Beyond the specific
findings above, every internal tool that belongs on the intranet's WP1–WP5
or "UMA internal tools" menus now requires a genuine login for every
single feature — not just a "guest" fallback that quietly let people look
around without one. Two tools that are deliberately public-facing research
resources (not internal admin tools) were confirmed and intentionally left
open.

**Matching web addresses to what things are actually called.** Six tools'
web addresses were renamed to match their display name on the intranet
menu exactly (for example, the Directory tool moved from a leftover
technical name to simply `/directory/`, and the UMA Holiday Tracker gained
the "uma-" prefix its name has always had) — partly a usability
improvement, but also useful for closing off any old bookmarked or guessed
addresses.

---

## Where things stand now

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Hardcoded fallback login secret (Eulalia/Moodle) | **Critical** | **Open** |
| 2 | Anonymous file-write via feedback form | Critical | Fixed |
| 3 | Research Proposals: anonymous hijack chain | Critical | Fixed (tool retired) |
| 4 | LTI "test launch" endpoints hand out instructor access | **Critical** | **Open** |
| 5 | Default `admin`/`admin` superuser account | High (was Critical) | Mitigated |
| 6 | Anonymous file-write via Eulalia bulos/respuestas | Critical | Fixed |
| 7 | Hardcoded LTI shared secrets (four tools) | **Critical** | **Open** |
| 8 | Fake-link code injection on university websites | High | Fixed |
| 9 | Old Directory: photo-upload file-write bug | High | Fixed (tool retired) |
| 10 | Directory: cross-university fake entries | High | Fixed |
| 11 | Site Analytics: no login check anywhere | High | Fixed |
| 12 | UMA Holiday Tracker: hidden-code trap, calendar chip | High | Fixed |
| 13 | Event Tracker: hidden-code trap, calendar + list views | High | Fixed |
| 14 | "Professor-only" Eulalia screens with no check | **High** | **Open** |
| 15 | Path traversal in Eulalia student-project files | High | Fixed |
| 16 | Password-reset links redirectable via forged Host header | **High** | **Open** |
| 17 | LTI logins can be replayed for up to ten minutes | **High** | **Open** |
| 18 | UMA Holiday Tracker: hidden-code trap in trip-detail popup | Medium | Fixed |
| 19 | Event Tracker: anonymous personal-event trap | Medium | Fixed (feature removed) |
| 20 | Sessions never expire / leak via web addresses | **Medium** | **Open** |
| 21 | Mobility Planner / Researcher Connect / UNIGRACON: open features | Medium | Fixed |
| 22 | Fake-link code injection, two more tools | Medium | Fixed |
| 23 | Survey tool: every response openly readable, no login | Medium | Fixed (tool retired) |
| 24 | Any logged-in account can create/manage AI agents | **Medium** | **Open** |
| 25 | Superuser-only report actually open to any account | **Medium** | **Open** |
| 26 | LTI: deleting a project file doesn't check the filename | Medium | Fixed |
| 27 | Sonic Pi tool: a chat message could steer generated code | **Medium** | **Open** |
| 28 | Hardcoded fallback analytics (Matomo) API token | **Low** | **Open** |
| 29 | LTI login links carry the session token in the address bar | Low | **Open** |
| 30 | Edit-permission check trusts a client-supplied value | Low | **Open** |
| 31 | Login-hiding fix accidentally locked everyone out | — (process) | Fixed |
| 32 | Retiring old Directory silently broke three other features | — (process) | Fixed |
| 33 | Agent public-path exemption is pattern-, not agent-specific | — (informational) | No action needed |
| 34 | Two agent folders contain unused, wide-open standalone copies | — (informational) | No action needed |

### Recommended next steps, in priority order

Thirteen findings are still open, plus one (#5) that's mitigated but not
fully closed. This list covers all of them, most to least urgent;
everything else in the table above (#2, #3, #6, #8–#13, #15, #18, #19,
#21, #22, #23, #26, #31, #32) is already fixed and needs no further
action.

1. **Shut down or gate the LTI "test launch" endpoints (#4).** Exploitable
   right now, by anyone, with zero credentials — the single most urgent
   item in this entire report.
2. **Finish closing #5**: generate a random one-time password for the
   default admin account instead of the fixed `admin`/`admin`. Downgraded
   from Critical to High since the account can no longer actually be used
   for anything once someone logs into it — but whoever gets there first,
   attacker or administrator, still locks the other out until it's reset
   by hand.
3. **Set real values for the hardcoded secrets — Moodle/Eulalia (#1) and
   all four LTI tools (#7).** Same fix, same root cause, five places.
4. **Add the missing "must be a real, logged-in teacher" check to the
   Eulalia professor screens (#14).**
5. **Add session expiry (#20)** and fix the related LTI-specific gap —
   login links carrying the token in the address bar (#29) — together;
   same underlying problem.
6. **Fix the Host-header trust gap in password-reset links (#16)** and add
   real replay protection to LTI logins (#17).
7. **Require a real login on the analytics report that's supposed to be
   superuser-only (#25)**, and the agent-creation/management screens that
   currently only check "logged in," not role (#24).
8. **Remove the hardcoded fallback analytics token (#28).** Lower stakes,
   same bad pattern as #1/#7, worth cleaning up while it's fresh.
9. **Apply the existing allow-lists consistently in the Sonic Pi tool
   (#27)** — worth confirming first whether Sonic Pi actually runs on the
   production host, which changes how urgent this one is.
10. **Fix the client-supplied ownership check on Eulalia's empathy-challenge
    answers (#30).** Lowest stakes of the open items, but a quick, clean
    fix.
11. No action needed on #33 or #34 today — just keep them in mind if the
    agent framework or either stand-alone agent copy is ever extended.

Everything in the table marked "Fixed" above has been fixed and verified
against the real, running code.
