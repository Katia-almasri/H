# Project Instructions

## Spec-driven development

This project is Harvest, a UAE-regulated fractional real estate investment
platform. For every task, first read and follow:

- `steering/product.md`
- `steering/structure.md`
- `steering/tech.md`
- the feature-specific requirements file, when one exists, at
  `.kiro/specs/<feature>/requirements.md`

Rules:

1. Never implement behavior that is not traceable to a steering rule or a
   feature requirement.
2. Use `steering/product.md` for domain context, regulatory constraints,
   security rules, API contract rules, and active sprint scope.
3. Follow the architecture in `steering/structure.md` exactly. Do not introduce
   new patterns without flagging the change first.
4. Follow the runtime, dependency, persistence, security, and testing choices in
   `steering/tech.md`.
