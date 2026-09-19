# Nestify Backend

## Digital infrastructure for property, addressing, and urban living

Nestify Backend is the production-oriented backend platform powering the
Nestify property and addressing ecosystem.

Nestify provides a digital infrastructure layer for properties, addresses,
physical address plates, property ownership, property discovery,
verification, and future property services across Africa.

This backend is designed around correctness, security, scalability,
traceability, and operational reliability.

The system supports Nestify's first production users, beginning with
landlords and property managers, while creating the foundation for future
expansion into property management, reservations, location intelligence,
government services, logistics, utilities, and smart-city infrastructure.

---

## 1. Project vision

Traditional property systems often treat a property as a collection of
separate pieces of information:

- A physical building
- An owner or landlord
- A location
- An address
- Property documents
- Rental information
- Tenants
- Listings
- External identification systems

Nestify connects these components through a persistent digital property
identity.

At the center of the system is the Nestify Property.

A property can include:

- A unique internal database identity
- A Nestify property identity
- A digital address
- A physical location
- A physical Address Plate
- One or more units
- A landlord or property manager
- Listings
- Media
- Verification records
- Historical activity
- Future integrations with external infrastructure

The backend maintains the relationships between these components.

---

## 2. Core objective

The first production objective is:

> Allow a legitimate landlord or authorized property manager to securely
> register and manage a property while ensuring that every Nestify Address
> Plate can be uniquely registered, activated, verified, and permanently
> associated with the correct property.

The system must prevent:

- One plate being assigned to multiple active properties
- One property having multiple conflicting primary plates
- Unauthorized users registering another person's property
- Duplicate property identities
- Invalid plate activations
- Location information being silently changed
- Activation occurring without an audit trail
- Partial database transactions
- Deleted records destroying important historical information

---

## 3. Product scope

The backend will initially support these major domains.

### 3.1 Identity and authentication

The system manages:

- User accounts
- Authentication
- Authorization
- Roles
- Sessions and tokens
- Account status
- Security-related events

Initial user types may include:

- Landlords
- Property managers
- Administrators
- Nestify staff

The authorization model ensures that users can only perform actions
permitted by role and relationship to a property.

### 3.2 Landlord management

Landlords will be able to:

- Create an account
- Complete their profile
- Register properties
- View properties they control
- Update permitted property information
- Manage property listings
- Manage property units
- View Address Plate information
- Initiate or complete supported verification processes

The backend maintains the landlord-property relationship rather than
relying only on frontend claims.

### 3.3 Property management

A Nestify property represents a physical property recognized by the
platform.

A property may contain:

- Property identity
- Address information
- Geographic coordinates
- Property type
- Ownership and management relationship
- Verification state
- Address Plate relationship
- Units
- Listings
- Media
- Activity history

The property record is the central entity connecting Nestify's property
infrastructure.

### 3.4 Address infrastructure

Nestify's addressing system creates a persistent digital identity for
physical properties.

The addressing layer separates three identities:

| Identity type | Purpose | Example |
| --- | --- | --- |
| Database identity | Internal backend identifier | property_id |
| Nestify property identity | Public-facing identity | NEST-PROP-XXXXXXXX |
| Physical plate identity | Physical plate identity | NEST-PLATE-XXXXXXXX |

These identities are related, but they are not the same thing.

---

## 4. Address plate system

The Address Plate is one of the most important infrastructure components
of Nestify.

A physical plate represents the connection between a physical building and
its digital property record.

The plate may eventually contain technologies such as:

- QR
- NFC
- Human-readable identifiers
- Other machine-readable identifiers

The plate does not replace the property's database record; it acts as a
physical gateway to that digital identity.

---

## 5. Address plate lifecycle

An Address Plate follows a controlled lifecycle.

```text
UNREGISTERED
      │
      ▼
REGISTERED
      │
      ▼
ACTIVATION REQUEST
      │
      ▼
VALIDATION
      │
      ▼
LOCATION VERIFICATION
      │
      ▼
PROPERTY CREATION / IDENTIFICATION
      │
      ▼
PLATE ↔ PROPERTY LINK
      │
      ▼
ACTIVATION RECORDED
      │
      ▼
ACTIVE
```

Possible future states include:

```text
ACTIVE
  │
  ├── SUSPENDED
  │
  ├── REPLACEMENT_PENDING
  │
  ├── DECOMMISSIONED
  │
  └── RETIRED
```

The state transitions are enforced by backend rules rather than by frontend
behavior alone.

---

## 6. Address plate activation

Address Plate activation is treated as a controlled backend operation.

A simplified activation flow is:

```text
Physical Plate
      │
      ▼
Plate Identifier
      │
      ▼
Nestify API
      │
      ▼
Validate Plate
      │
      ▼
Authenticate User
      │
      ▼
Validate Location
      │
      ▼
Create or Identify Property
      │
      ▼
Create Address
      │
      ▼
Link Plate
      │
      ▼
Record Activation
      │
      ▼
ACTIVE
```

The activation operation must be transactional. The system must not reach
states such as:

```text
Plate = ACTIVE
Property = missing
```

or:

```text
Property = created
Plate = incorrectly linked
```

or:

```text
Plate = linked
Activation history = missing
```

The backend either completes the operation or safely rolls it back.

---

## 7. Core address plate invariant

The system will enforce the core relationship below:

```text
ONE PLATE ─────── ONE ACTIVE PROPERTY

ONE PROPERTY ──── ONE PRIMARY PLATE
```

This does not mean a property can never have additional plates in the
future. The platform can distinguish between:

- Primary plate
- Secondary plate
- Replacement plate
- Historical plate

This allows evolution without corrupting historical records.

---

## 8. Property identity architecture

Nestify separates three important concepts:

```text
                    NESTIFY PROPERTY
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
       Property ID      Address       Plate ID
             │             │             │
             └─────────────┼─────────────┘
                           │
                           ▼
                    Physical Building
```

This separation is intentional. A geographic coordinate should not become
an identity, a physical plate should not become the entire property record,
and a database UUID should not be exposed as the public identity.

---

## 9. Geographic data

Properties are physical entities, so geographic information is required.

The backend will support geospatial data including:

- Latitude
- Longitude
- Geographic points
- Location accuracy
- Location verification
- Future geographic boundaries
- Future geospatial indexing

The system uses PostGIS where appropriate for spatial data.

Coordinates alone do not prove ownership or authority over a property.

---

## 10. Property verification

Property verification is designed as a separate domain from property
creation.

Creating a property record does not automatically mean Nestify has verified
all claims associated with it.

The system may eventually support multiple verification methods:

- Location verification
- Plate verification
- Landlord verification
- Property manager verification
- Documentation
- Staff verification
- External data sources
- Government integrations
- Community or operational verification

Verification events are recorded independently so the system maintains an
auditable history.

---

## 11. Core database entities

The initial architecture is expected to include:

```text
users
landlords
properties
property_addresses
address_plates
plate_activations
property_verifications
units
listings
property_media
bookings
audit_logs
```

These entities will evolve through deliberate database migrations rather
than uncontrolled schema changes.

---

## 12. Relationships

The conceptual relationship between the major entities is:

```text
USER
 │
 └── LANDLORD
       │
       └── PROPERTY
             │
             ├── PROPERTY ADDRESS
             │
             ├── ADDRESS PLATE
             │
             ├── UNITS
             │
             ├── LISTINGS
             │
             ├── MEDIA
             │
             ├── VERIFICATIONS
             │
             └── AUDIT HISTORY
```

A landlord may manage multiple properties. A property may contain multiple
units and listings. A physical Address Plate is linked to a property's
digital identity through controlled backend operations.

---

## 13. Technology stack

The backend will initially use:

| Technology | Purpose |
| --- | --- |
| Python | Primary programming language |
| FastAPI | REST API framework |
| PostgreSQL | Primary relational database |
| PostGIS | Geospatial data |
| SQLAlchemy | Database ORM |
| Alembic | Database migrations |
| Pydantic | Data validation |
| pytest | Automated testing |
| Docker | Development and deployment environment |
| Git | Version control |
| GitHub | Source control and collaboration |

Additional technologies should be introduced only when they solve a
clear architectural requirement.

---

## 14. Architectural principles

### 14.1 Database integrity

Important business rules must be enforced at the database level wherever
possible.

Examples:

- Unique identifiers
- Foreign keys
- Required relationships
- Unique constraints
- Valid states
- Referential integrity

The application should not be the only layer protecting critical data.

### 14.2 Transactional operations

Operations that modify multiple related records must use database
transactions.

Example:

```text
Create Property
+
Create Address
+
Link Plate
+
Record Activation
```

This should be treated as one logical operation when appropriate.

### 14.3 Explicit state machines

Important entities such as Address Plates and verification records use
explicit states.

The backend defines which transitions are legal. For example:

```text
UNREGISTERED → REGISTERED
REGISTERED → ACTIVATION_PENDING
ACTIVATION_PENDING → ACTIVE
```

An invalid transition such as UNREGISTERED → ACTIVE should not be silently
accepted when intermediate validation is required.

### 14.4 Auditability

Important changes should be traceable.

The system maintains audit information for relevant operations such as:

- Property creation
- Plate registration
- Plate activation
- Property updates
- Verification
- Administrative actions
- Relationship changes

The purpose is to answer:

```text
Who?
What?
When?
Which record?
What changed?
Why?
```

---

## 15. Security principles

Security is considered from the beginning, not as an afterthought.

The backend implements controls for:

- Authentication
- Authorization
- Password security
- Token security
- Input validation
- Rate limiting
- Secure configuration
- Secret management
- Database permissions
- API error handling
- Logging
- Audit trails
- Resource ownership checks

Sensitive information should not be stored unnecessarily. Secrets must not
be committed to Git, and environment-specific configuration should be kept
separate from application code.

---

## 16. API design

The API is versioned.

The initial API structure follows a pattern similar to:

```text
/api/v1/
```

Example resource structure:

```text
/api/v1/auth
/api/v1/users
/api/v1/landlords
/api/v1/properties
/api/v1/plates
/api/v1/verifications
```

Responses should be predictable and machine-readable, and errors should be
useful without exposing internal implementation details.

---

## 17. Project structure

The backend follows a modular architecture.

The intended structure evolves toward:

```text
nestify-backend/
│
├── app/
│   ├── main.py
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── api/
│   ├── services/
│   └── repositories/
│
├── tests/
├── migrations/
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

The final structure may differ if implementation experience demonstrates a
better organization.

---

## 18. Separation of responsibilities

The backend separates distinct responsibilities.

### API layer

Responsible for:

- HTTP requests
- Authentication dependencies
- Request validation
- Response formatting

### Service layer

Responsible for:

- Business logic
- Workflows
- State transitions
- Transactions

### Repository and data access layer

Responsible for:

- Database operations
- Queries
- Persistence

### Models

Responsible for:

- Database representation
- Relationships
- Constraints

### Schemas

Responsible for:

- Input validation
- Output serialization
- API contracts

This separation makes the system easier to test, maintain, and extend.

---

## 19. Testing strategy

Testing is part of implementation, not an optional final step.

The system includes multiple levels of tests.

### Unit tests

Test individual pieces of business logic.

Example:

```text
Can this plate transition from REGISTERED to ACTIVE?
```

### Integration tests

Test interactions between application components and the database.

Example:

```text
Can a landlord register a property successfully?
```

### Workflow tests

Test complete business operations.

Example:

```text
Register plate
→ authenticate landlord
→ verify location
→ create property
→ link plate
→ record activation
→ return active property
```

### Security tests

Test authorization and ownership boundaries.

Example:

```text
Landlord A cannot modify Landlord B's property.
```

---

## 20. Database migrations

Database schema changes are managed using Alembic.

The database should never be modified manually in production as the normal
workflow.

Schema changes follow:

```text
Code Change
     ↓
Migration
     ↓
Migration Review
     ↓
Testing
     ↓
Deployment
```

This ensures environments can be reproduced consistently.

---

## 21. Environment configuration

The application supports separate environments.

At minimum:

```text
Development
Testing
Staging
Production
```

Environment-specific secrets and configuration must not be hard-coded.

Example values may include:

```text
DATABASE_URL
SECRET_KEY
ENVIRONMENT
CORS_ORIGINS
```

The actual environment configuration is documented separately from secret
values.

---

## 22. Production requirements

Before the backend is considered production-ready, it should have:

- PostgreSQL
- Database migrations
- Secure authentication
- Authorization
- Input validation
- Structured error handling
- Logging
- Audit logging
- Automated tests
- API documentation
- Environment configuration
- Database backups
- Health checks
- Security controls
- Transactional workflows
- Monitoring strategy
- Deployment process
- Staging environment

Production readiness means more than successfully running the API locally.

---

## 23. Reliability requirements

The backend should avoid inconsistent states.

Examples of operations requiring careful handling include:

### Address Plate Activation

```text
Validate
→ Verify
→ Create/identify property
→ Link
→ Record event
```

### Property Registration

```text
Authenticate
→ Validate landlord
→ Validate property information
→ Create property
→ Create address
→ Record ownership/management relationship
```

### Plate Replacement

```text
Identify existing plate
→ Validate replacement authority
→ Retire/deactivate old plate
→ Register replacement
→ Link replacement
→ Record history
```

These workflows should be implemented as controlled transactions.

---

## 24. Idempotency

Certain operations may be repeated because of:

- Network failures
- Browser retries
- Mobile retries
- API clients retrying requests
- Users accidentally submitting forms twice

The backend should therefore make critical operations idempotent where
appropriate.

For example, sending the same valid activation request twice should not
create two properties or activate the same plate twice.

---

## 25. Data lifecycle

The system distinguishes between:

```text
Active
Inactive
Archived
Deleted
```

Not every record should be physically deleted.

For important infrastructure records, historical information may need to
remain available for:

- Auditing
- Security
- Troubleshooting
- Analytics
- Compliance
- Property history

Soft deletion or archival is used where appropriate.

---

## 26. Address plate and property relationship

The core relationship is:

```text
             PHYSICAL WORLD
                    │
                    ▼
             ADDRESS PLATE
                    │
                    ▼
             NESTIFY SYSTEM
                    │
                    ▼
               PROPERTY ID
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       ADDRESS             PROPERTY
                              │
                   ┌──────────┼──────────┐
                   ▼          ▼          ▼
                 Units     Listings    Media
```

This keeps the physical plate from becoming the entire source of truth.

---

## 27. Future expansion

The initial backend is designed so that additional capabilities can be added
without rebuilding the core property identity system.

Future domains may include:

### Property management

- Tenant management
- Maintenance
- Property operations
- Rent management
- Owner dashboards

### Consumer marketplace

- Property discovery
- Reservations
- Rentals
- Short stays
- Long-term rentals

### Location intelligence

- Geographic analytics
- Property density
- Movement patterns
- Urban data
- Spatial intelligence

#### Infrastructure

- Digital property identity
- Addressing
- Smart buildings
- Utility integrations

#### Government and institutional integrations

- Property verification
- Tax-related infrastructure
- Regulatory services
- Planning
- Public infrastructure

#### Logistics

- Delivery addressing
- Emergency response
- Location-based services

These systems build on the core property identity rather than replacing it.

---

## 28. Development workflow

Development follows a controlled sequence.

```text
Architecture
     ↓
Project Foundation
     ↓
Database Design
     ↓
Database Implementation
     ↓
Authentication
     ↓
Landlord Onboarding
     ↓
Property Registration
     ↓
Address Infrastructure
     ↓
Address Plate Registration
     ↓
Address Plate Activation
     ↓
Verification
     ↓
Listings
     ↓
Testing
     ↓
Security Hardening
     ↓
Deployment
```

Each major stage should be verified before the next begins.

---

## 29. Definition of done

A feature is not complete simply because its endpoint works.

A production feature generally satisfies:

```text
Code
+
Validation
+
Database Integrity
+
Authorization
+
Error Handling
+
Tests
+
Documentation
```

For critical workflows:

```text
Code
+
Transaction Safety
+
Auditability
+
Idempotency
+
Security
+
Tests
```

---

## 30. Initial production target

The first production target is not to build every Nestify feature.

The initial objective is to build a reliable infrastructure capable of
safely supporting the first group of real landlords and properties.

The first production system should reliably support:

```text
User
  ↓
Landlord
  ↓
Property
  ↓
Address
  ↓
Address Plate
  ↓
Activation
  ↓
Verification
  ↓
Property Management
```

Once this foundation is reliable, additional Nestify services can be built
on top of it.

---

## 31. Engineering philosophy

Nestify's backend follows these principles:

### Build for correctness first

A fast system with incorrect property relationships is worse than a slower
system with reliable data.

### Make important rules explicit

Critical business logic should not exist only as assumptions in frontend
code.

### Protect the database

The database is a core source of truth and must enforce important integrity
rules.

### Keep infrastructure modular

New Nestify services should build on the property identity layer.

### Preserve history

Properties and infrastructure can change over time. The system should be
capable of representing that history.

### Design for real-world failure

Networks fail. Users retry requests. Devices disconnect. Operations are
interrupted. The backend must be designed accordingly.

### Security is part of architecture

Authentication, authorization, validation, auditing, and secure
configuration are foundational concerns.

---

## 32. Project status

This repository represents a new implementation of the Nestify backend.

It is intentionally developed separately from earlier Nestify and Address
Plate prototypes so the architecture can be evaluated independently.

The implementation proceeds incrementally.

Current development stages:

- [ ] Architecture
- [ ] Project foundation
- [ ] Database architecture
- [ ] Database implementation
- [ ] Authentication
- [ ] Landlord onboarding
- [ ] Property registration
- [ ] Address system
- [ ] Address Plate registration
- [ ] Address Plate activation
- [ ] Property verification
- [ ] Listings
- [ ] Testing
- [ ] Security hardening
- [ ] Staging deployment
- [ ] Production deployment

---

## 33. Repository rule

This project should remain focused on the Nestify backend.

Frontend applications, experiments, temporary scripts, and unrelated
projects should not be added unless they directly support backend
development.

Production secrets must never be committed.

Examples:

```text
.env
database passwords
API keys
private tokens
JWT secrets
cloud credentials
```

Use .env.example to document required configuration variables without
exposing their values.

---

## 34. Final objective

The ultimate purpose of this backend is to establish a reliable digital
infrastructure layer connecting:

```text
PEOPLE
   │
   ▼
LANDLORDS
   │
   ▼
PROPERTIES
   │
   ▼
ADDRESSES
   │
   ▼
PHYSICAL ADDRESS PLATES
   │
   ▼
DIGITAL PROPERTY IDENTITIES
   │
   ▼
NESTIFY SERVICES
   │
   ├── Property Management
   ├── Rentals
   ├── Reservations
   ├── Location Intelligence
   ├── Infrastructure
   ├── Government Services
   └── Smart-City Services
```

The backend is not merely an API for a website. It is the core
infrastructure layer for Nestify's property and addressing platform.

---

## License

This project is proprietary software belonging to Nestify.

The license and commercial usage terms are defined separately.

---

## Maintainer

Nestify

Backend development is being carried out as part of the Nestify platform.
