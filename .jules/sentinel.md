## 2024-05-13 - Prevent Exception Details Leakage in HTTP Error Responses
**Vulnerability:** Found unhandled exception messages (which could contain sensitive internal details like query formatting, library internals, database schemes, etc) being explicitly returned to end users in the HTTP Response details fields.
**Learning:** Returning `str(exc)` in production environments represents an information leakage risk that can assist attackers.
**Prevention:** Catch exception and log locally with `log.exception` or `log.error`, but return a generic string (e.g. "An internal server error occurred") to clients.
