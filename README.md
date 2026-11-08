# e-Bunge — Digital County Assembly Motion and Proceedings Platform

A working PHP 8.2+ application using PDO SQLite, server-rendered HTML, CSS and JavaScript. The app stores real accounts and records, enforces role and record-scope permissions on the server, and supports workspaces for Members of County Assembly (MCA), the Hansard Office and the Office of the Speaker, plus a public portal.

## Account-role policy

Registration permits a person to select MCA, Hansard Office or Office of the Speaker, and immediately activates that role, as explicitly requested. Passwords are hashed and restricted actions check the selected role, but self-selection does not verify institutional identity. Do not expose this registration flow on a live County Assembly system without verified institutional onboarding (for example, administrator-approved invitations or authoritative identity verification).

## Run locally

Requirements: PHP 8.2 or newer with PDO SQLite, SQLite3, mbstring and fileinfo, plus writable data storage.

```sh
cd ebunge-system
EBUNGE_COOKIE_SECURE=0 php -d upload_max_filesize=8M -d post_max_size=10M -S 127.0.0.1:3000 -t public public/router.php
```

Open `http://127.0.0.1:3000`. On first request the app creates `var/ebunge.sqlite`. `var/` holds the SQLite database and private motion attachments; keep it outside the public web root on a conventional production server, restrict access and back it up. The database also contains the assembly branding settings and validated logo image data. The source package includes no pre-filled users, passwords, records or logo settings. Create the first account through registration.

The managed Preview command starts the same PHP app on port 3000. The source package can run independently of Preview.

### Runtime configuration

Set `EBUNGE_COOKIE_SECURE=1` (the default) behind public HTTPS; set `0` only for plain-HTTP local development. `EBUNGE_DB_PATH` may be an absolute path or a path relative to this application directory. `EBUNGE_UPLOAD_DIR` accepts an absolute or application-relative private directory for motion attachments and defaults to `var/uploads`.

## Password recovery email

Reset tokens are random, stored only as hashes, single-use and expire after one hour. Requests are limited to five per address/IP per hour. The response does not reveal whether an address has an account. Configure PHP's `mail()` transport and set both values to send real email:

```sh
EBUNGE_MAIL_FROM='e-Bunge <no-reply@your-domain.example>'
EBUNGE_PUBLIC_URL='https://your-verified-host.example'
```

Without both values and a working mail transport, the app does not claim an email was delivered. Keep provider credentials out of source.

## Workflows

- **MCA:** submit and track motions, correct motions returned by Hansard or the Speaker, see approved sittings and own approved attendance, cast one Support or Oppose vote per open subject, submit petitions, track their review and any converted motion, view only committees they belong to, and download authorized reports.
- **Hansard Office:** review/forward motions, correct and resubmit Hansard-origin records returned by the Speaker, review and forward petitions, prepare/submit attendance for explicit Speaker approval, create voting subjects, inspect closed results, and submit results for Speaker approval; prepare and resubmit committees/sittings/voting subjects as returned; create committee meetings and prepare reports.
- **Office of the Speaker:** open approved voting subjects for MCA ballots; approve results after Hansard review; return motions, petitions, voting subjects, sittings and committees for correction with a note; approve sittings, attendance, committees/meetings and reports; review an incoming/waiting/recently-completed decision board.
- **Voting lifecycle:** Hansard submits a subject → Speaker approves and opens it → each MCA may vote Support or Oppose once → Hansard closes and reviews the computed tally → Speaker approves the result. New ballots are Support/Oppose only. Existing database values `yes` and `no` render as Support and Oppose; any legacy Abstain ballot remains distinguishable in the tally. Results remain hidden from MCAs until Speaker approval.
- **Petition conversion:** Speaker approval creates a linked motion at Hansard review. An MCA-origin petition keeps the MCA as motion sponsor and appears in that MCA's motion register. A public petition has no account owner; its converted motion is attributed to the Hansard account that forwarded it. The petition and motion retain a traceable link; repeated decisions do not duplicate the conversion.
- **Assembly identity:** the Speaker may open **Assembly identity** in the workspace to set a motto (maximum 120 characters), upload a PNG/JPEG/WebP logo or photo (maximum 1 MiB), replace it or restore the default chamber mark. Only these image formats are accepted and image bytes are stored with the SQLite branding row. This setting is global and visible on public and authenticated pages; other roles cannot edit it.
- **Progress and audit:** Activity shows accessible stage-by-stage progress for supported records and a timestamped audit timeline. Speaker task cards link incoming decisions, work awaiting another office or MCA ballots, and recent completed decisions. Attendance approval updates the sitting and its attendance entries so Hansard and affected MCAs see the approved record.
- **Public portal:** visitors see only Speaker-approved public motions, petitions and sitting schedules and may submit a petition without an account. An approved public petition is displayed publicly after review; it is also converted to a motion linked to the original petition.

The app records staff-entered quorum thresholds and approved-present attendance for procedural review; it does not independently decide a legally valid quorum or interpret the Constitution, applicable legislation or County Assembly Standing Orders. Review reports and recorded decisions under actual office procedures before relying on them.

## Run in a container

The included `Dockerfile` installs PHP with PDO SQLite and mbstring, sets an 8 MB motion-attachment limit and listens on `PORT` (default `3000`). Container filesystems may be temporary. Mount persistent private storage and set `EBUNGE_DB_PATH` and `EBUNGE_UPLOAD_DIR` to it for durable use. Back up the SQLite database (which includes the logo/motto) and attachments; temporary container files are not a backup.

## Security and operational care

Use a trusted HTTPS hostname, restrict access to the database and private uploads, configure operational email before relying on password recovery, and use monitored backups. The Speaker-only branding editor does not change institutional role verification. Self-selected role activation remains an explicit academic-prototype choice; verifying a user's office is an institutional responsibility not supplied by this package.

## Isolated workflow checks

From this directory, run `python3 tests/workflows.py`. The integration suite starts its own temporary PHP server and SQLite database, exercises each of the three roles plus public access, and deletes its temporary test data on exit; it does not use the live Preview database. A source-only syntax pass can also be run with `find . -name '*.php' -type f -print0 | xargs -0 -n1 php -l`.
