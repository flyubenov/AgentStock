# Product Requirement Document (PRD)
## Section 6: The Local Sandbox Alternative & Private Engine Bypass

### 1. Document Control
- **Title:** Local Sandbox Alternative & Private Engine Bypass (Low-Code/Conceptual Specification)
- **Component Owner:** Lead Software Engineer / Product Founder
- **Status:** Approved for Architectural Input
- **Target Audience:** Engineering Agents, Technical Architects, LLM Developers

---

### 2. Component Vision & Strategic Objective
The purpose of the Local Sandbox Alternative is to provide the product architect with a permanent, unrestricted, zero-cost runtime environment to access all system analytical features (Fair Value calculations, Moat evaluation matrices, Risk/Reward analysis, and batch calculations) without needing active payment structures or exposing production clouds to security bypass vectors. 

This setup decouples local analysis from public SaaS restrictions, allowing the app to run as an independent, high-powered personal analytical platform on local machines while the production branch serves public commercial users.

---

### 3. Structural Design Requirements

#### 3.1 Environment-Driven Routing Behavior
- **Context Differentiation:** The system must evaluate its execution state strictly via configuration flags prior to application initialization.
- **Local Isolation:** When configured for the sandbox environment, all external authentication filters, access checks, and paywall rules must switch off by default.
- **Operational Safety Guardrail:** The production branch configuration must include an automated check that prevents the system from launching if sandbox overrides are active. This guarantees sandbox configurations cannot be loaded on public production environments.

#### 3.2 Security Short-Circuiting & Session Mocking
- **Access Bypass:** The core authorization layer must intercept incoming client calls. If sandbox mode is validated, it must immediately grant full administrative rights, bypassing third-party authorization APIs or token lookups.
- **Identity Mocking:** The system must generate a mock data profile containing permanent, unrestricted entitlement configurations for the session. This profile is fed to the downstream analytical modules to unlock all features automatically.

#### 3.3 Dynamic Database Abstraction Requirements
- **Local Persistence Layer:** The application repository must dynamically switch its persistence target based on active configuration settings.
- **Production Mode Behavior:** The app connects to the managed, relational cloud database cluster to isolate individual customer data.
- **Sandbox Mode Behavior:** The system drops all cloud network infrastructure requirements. It maps all data modifications, watchlists, and computed metrics to a lightweight, single-file database located entirely within the local workspace directory.

---

### 4. Front-End Canvas Adaptations & Sandbox States

#### 4.1 Paywall Deactivation
- **Unrestricted Data Rendering:** All visual locking layers, payment modals, blur filters, or premium restrictions across the interface must be deactivated.
- **Calculations Transparency:** The client application must render the granular elements of every analytical module (e.g., individual valuation legs, cash flows, and moat gate thresholds) in absolute raw clarity.

#### 4.2 Environmental Status Visibility
- **Interface Badging:** When running in sandbox mode, the user interface must display a prominent, permanent visual indicator at the edge of the layout.
- **Label Text:** The text must state explicitly: "LOCAL SANDBOX ENGINE ACTIVE — UNRESTRICTED SYSTEM ACCESS MASTER KEY ENFORCED". This ensures the operator can visually confirm the decoupled context immediately.

---

### 5. Repository Management & Operational Procedures

#### 5.1 Version Control Branch Isolation
- **Pragmatic Branch Separation:** The codebase must maintain distinct operational branches:
  - **Main Branch:** Reserved exclusively for secure, production-gated client architectures where sandbox overrides are structurally prevented from executing.
  - **Sandbox Branch:** Holds local configuration files and local test scripts natively. It pulls analytical engine updates from the main branch without pushing local settings changes back upstream.
- **Asset Exclusion:** The local settings files and local database files must be explicitly ignored by version control to prevent local developer overrides from leaking online.

#### 5.2 Automated Validation Procedures
- **Pre-Deployment Scanning:** The CI/CD deployment routines must scan environmental files to verify that sandbox configurations cannot pass validation tests during artifact assembly. If a sandbox flag is found in a production build, the compilation pipeline must fail instantly.
