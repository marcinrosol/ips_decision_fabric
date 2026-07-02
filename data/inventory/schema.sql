-- Chemical inventory schema for the energetics-fabric decision system.
-- Backs the live half of the agentic decision fabric (the other half is a
-- vector store of IPS pyrotechnics proceedings, queried separately).

PRAGMA foreign_keys = ON;

CREATE TABLE Chemical (
    chemical_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT NOT NULL,
    cas_number             TEXT,
    chemical_formula       TEXT,
    category               TEXT NOT NULL CHECK (category IN (
                                'Oxidizer', 'Metal Fuel', 'Fuel', 'Binder',
                                'Color Agent', 'Chlorine Donor', 'Sensitizer',
                                'Retardant', 'Buffer/Coating'
                            )),
    physical_form          TEXT,
    particle_size_microns  REAL,
    purity_percent         REAL,
    un_number              TEXT,
    hazard_class           TEXT,
    storage_class          TEXT,
    storage_location       TEXT,
    quantity_on_hand       REAL NOT NULL DEFAULT 0,
    unit_of_measure        TEXT NOT NULL DEFAULT 'kg',
    reorder_threshold      REAL NOT NULL DEFAULT 0,
    unit_cost_usd          REAL,
    supplier_name          TEXT,
    expiration_date        TEXT,
    last_inventory_check   TEXT,
    sensitivity_impact_j   REAL,
    sensitivity_friction_n REAL,
    msds_url               TEXT,
    notes                  TEXT
);

CREATE TABLE Experiment_Schedule (
    schedule_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_code        TEXT NOT NULL UNIQUE,
    title                  TEXT NOT NULL,
    objective              TEXT,
    lead_chemist           TEXT NOT NULL,
    scheduled_date         TEXT NOT NULL,
    duration_minutes       INTEGER,
    test_site              TEXT,
    risk_level             TEXT NOT NULL CHECK (risk_level IN
                                ('Low', 'Moderate', 'High', 'Severe')),
    status                 TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN (
                                'Planned', 'Approved', 'In Progress',
                                'Completed', 'Cancelled', 'Postponed'
                            )),
    approval_status        TEXT NOT NULL DEFAULT 'Pending' CHECK (approval_status IN
                                ('Pending', 'Approved', 'Rejected')),
    approved_by            TEXT,
    ips_reference_citation TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Junction table: one experiment draws on several chemicals, one chemical
-- can be required by several experiments.
CREATE TABLE Experiment_Chemical (
    experiment_chemical_id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id            INTEGER NOT NULL REFERENCES Experiment_Schedule(schedule_id) ON DELETE CASCADE,
    chemical_id            INTEGER NOT NULL REFERENCES Chemical(chemical_id) ON DELETE RESTRICT,
    quantity_required      REAL NOT NULL,
    unit_of_measure        TEXT NOT NULL DEFAULT 'kg',
    role_in_composition    TEXT,
    UNIQUE (schedule_id, chemical_id)
);

CREATE TABLE Purchase_Order (
    po_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number                   TEXT NOT NULL UNIQUE,
    chemical_id                 INTEGER NOT NULL REFERENCES Chemical(chemical_id) ON DELETE RESTRICT,
    supplier_name                TEXT NOT NULL,
    quantity_ordered             REAL NOT NULL,
    unit_of_measure               TEXT NOT NULL DEFAULT 'kg',
    unit_cost_usd                REAL,
    total_cost_usd                REAL,
    order_date                   TEXT NOT NULL,
    expected_delivery_date        TEXT,
    actual_delivery_date          TEXT,
    status                       TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN (
                                    'Draft', 'Submitted', 'Approved', 'Shipped',
                                    'Received', 'Backordered', 'Cancelled'
                                )),
    requested_by                 TEXT,
    approved_by                  TEXT,
    dot_hazmat_shipping_class    TEXT,
    notes                        TEXT
);

-- Audit trail of decisions made by the agentic layer, each one optionally
-- grounded in citations pulled from the IPS proceedings vector store and/or
-- a snapshot of live inventory state.
CREATE TABLE Decision_Log (
    decision_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp                 TEXT NOT NULL DEFAULT (datetime('now')),
    decision_type             TEXT NOT NULL CHECK (decision_type IN (
                                   'Reorder Recommendation', 'Experiment Risk Assessment',
                                   'Composition Substitution', 'Compliance Flag',
                                   'Schedule Conflict Resolution', 'Storage Compatibility Flag'
                               )),
    related_chemical_id       INTEGER REFERENCES Chemical(chemical_id) ON DELETE SET NULL,
    related_schedule_id       INTEGER REFERENCES Experiment_Schedule(schedule_id) ON DELETE SET NULL,
    related_po_id             INTEGER REFERENCES Purchase_Order(po_id) ON DELETE SET NULL,
    triggering_event          TEXT NOT NULL,
    vector_store_citations    TEXT,
    inventory_snapshot_summary TEXT,
    recommended_action        TEXT NOT NULL,
    confidence_score          REAL CHECK (confidence_score BETWEEN 0 AND 1),
    agent_model                TEXT,
    human_reviewer             TEXT,
    human_decision              TEXT CHECK (human_decision IN
                                   ('Approved', 'Overridden', 'Pending') OR human_decision IS NULL),
    outcome                    TEXT,
    rationale                  TEXT
);

CREATE INDEX idx_chemical_category ON Chemical(category);
CREATE INDEX idx_chemical_reorder ON Chemical(quantity_on_hand, reorder_threshold);
CREATE INDEX idx_schedule_date ON Experiment_Schedule(scheduled_date);
CREATE INDEX idx_po_status ON Purchase_Order(status);
CREATE INDEX idx_decision_type ON Decision_Log(decision_type);
CREATE INDEX idx_decision_timestamp ON Decision_Log(timestamp);

-- Tracks the simulation engine's current position in simulated time and
-- basic run metadata. Single-row table (enforced by CHECK on the PK).
-- Not touched by the human/agent decision workflow -- engine-owned state.
CREATE TABLE Sim_State (
    id                          INTEGER PRIMARY KEY CHECK (id = 1),
    sim_now                     TEXT NOT NULL,
    last_processed_sim_date     TEXT,
    real_started_at             TEXT NOT NULL DEFAULT (datetime('now')),
    speed_factor                REAL NOT NULL DEFAULT 1440.0,
    random_seed                 INTEGER,
    total_sim_days_processed    INTEGER NOT NULL DEFAULT 0,
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Append-only operational log of everything the simulation engine does, for
-- the dashboard's live event feed. Distinct from Decision_Log (which is
-- agent reasoning with citations/confidence) -- this is plain telemetry.
CREATE TABLE Sim_Event_Log (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_date         TEXT NOT NULL,
    event_type       TEXT NOT NULL CHECK (event_type IN (
                          'ExperimentStarted', 'ExperimentCompleted', 'ApprovalPending',
                          'POTransition', 'SupplierDelay', 'Backordered',
                          'StochasticRecount', 'Expiration'
                      )),
    entity_type       TEXT,
    entity_id         INTEGER,
    message           TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_sim_event_log_id ON Sim_Event_Log(event_id DESC);
