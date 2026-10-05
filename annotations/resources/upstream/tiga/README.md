# Kenya Geospatial Data

Kenya administrative boundary data (counties, constituencies, wards) with PostGIS and SpatiaLite geometry support via Drizzle ORM. Targets PostgreSQL, PGlite (in-browser WASM Postgres), Cloudflare D1, and SQLite/SpatiaLite.

**Data source:** [Kenya Elections — Humanitarian Data Exchange](https://data.humdata.org/dataset/kenya-elections)

Source shapefiles are not committed to the repo. A download script fetches them on demand from humdata.org.

## Data overview

| Level          | Records | Geometry       | Source CRS |
|----------------|---------|----------------|------------|
| Counties       | 47      | MultiPolygon   | EPSG:4326 (WGS84) |
| Constituencies | 290     | MultiPolygon   | EPSG:4326 (WGS84) |
| Wards          | 1,450   | Polygon / MultiPolygon | EPSG:3857 (Web Mercator) |

The ward shapefile is in **EPSG:3857** (Google Maps Global Mercator — coordinates in meters, not degrees). Counties and constituencies are already in WGS84. The extract script reprojects ward coordinates from 3857 to 4326 at extraction time, so all output GeoJSON files are in **EPSG:4326 (WGS84)**.

## Schema

Tables use the `kenya_` prefix. Foreign keys reference `id` (not `code`), matching the consuming project's schema:

```
kenya_counties (47)
├── kenya_constituencies (290)     FK → kenya_counties.id
│   └── kenya_wards (1,450)        FK → kenya_constituencies.id
├── kenya_governors                FK → kenya_counties.id, kenya_parties.id
├── kenya_mps                      FK → kenya_constituencies.id, kenya_parties.id
└── kenya_mcas                     FK → kenya_wards.id, kenya_parties.id

kenya_parties
```

PG schema (`src/schema/pg.ts`) uses `geometry(MultiPolygon, 4326)` via a Drizzle `customType` — workaround for [drizzle-orm#3040](https://github.com/drizzle-team/drizzle-orm/issues/3040).

D1 schema (`src/schema/d1.ts`) mirrors PG exactly but stores geometry as `text` (GeoJSON string). This means pulling rows from D1 into PGlite requires only `ST_GeomFromGeoJSON(text)` — no hacks, the data feels native to PostGIS.

SpatiaLite schema (`src/schema/spatialite.ts`) mirrors PG table and column names but stores geometry as `BLOB` (SpatiaLite's native binary format). Table creation and geometry column registration are handled via raw SQL using `AddGeometryColumn` and `CreateSpatialIndex`, while the Drizzle schema provides type safety for non-spatial queries.

## Prerequisites

- **Node.js** >= 18
- **pnpm** (see `packageManager` in package.json)
- **PostgreSQL** with PostGIS extension (for PG target)
- **libspatialite** (`mod_spatialite`) for the SpatiaLite target

```bash
pnpm install
```

## Environment

Create a `.env` file:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/mzalendo
PGLITE_DATA_URL=./src/data/.pglite
SPATIALITE_DB_PATH=./src/data/spatialite.db   # optional, defaults to src/data/spatialite.db
SPATIALITE_PATH=mod_spatialite                # optional, full path if not on library path
```

## Quick start

### 1. Download source shapefiles

Fetches county, constituency, and ward boundary shapefiles from [humdata.org](https://data.humdata.org/dataset/kenya-elections) and unzips them into `src/data/source/`:

```bash
pnpm download-source
```

### 2. Extract clean data

Reads the downloaded shapefiles, reprojects ward coordinates from EPSG:3857 to WGS84, and outputs clean JSON and GeoJSON to `src/data/{counties,constituencies,wards}/`:

```bash
pnpm extract-data
```

### 3. Choose a database target

---

### PostgreSQL (remote/local)

Requires a running Postgres instance with PostGIS.

```bash
psql -U postgres -c "CREATE DATABASE mzalendo;"
psql -U postgres -d mzalendo -c "CREATE EXTENSION IF NOT EXISTS postgis;"

pnpm pg:push       # Push schema directly (or pg:generate for migrations)
pnpm pg:seed       # Seed counties, constituencies, wards
pnpm pg:studio     # Browse data in Drizzle Studio
```

---

### PGlite (embedded, no server)

Uses an in-process WASM Postgres via `@electric-sql/pglite`. Data stored in `src/data/.pglite/`.

```bash
pnpm pglite:generate:custom   # Generate PostGIS extension migration
# Edit the generated file to contain: CREATE EXTENSION IF NOT EXISTS postgis;

pnpm pglite:generate           # Generate schema migration
pnpm pglite:migrate            # Run all migrations
pnpm pglite:seed               # Seed data
pnpm pglite:studio             # Browse data
```

---

### Cloudflare D1 (local SQLite)

Uses `better-sqlite3` to seed a local D1-compatible database at `src/data/d1-local.db`. Geometry is stored as GeoJSON text — identical column structure to PG so rows can be pulled directly into PGlite.

```bash
pnpm d1:generate    # Generate migrations
pnpm d1:seed        # Seed the local D1 database
pnpm d1:export      # Export as SQL for wrangler d1 execute
```

---

### SQLite / SpatiaLite (local, native spatial)

Uses `better-sqlite3` with the `mod_spatialite` extension. Geometry is stored as SpatiaLite binary blobs with spatial indexes — full spatial query support (`ST_Contains`, `ST_Distance`, etc.) without needing a Postgres server.

**Install SpatiaLite** (if not already):

```bash
# Ubuntu / Debian
sudo apt install libsqlite3-mod-spatialite

# macOS (Homebrew)
brew install libspatialite

# Arch
sudo pacman -S libspatialite
```

If `mod_spatialite` is not on the default library path, set `SPATIALITE_PATH` to the full path of the shared object (e.g. `SPATIALITE_PATH=/usr/lib/x86_64-linux-gnu/mod_spatialite.so`).

```bash
pnpm spatialite:seed      # Create DB, init tables, seed all data
pnpm spatialite:rebuild   # Rebuild better-sqlite3 native addon (if needed)
```

The seed script creates `src/data/spatialite.db`, initializes SpatiaLite metadata (`InitSpatialMetaData`), creates tables with geometry columns registered via `AddGeometryColumn`, builds spatial indexes via `CreateSpatialIndex`, and inserts all boundary data using `SetSRID(GeomFromGeoJSON(...), 4326)`.

To verify the seed:

```bash
npx tsx src/seed/verify-spatialite.ts
```

## D1 → PGlite data flow

D1 has no spatial functions, so geometry is stored as plain GeoJSON text. When pulling rows into PGlite for spatial queries in the browser:

```sql
INSERT INTO kenya_wards (ward_code, name, constituency_id, geometry)
SELECT
  ward_code,
  name,
  constituency_id,
  ST_GeomFromGeoJSON(geometry)
FROM d1_import;
```

Because the extract step already outputs WGS84 coordinates and the geometry column is a valid GeoJSON `MultiPolygon` string, `ST_GeomFromGeoJSON` produces a native PostGIS geometry with SRID 4326 — no `ST_Transform`, no coordinate conversion, no hacks.

## Project structure

```
src/
├── data/
│   ├── extract/
│   │   ├── download-source.ts    # Downloads shapefiles from humdata.org
│   │   ├── run.ts                # Shapefile → GeoJSON (with ward reprojection)
│   │   └── types.ts              # GeoJSON type definitions
│   ├── source/                   # Downloaded shapefiles (gitignored)
│   ├── counties/                 # Extracted counties.json + counties.geojson
│   ├── constituencies/           # Extracted constituencies.json + constituencies.geojson
│   └── wards/                    # Extracted wards.json + wards.geojson
│
├── schema/
│   ├── pg.ts                     # PostGIS schema (kenya_* tables + relations)
│   ├── d1.ts                     # D1/SQLite schema (mirrors PG, text geometry)
│   └── spatialite.ts             # SpatiaLite schema (mirrors PG, BLOB geometry)
│
├── db/
│   ├── pg.ts                     # node-postgres Drizzle client
│   ├── pglite.ts                 # PGlite Drizzle client
│   ├── neon.ts                   # Neon serverless Drizzle client
│   └── run-pglite-migrations.ts  # PGlite migration runner
│
├── seed/
│   ├── helpers.ts                # Shared: readGeoJSON, toMultiPolygon, batchInsert
│   ├── pg/                       # PG seed (counties → constituencies → wards)
│   ├── d1/                       # D1 seed (same flow, text geometry)
│   ├── spatialite/               # SpatiaLite seed (native binary geometry)
│   │   ├── init-tables.ts        # Raw SQL table creation + AddGeometryColumn
│   │   ├── run.ts                # Seed orchestrator
│   │   ├── seed-counties.ts
│   │   ├── seed-constituencies.ts
│   │   └── seed-wards.ts
│   ├── run-pg.ts                 # Entry: seed node-postgres
│   ├── run-pglite.ts             # Entry: seed PGlite
│   ├── run-d1-local.ts           # Entry: seed local D1
│   ├── run-spatialite.ts         # Entry: seed SpatiaLite
│   ├── verify-spatialite.ts      # Sanity checks against SpatiaLite DB
│   └── export-sql.ts             # Export D1 data as SQL for wrangler deploy
│
└── drizzle/
    ├── pg/                       # Generated PG migrations
    ├── pglite/                   # Generated PGlite migrations
    └── d1/                       # Generated D1 migrations
```

## Scripts reference

| Script                    | Description                                          |
|---------------------------|------------------------------------------------------|
| `pnpm download-source`    | Download shapefiles from humdata.org                 |
| `pnpm extract-data`       | Convert shapefiles to clean GeoJSON (reprojects wards) |
| `pnpm pg:push`            | Push schema to PostgreSQL (no migration files)       |
| `pnpm pg:generate`        | Generate PG migration SQL                            |
| `pnpm pg:seed`            | Seed PostgreSQL with all boundary data               |
| `pnpm pg:studio`          | Open Drizzle Studio for PostgreSQL                   |
| `pnpm pglite:generate`    | Generate PGlite migration SQL                        |
| `pnpm pglite:migrate`     | Run PGlite migrations                                |
| `pnpm pglite:seed`        | Seed PGlite with all boundary data                   |
| `pnpm pglite:studio`      | Open Drizzle Studio for PGlite                       |
| `pnpm d1:generate`        | Generate D1 migration SQL                            |
| `pnpm d1:seed`            | Seed local D1 SQLite database                        |
| `pnpm d1:export`          | Export D1 data as SQL for wrangler deploy             |
| `pnpm spatialite:seed`    | Create and seed SpatiaLite database                  |
| `pnpm spatialite:rebuild` | Rebuild better-sqlite3 native addon                  |
| `pnpm test`               | Run tests in watch mode                              |
| `pnpm test:run`           | Run tests once                                       |
| `pnpm test:coverage`      | Run tests with coverage                              |

## Verify seed (raw SQL sanity checks)

Quick queries to confirm the seed worked. Drop these into `psql` or Drizzle Studio:

```sql
-- Row counts
SELECT 'counties' AS t, count(*) FROM kenya_counties
UNION ALL SELECT 'constituencies', count(*) FROM kenya_constituencies
UNION ALL SELECT 'wards', count(*) FROM kenya_wards;

-- Nairobi CBD (-1.286389, 36.817223) → should be Nairobi Central ward, Starehe constituency, Nairobi county
SELECT w.ward_code, w.name AS ward, c.name AS constituency, co.name AS county,
  round(ST_Distance(w.geometry::geography, ST_SetSRID(ST_MakePoint(36.817223, -1.286389), 4326)::geography)::numeric, 0) AS distance_m
FROM kenya_wards w
JOIN kenya_constituencies c ON c.id = w.constituency_id
JOIN kenya_counties co ON co.id = c.county_id
WHERE ST_DWithin(w.geometry::geography, ST_SetSRID(ST_MakePoint(36.817223, -1.286389), 4326)::geography, 1000)
ORDER BY distance_m
LIMIT 3;

-- Kiambu Town (-1.1697, 36.8295) → should be Riabai ward, Kiambu constituency, Kiambu county
SELECT w.ward_code, w.name AS ward, c.name AS constituency, co.name AS county,
  round(ST_Distance(w.geometry::geography, ST_SetSRID(ST_MakePoint(36.8295, -1.1697), 4326)::geography)::numeric, 0) AS distance_m
FROM kenya_wards w
JOIN kenya_constituencies c ON c.id = w.constituency_id
JOIN kenya_counties co ON co.id = c.county_id
WHERE ST_DWithin(w.geometry::geography, ST_SetSRID(ST_MakePoint(36.8295, -1.1697), 4326)::geography, 1000)
ORDER BY distance_m
LIMIT 3;

-- Kalama Area (-1.6725, 37.2529) → should be Kiima Kiu/Kalanzoni ward, Kilome constituency, Makueni county
SELECT w.ward_code, w.name AS ward, c.name AS constituency, co.name AS county,
  round(ST_Distance(w.geometry::geography, ST_SetSRID(ST_MakePoint(37.2529, -1.6725), 4326)::geography)::numeric, 0) AS distance_m
FROM kenya_wards w
JOIN kenya_constituencies c ON c.id = w.constituency_id
JOIN kenya_counties co ON co.id = c.county_id
WHERE ST_DWithin(w.geometry::geography, ST_SetSRID(ST_MakePoint(37.2529, -1.6725), 4326)::geography, 1000)
ORDER BY distance_m
LIMIT 3;
```

If wards are in the wrong CRS, distance values will be wildly off (millions of meters) and containment checks will return zero rows.

## Verify seed — SpatiaLite sanity checks

Run the verification script:

```bash
npx tsx src/seed/verify-spatialite.ts
```

Or manually via the `sqlite3` CLI with SpatiaLite loaded:

```bash
sqlite3 src/data/spatialite.db
```

```sql
.load mod_spatialite

-- Row counts
SELECT 'counties' AS t, count(*) AS c FROM kenya_counties
UNION ALL SELECT 'constituencies', count(*) FROM kenya_constituencies
UNION ALL SELECT 'wards', count(*) FROM kenya_wards;

-- Nairobi CBD → nearest wards (geodesic distance in meters)
SELECT w.ward_code, w.name AS ward, c.name AS constituency, co.name AS county,
  CAST(ST_Distance(w.geometry, MakePoint(36.817223, -1.286389, 4326), 1) AS INTEGER) AS distance_m
FROM kenya_wards w
JOIN kenya_constituencies c ON c.id = w.constituency_id
JOIN kenya_counties co ON co.id = c.county_id
WHERE ST_Distance(w.geometry, MakePoint(36.817223, -1.286389, 4326), 1) < 2000
ORDER BY distance_m
LIMIT 3;

-- Containment check
SELECT w.ward_code, w.name AS ward
FROM kenya_wards w
WHERE ST_Contains(w.geometry, MakePoint(36.817223, -1.286389, 4326));

-- GeoJSON export
SELECT name, AsGeoJSON(geometry) AS geojson
FROM kenya_wards WHERE ward_code = '1439';
```

SpatiaLite uses `MakePoint(lng, lat, srid)` instead of PostGIS's `ST_SetSRID(ST_MakePoint(...), ...)`. The third argument to `ST_Distance` (`1`) enables geodesic distance in meters on the WGS84 ellipsoid.

## Spatial queries with Drizzle

PostGIS functions work directly in Drizzle's `sql` template literals. Because the query references the actual schema columns (`kenyaWards.geometry`, `kenyaWards.constituencyId`, etc.), return types stay inferred — no manual typecasting or string-literal type divergence.

### Find nearest wards to a coordinate

```typescript
import { sql, eq } from "drizzle-orm";
import { kenyaWards, kenyaConstituencies, kenyaCounties } from "./schema/pg.js";

const lat = -1.2921;
const lng = 36.8219;
const point = sql`ST_SetSRID(ST_Point(${lng}, ${lat}), 4326)`;

const nearest = await db
  .select({
    id: kenyaWards.id,
    wardCode: kenyaWards.wardCode,
    name: kenyaWards.name,
    constituencyId: kenyaWards.constituencyId,
    subCounty: kenyaWards.subCounty,
    constituency: kenyaConstituencies.name,
    constituencyCode: kenyaConstituencies.code,
    county: kenyaCounties.name,
    countyCode: kenyaCounties.code,
    distance:
      sql<number>`ST_Distance(${kenyaWards.geometry}::geography, ${point}::geography)`.as(
        "distance",
      ),
    geojson:
      sql<string>`ST_AsGeoJSON(ST_SimplifyPreserveTopology(${kenyaWards.geometry}, 0.001))`.as(
        "geojson",
      ),
  })
  .from(kenyaWards)
  .innerJoin(kenyaConstituencies, eq(kenyaWards.constituencyId, kenyaConstituencies.id))
  .innerJoin(kenyaCounties, eq(kenyaConstituencies.countyId, kenyaCounties.id))
  .orderBy(sql`ST_Distance(${kenyaWards.geometry}::geography, ${point}::geography)`)
  .limit(5);
```

`distance` is typed `number` and `geojson` is typed `string` at compile time. The join columns (`constituencyId`, `countyId`) resolve through the schema's FK references, so a column rename in the schema propagates through every query that uses it.

### Containment check

```typescript
const containing = await db
  .select({
    id: kenyaWards.id,
    name: kenyaWards.name,
    wardCode: kenyaWards.wardCode,
  })
  .from(kenyaWards)
  .where(sql`ST_Contains(${kenyaWards.geometry}, ${point})`);
```

### Raw SQL equivalent (for reference)

```sql
SELECT * FROM kenya_wards
WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(36.8219, -1.2921), 4326));

SELECT *, ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(36.8219, -1.2921), 4326)::geography) AS distance_m
FROM kenya_wards
ORDER BY distance_m
LIMIT 5;
```

## SpatiaLite spatial queries (raw SQL via better-sqlite3)

SpatiaLite uses slightly different function names than PostGIS. Since geometry is stored as native SpatiaLite binary (not text), spatial indexes and functions work out of the box.

### Nearest wards

```typescript
import Database from "better-sqlite3";

const sqlite = new Database("src/data/spatialite.db");
sqlite.loadExtension("mod_spatialite");

interface WardResult {
  ward_code: string;
  ward: string;
  constituency: string;
  county: string;
  distance_m: number;
}

const lng = 36.8219;
const lat = -1.2921;

const nearest = sqlite
  .prepare(
    `SELECT w.ward_code, w.name AS ward, c.name AS constituency, co.name AS county,
       CAST(ST_Distance(w.geometry, MakePoint(?, ?, 4326), 1) AS INTEGER) AS distance_m
     FROM kenya_wards w
     JOIN kenya_constituencies c ON c.id = w.constituency_id
     JOIN kenya_counties co ON co.id = c.county_id
     WHERE ST_Distance(w.geometry, MakePoint(?, ?, 4326), 1) < 5000
     ORDER BY distance_m
     LIMIT 5`,
  )
  .all(lng, lat, lng, lat) as WardResult[];
```

### Containment check

```typescript
interface ContainmentResult {
  ward_code: string;
  ward: string;
}

const containing = sqlite
  .prepare(
    `SELECT w.ward_code, w.name AS ward
     FROM kenya_wards w
     WHERE ST_Contains(w.geometry, MakePoint(?, ?, 4326))`,
  )
  .all(lng, lat) as ContainmentResult[];
```

### GeoJSON export

```typescript
interface GeoJsonResult {
  name: string;
  geojson: string;
}

const row = sqlite
  .prepare(
    `SELECT name, AsGeoJSON(geometry) AS geojson FROM kenya_counties WHERE code = 47`,
  )
  .get() as GeoJsonResult | undefined;
```

### Key differences from PostGIS

| PostGIS                                          | SpatiaLite                              |
|--------------------------------------------------|-----------------------------------------|
| `ST_SetSRID(ST_MakePoint(lng, lat), 4326)`       | `MakePoint(lng, lat, 4326)`             |
| `ST_GeomFromGeoJSON(text)`                        | `GeomFromGeoJSON(text)`                 |
| `ST_AsGeoJSON(geom)`                              | `AsGeoJSON(geom)`                       |
| `ST_Distance(geom::geography, point::geography)`  | `ST_Distance(geom, point, 1)`           |
| Geometry stored as PostGIS binary (via WKB)       | Geometry stored as SpatiaLite BLOB      |

The `1` flag on `ST_Distance` switches from planar to geodesic (ellipsoidal) distance in meters, equivalent to the PostGIS `::geography` cast.

## Drizzle relational queries

```typescript
import { db } from "./db/pg.js";
import { kenyaCounties } from "./schema/pg.js";
import { eq } from "drizzle-orm";

const result = await db.query.kenyaCounties.findFirst({
  where: eq(kenyaCounties.name, "NAIROBI"),
  columns: { code: true, name: true },
  with: {
    constituencies: {
      columns: { code: true, name: true },
      with: {
        wards: {
          columns: { wardCode: true, name: true },
        },
      },
    },
  },
});
```
