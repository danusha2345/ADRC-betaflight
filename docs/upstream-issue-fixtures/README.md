# Fixtures for the upstream blackbox-tools / Betaflight issue reports

Small synthetic Blackbox logs attached to issue reports filed against
`betaflight/blackbox-tools` and `betaflight/betaflight`. They are here because
GitHub issues created through the CLI cannot carry file attachments.

Every `.bbl` here is produced byte-for-byte by the generator next to it, so the
files are reproducible without trusting this directory:

| file | bytes | generator | what it shows |
|---|---:|---|---|
| `modeflags.bbl` | 338 | `gen2.py` | S frame with `flightModeFlags = 0x01000001`; default output says `ANGLE_MODE` |
| `plain.bbl` | 201 | `gen.py` | clean control, no event frame |
| `event15_disarm.bbl` | 204 | `gen.py` | DISARM event 15, reason 4 — silently dropped |
| `event30_flightmode.bbl` | 208 | `gen.py` | FLIGHTMODE event 30 — silently dropped |
| `event30_desync.bbl` | 205 | `gen.py` | unread payload byte `0x49` = `'I'`; one data row is lost |
| `event30_eoftrunc.bbl` | 206 | `gen.py` | unread payload byte `0xFF` read as EOF; rest of a valid log is lost |
| `ok_header_tiny.bbl` | 64 | `printf`, see the issue | control for the header hang |
| `hang_header_tiny.bbl` | 64 | `printf`, see the issue | one byte different; parser spins forever |

Decoder used for every result quoted in the issues:
`betaflight/blackbox-tools` at `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`.
