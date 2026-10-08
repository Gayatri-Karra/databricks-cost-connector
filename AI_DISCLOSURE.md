# AI Usage Disclosure Note

As requested in the assessment deliverables, this document details how AI assistance was leveraged during the development of this project.

---

### Tools Used

- **AI Assistant:** ChatGPT

### Scope of AI Assistance

AI assistance was used as a development support tool for:
1. **Boilerplate Scaffolding:** Assisting with initial data-class structures, repetitive schema definitions, and project organization.
2. **Synthetic Test Data Generation:** Assisting with the creation and variation of synthetic JSON fixtures used for offline testing.
3. **Test Case Brainstorming:** Suggesting edge cases for test parametrization, including malformed numeric values, timestamp formats, empty API responses, and nested metadata.
4. **Debugging and Review:** Assisting with debugging, reviewing collector behavior, improving error handling, and validating the live-versus-fixture execution separation.
5. **Documentation:** Assisting with README, execution evidence, coverage documentation, and submission preparation.

### Human Engineering & Architectural Decisions

The final implementation, architectural decisions, Databricks account/workspace configuration, live execution, and verification were performed and reviewed by the developer.

Key engineering decisions included:

- **Two-Tier Control Plane Strategy:** Separating Workspace API functionality from Account API functionality so that workspace-level credentials do not cause account-level collection failures.
- **Lazy SDK Instantiation:** Preventing unnecessary network initialization during offline evaluation.
- **Strict Decimal Precision Arithmetic:** Using `decimal.Decimal` for DBU quantities and pricing calculations to avoid binary floating-point precision errors.
- **Fault-Tolerant Orchestrator:** Isolating category collectors so permission-denied, unavailable, or empty categories do not terminate the complete collection run.
- **UTC Normalization Logic:** Converting supported timestamp formats into canonical UTC ISO 8601 representation.
- **Live/Mock Separation:** Ensuring fixture data is used for mock/offline execution and is not substituted for unavailable data during live execution.

The developer reviewed and verified the final live execution results, including the 17-category coverage report and normalized output.