# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.x     | ✅ Yes              |

Only the latest minor release on each major version receives security fixes.
Pin to a specific minor version in production and update promptly when patches
are released.

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Security issues in SocketSpec should be reported privately so that a fix can be
prepared and released before the vulnerability is publicly disclosed.

### Contact

Email: **its.laiba.shahab@email.com**

Please use the subject line: `[SECURITY] SocketSpec — <short description>`

### What to Include

Your report should contain as much of the following as possible:

- **Description** — a clear explanation of the vulnerability
- **Steps to reproduce** — minimal code or curl commands to trigger the issue
- **Impact assessment** — what an attacker could achieve (e.g. auth bypass,
  arbitrary code execution, denial of service)
- **Affected versions** — which versions of SocketSpec are affected
- **Suggested fix** — if you have one (optional but appreciated)

### What to Expect

| Timeline | Action |
|---|---|
| Within 48 hours | Acknowledgement of your report |
| Within 7 days | Initial assessment and severity classification |
| Within 30 days | Fix developed and tested |
| Coordinated | Public disclosure after patch release |

We follow a coordinated disclosure model. Once a fix is released we will publish
a security advisory on the GitHub repository and credit the reporter (unless you
prefer to remain anonymous).

---

## Scope

The following are **in scope**:

- Authentication bypass in `JWTAuth` or `APIKeyAuth`
- Origin validation bypass in `OriginValidator`
- Privilege escalation via room guards
- Denial of service via payload size or rate limit bypass
- Arbitrary code execution in any code path

The following are **out of scope**:

- Vulnerabilities in third-party dependencies (report to the dependency
  maintainer directly; we will update our dependency when a fix is available)
- Issues requiring physical access to the server
- Social engineering

---

## Preferred Languages

Reports may be submitted in English or Urdu.
