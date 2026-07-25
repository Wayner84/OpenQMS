# Products

**Status: Planned.** Not yet implemented — targeted for
[Milestone 3](../Roadmap.md#m3-products-and-suppliers). No code exists for this
module yet; see [docs/CurrentStatus.md](../CurrentStatus.md).

## Purpose

Central records for internal products, purchased products, assemblies and
components: part number, description, revision, images, CAD/drawing/specification
links, categories, manufacturing notes and supplier relationships, integrated with
NCR, FAIR, SPC, documents and suppliers, with future ERP integrations in mind, per
[ProductSpecification.md](../ProductSpecification.md#products).

## Planned database tables

All tables carry `organisation_id` per [Database.md](../Database.md#multi-tenancy-baseline).

- **`product_categories`** — `id`, `organisation_id`, `name`.
- **`products`** — `id`, `organisation_id`, `part_number`, `description`, `revision`,
  `category_id`, `type` (`internal` / `purchased` / `assembly` / `component`),
  `manufacturing_notes`, `created_at`, `updated_at`.
- **`product_documents`** — link table: `product_id`, `document_id` →
  [Document Management](DocumentManagement.md), `relationship_type` (`drawing` /
  `specification` / `cad`), satisfying "images, CAD/drawing/specification links"
  without duplicating file storage.
- **`product_supplier_links`** — `product_id`, `supplier_id` →
  [Suppliers](Suppliers.md), `is_preferred` (bool).

## Planned APIs

Under `/api/v1/products`:

- `GET/POST /api/v1/products`, `GET/PATCH/DELETE /api/v1/products/{id}` — CRUD,
  filterable by category, type, part number.
- `GET/POST /api/v1/products/{id}/documents` — attach/list linked drawings/specs.
- `GET/POST /api/v1/products/{id}/suppliers` — attach/list linked suppliers.
- `GET /api/v1/products?search=` — search by part number/description.

## Workflow

Create a product record → attach drawings/specifications/CAD links (via
[Document Management](DocumentManagement.md)) → link approved suppliers → the product
is then referenced (not duplicated) by NCR, FAIR and SPC records raised against it.
Revisions are tracked on the product record itself; a revision change is expected to
prompt review of linked documents' currency (exact mechanism to be designed during
implementation).

## Relationships to other modules

Per [ProductSpecification.md](../ProductSpecification.md#module-relationships):

- **Products link to NCR, FAIR, SPC and documents.** [NCR](NCR.md), [FAIR](FAIR.md)
  and [SPC](SPC.md) records reference `products.id`.
- Products link to [Suppliers](Suppliers.md) via `product_supplier_links`.
- Future ERP integrations are anticipated in the data model (part number as a stable
  external key) but not built now — see [FutureIdeas.md](../FutureIdeas.md).

## Future improvements

- Bill-of-materials / assembly structure (parent/child product relationships).
- Image gallery beyond single document links.
- Direct ERP integration.

## Known issues / status

Planned only; no schema, API, or UI exists yet. Depends on
[Document Management](DocumentManagement.md) existing first for drawing/spec links to
be meaningful (see [Roadmap.md](../Roadmap.md)).

## Related documents

- [Roadmap.md](../Roadmap.md#m3-products-and-suppliers)
- [Suppliers.md](Suppliers.md)
- [NCR.md](NCR.md)
