"""Build inventory.db from schema.sql and load realistic fake lab data."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "inventory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

CHEMICALS = [
    # name, cas, formula, category, form, particle_um, purity%, un_number,
    # hazard_class, storage_class, location, qty, unit, reorder, unit_cost,
    # supplier, expiration, last_check, sens_impact_j, sens_friction_n, msds_url, notes
    ("Potassium Perchlorate", "7778-74-7", "KClO4", "Oxidizer", "Fine powder", 15, 99.5,
     "UN1489", "5.1", "Magazine B - Oxidizers", "Bunker 2, Shelf A1", 42.5, "kg", 10,
     18.40, "Apex Oxidizer Solutions", "2027-11-30", "2026-06-01", 8.0, 80,
     "https://example-msds.local/kclo4", "Primary oxidizer for flash and color stars."),
    ("Potassium Nitrate", "7757-79-1", "KNO3", "Oxidizer", "Granular", 120, 99.0,
     "UN1486", "5.1", "Magazine B - Oxidizers", "Bunker 2, Shelf A2", 88.0, "kg", 15,
     6.20, "Meridian Specialty Chemicals", "2028-03-15", "2026-06-01", 25.0, 250,
     "https://example-msds.local/kno3", "Used in black powder and gerb compositions."),
    ("Strontium Nitrate", "10042-76-9", "Sr(NO3)2", "Oxidizer", "Granular", 100, 98.5,
     "UN1507", "5.1", "Magazine B - Oxidizers", "Bunker 2, Shelf A3", 36.0, "kg", 10,
     9.10, "Meridian Specialty Chemicals", "2027-09-01", "2026-06-01", 30.0, 300,
     "https://example-msds.local/srno3", "Red color donor oxidizer."),
    ("Barium Nitrate", "10022-31-8", "Ba(NO3)2", "Oxidizer", "Granular", 90, 99.0,
     "UN1446", "5.1", "Magazine B - Oxidizers", "Bunker 2, Shelf A4", 28.5, "kg", 10,
     7.80, "Apex Oxidizer Solutions", "2027-12-20", "2026-06-01", 28.0, 280,
     "https://example-msds.local/bano3", "Green color donor; toxicity controls apply."),
    ("Ammonium Perchlorate", "7790-98-9", "NH4ClO4", "Oxidizer", "Fine powder", 20, 99.8,
     "UN0402", "1.1D", "Magazine A - Class 1.1", "Bunker 1, Vault 1", 12.0, "kg", 5,
     22.00, "Cascade Energetic Supply Co.", "2027-05-10", "2026-06-05", 4.0, 40,
     "https://example-msds.local/ap", "Restricted-access vault; explosive oxidizer, log every withdrawal."),
    ("Potassium Chlorate", "3811-04-9", "KClO3", "Oxidizer", "Fine powder", 18, 99.0,
     "UN1485", "5.1", "Magazine B - Oxidizers", "Bunker 2, Shelf A5", 6.0, "kg", 5,
     15.60, "Apex Oxidizer Solutions", "2027-07-01", "2026-06-01", 2.5, 30,
     "https://example-msds.local/kclo3", "Never store adjacent to sulfur or sulfides; segregated shelf."),
    ("Magnesium Powder", "7439-95-4", "Mg", "Metal Fuel", "Powder, -100 mesh", 150, 99.0,
     "UN1418", "4.3", "Magazine C - Metal Fuels", "Bunker 3, Shelf B1", 18.0, "kg", 8,
     34.00, "Northstar Pyrotechnic Materials", "2028-01-01", "2026-06-02", 5.0, 5,
     "https://example-msds.local/mg", "Water-reactive; dry storage only, CO2 extinguishers nearby."),
    ("Aluminum Powder (Dark)", "7429-90-5", "Al", "Metal Fuel", "Flake, -325 mesh", 44, 99.0,
     "UN1309", "4.1", "Magazine C - Metal Fuels", "Bunker 3, Shelf B2", 24.0, "kg", 8,
     19.50, "Northstar Pyrotechnic Materials", "2028-02-15", "2026-06-02", 6.0, 8,
     "https://example-msds.local/al-dark", "Used in glitter and silver tail effects."),
    ("Titanium Powder", "7440-32-6", "Ti", "Metal Fuel", "Sponge, 30-100 mesh", 500, 99.5,
     "UN2546", "4.1", "Magazine C - Metal Fuels", "Bunker 3, Shelf B3", 4.5, "kg", 3,
     86.00, "Northstar Pyrotechnic Materials", "2027-10-10", "2026-06-02", 12.0, 50,
     "https://example-msds.local/ti", "Coarse grade for titanium salute crackle effect."),
    ("Antimony Trisulfide", "1345-04-6", "Sb2S3", "Metal Fuel", "Fine powder", 10, 98.0,
     "None", "4.1", "Magazine C - Metal Fuels", "Bunker 3, Shelf B4", 7.0, "kg", 5,
     28.00, "Cascade Energetic Supply Co.", "2027-08-01", "2026-06-02", 3.0, 20,
     "https://example-msds.local/sb2s3", "Glitter/whitening agent; fine grade is friction sensitive."),
    ("Airfloat Charcoal", "7440-44-0", "C", "Fuel", "Ultra-fine powder", 40, 95.0,
     "None", "Non-hazardous", "Magazine D - Fuels", "Bunker 4, Shelf C1", 30.0, "kg", 10,
     11.20, "Meridian Specialty Chemicals", "2029-01-01", "2026-06-03", None, None,
     "https://example-msds.local/charcoal", "Willow and charcoal-streamer star fuel."),
    ("Sulfur", "7704-34-9", "S8", "Fuel", "Flour, 325 mesh", 30, 99.5,
     "UN1350", "4.1", "Magazine D - Fuels", "Bunker 4, Shelf C2", 22.0, "kg", 8,
     5.40, "Meridian Specialty Chemicals", "2028-06-01", "2026-06-03", 7.0, 60,
     "https://example-msds.local/sulfur", "Keep segregated from chlorates per storage matrix."),
    ("Dextrin", "9004-53-9", "(C6H10O5)n", "Binder", "Fine powder", 60, 97.0,
     "None", "Non-hazardous", "Magazine D - Fuels", "Bunker 4, Shelf C3", 14.0, "kg", 5,
     9.80, "Cascade Energetic Supply Co.", "2028-09-01", "2026-06-03", None, None,
     "https://example-msds.local/dextrin", "Standard water-activated binder for stars and comets."),
    ("Red Gum", "9000-15-1", "Resin", "Binder", "Flake", 200, 96.0,
     "None", "Non-hazardous", "Magazine D - Fuels", "Bunker 4, Shelf C4", 9.5, "kg", 4,
     14.50, "Cascade Energetic Supply Co.", "2028-04-01", "2026-06-03", None, None,
     "https://example-msds.local/redgum", "Alcohol-activated binder, adds fuel value."),
    ("Parlon (Chlorinated Rubber)", "9002-86-2", "C3H4Cl2", "Chlorine Donor", "Fine powder", 50, 98.0,
     "None", "Non-hazardous", "Magazine D - Fuels", "Bunker 4, Shelf C5", 11.0, "kg", 5,
     21.00, "Northstar Pyrotechnic Materials", "2027-12-01", "2026-06-03", None, None,
     "https://example-msds.local/parlon", "Chlorine donor that intensifies color purity."),
    ("Copper(II) Carbonate (Basic)", "12069-69-1", "CuCO3*Cu(OH)2", "Color Agent", "Fine powder", 25, 98.5,
     "None", "Non-hazardous", "Magazine E - Colorants", "Bunker 5, Shelf D1", 8.0, "kg", 4,
     26.30, "Meridian Specialty Chemicals", "2029-02-01", "2026-06-04", None, None,
     "https://example-msds.local/cuco3", "Blue/green color donor."),
    ("Strontium Carbonate", "1633-05-2", "SrCO3", "Color Agent", "Fine powder", 20, 99.0,
     "None", "Non-hazardous", "Magazine E - Colorants", "Bunker 5, Shelf D2", 16.0, "kg", 6,
     12.70, "Meridian Specialty Chemicals", "2028-11-01", "2026-06-04", None, None,
     "https://example-msds.local/srco3", "Red color donor, less hygroscopic than nitrate."),
    ("Barium Chloride", "10361-37-2", "BaCl2", "Color Agent", "Crystalline", 80, 99.0,
     "UN1564", "6.1", "Magazine E - Colorants", "Bunker 5, Shelf D3", 5.5, "kg", 3,
     17.90, "Apex Oxidizer Solutions", "2027-06-01", "2026-06-04", None, None,
     "https://example-msds.local/bacl2", "Toxic; gloves and respirator mandatory for handling."),
    ("Sodium Oxalate", "62-76-0", "Na2C2O4", "Color Agent", "Fine powder", 35, 99.0,
     "None", "Non-hazardous", "Magazine E - Colorants", "Bunker 5, Shelf D4", 6.0, "kg", 3,
     20.10, "Cascade Energetic Supply Co.", "2028-07-01", "2026-06-04", None, None,
     "https://example-msds.local/naox", "Yellow color donor, used with chlorine donors."),
    ("Boric Acid", "10043-35-3", "H3BO3", "Buffer/Coating", "Fine powder", 45, 99.5,
     "None", "Non-hazardous", "Magazine D - Fuels", "Bunker 4, Shelf C6", 10.0, "kg", 4,
     8.90, "Meridian Specialty Chemicals", "2029-05-01", "2026-06-03", None, None,
     "https://example-msds.local/boric", "Coats aluminum/magnesium to suppress nitrate reaction in storage."),
]

EXPERIMENTS = [
    # code, title, objective, lead, date, duration, site, risk, status,
    # approval, approved_by, ips_citation
    ("EXP-2026-014", "Strontium Red Star Burn Rate Trial",
     "Quantify burn rate vs. particle size for SrCO3-based red star formulation.",
     "Dr. Elena Vasquez", "2026-07-08", 90, "Range 3 - Static Test Pad", "Moderate",
     "Approved", "Approved", "Dr. Marcus Lindqvist",
     "Proc. 41st Int'l Pyrotechnics Seminar (2015), pp. 211-224"),
    ("EXP-2026-015", "Titanium Salute Flash Powder Sensitivity Screen",
     "Impact/friction sensitivity mapping for coarse Ti sponge in KClO4 flash blend.",
     "Dr. Marcus Lindqvist", "2026-07-10", 60, "Bunker 1 - Sensitivity Lab", "Severe",
     "Approved", "Approved", "Safety Committee",
     "Proc. 33rd Int'l Pyrotechnics Seminar (2007), pp. 88-102"),
    ("EXP-2026-016", "Willow Effect Charcoal Comet Comparison",
     "Compare tail persistence of airfloat vs. coarse charcoal in comet stars.",
     "Priya Natarajan", "2026-07-12", 75, "Range 2 - Aerial Test Tower", "Low",
     "Planned", "Pending", None,
     "Proc. 39th Int'l Pyrotechnics Seminar (2013), pp. 301-310"),
    ("EXP-2026-017", "Green Color Purity: Barium vs. Copper Donor",
     "Spectrometric comparison of BaCl2 vs CuCO3-based green star compositions.",
     "Dr. Elena Vasquez", "2026-07-15", 120, "Range 3 - Static Test Pad", "Moderate",
     "Approved", "Approved", "Dr. Marcus Lindqvist",
     "Proc. 44th Int'l Pyrotechnics Seminar (2018), pp. 55-69"),
    ("EXP-2026-018", "Whistle Mix Friction Sensitivity Screening",
     "Establish safe handling friction threshold for potassium benzoate whistle fuel batch.",
     "Dr. Marcus Lindqvist", "2026-07-18", 45, "Bunker 1 - Sensitivity Lab", "High",
     "Approved", "Approved", "Safety Committee",
     "Proc. 36th Int'l Pyrotechnics Seminar (2010), pp. 144-159"),
    ("EXP-2026-019", "Aluminum Flitter Electrostatic Discharge Test",
     "Measure ESD ignition threshold for dark Al flake at varying humidity.",
     "Priya Natarajan", "2026-07-21", 60, "Bunker 1 - Sensitivity Lab", "High",
     "Planned", "Pending", None,
     "Proc. 42nd Int'l Pyrotechnics Seminar (2016), pp. 401-415"),
    ("EXP-2026-020", "Crossette Break Charge Optimization",
     "Tune KClO4/charcoal ratio for clean four-way crossette break.",
     "Dr. Elena Vasquez", "2026-07-24", 100, "Range 2 - Aerial Test Tower", "Moderate",
     "Planned", "Pending", None,
     "Proc. 40th Int'l Pyrotechnics Seminar (2014), pp. 177-190"),
    ("EXP-2026-021", "Ammonium Perchlorate Composite Propellant Burn Study",
     "Baseline burn rate characterization for AP/Al composite gerb propellant.",
     "Dr. Marcus Lindqvist", "2026-07-28", 90, "Range 3 - Static Test Pad", "Severe",
     "Planned", "Pending", None,
     "Proc. 45th Int'l Pyrotechnics Seminar (2019), pp. 12-27"),
    ("EXP-2026-022", "Storage Co-location Compatibility Re-verification",
     "Routine re-test of chlorate/sulfur segregation margin per updated storage matrix.",
     "Priya Natarajan", "2026-08-02", 50, "Bunker 1 - Sensitivity Lab", "Moderate",
     "Planned", "Pending", None,
     "Proc. 30th Int'l Pyrotechnics Seminar (2004), pp. 233-248"),
    ("EXP-2026-023", "Yellow Star Sodium Oxalate Chlorine-Donor Ratio Sweep",
     "Identify optimal Parlon ratio for maximum yellow color purity.",
     "Dr. Elena Vasquez", "2026-08-05", 80, "Range 3 - Static Test Pad", "Low",
     "Planned", "Pending", None,
     "Proc. 43rd Int'l Pyrotechnics Seminar (2017), pp. 269-281"),
]

# (experiment_code, chemical_name, quantity_required, unit, role)
EXPERIMENT_CHEMICALS = [
    ("EXP-2026-014", "Strontium Carbonate", 2.0, "kg", "Color donor"),
    ("EXP-2026-014", "Potassium Perchlorate", 1.5, "kg", "Oxidizer"),
    ("EXP-2026-014", "Dextrin", 0.3, "kg", "Binder"),
    ("EXP-2026-015", "Titanium Powder", 0.5, "kg", "Metal fuel"),
    ("EXP-2026-015", "Potassium Perchlorate", 1.0, "kg", "Oxidizer"),
    ("EXP-2026-016", "Airfloat Charcoal", 3.0, "kg", "Fuel"),
    ("EXP-2026-016", "Potassium Nitrate", 2.0, "kg", "Oxidizer"),
    ("EXP-2026-016", "Dextrin", 0.4, "kg", "Binder"),
    ("EXP-2026-017", "Barium Chloride", 1.0, "kg", "Color donor"),
    ("EXP-2026-017", "Copper(II) Carbonate (Basic)", 1.0, "kg", "Color donor"),
    ("EXP-2026-017", "Parlon (Chlorinated Rubber)", 0.8, "kg", "Chlorine donor"),
    ("EXP-2026-018", "Sulfur", 0.6, "kg", "Fuel"),
    ("EXP-2026-018", "Potassium Perchlorate", 0.5, "kg", "Oxidizer"),
    ("EXP-2026-019", "Aluminum Powder (Dark)", 1.2, "kg", "Metal fuel"),
    ("EXP-2026-020", "Potassium Perchlorate", 2.5, "kg", "Oxidizer"),
    ("EXP-2026-020", "Airfloat Charcoal", 1.8, "kg", "Fuel"),
    ("EXP-2026-021", "Ammonium Perchlorate", 4.0, "kg", "Oxidizer"),
    ("EXP-2026-021", "Aluminum Powder (Dark)", 1.5, "kg", "Metal fuel"),
    ("EXP-2026-022", "Potassium Chlorate", 0.2, "kg", "Sensitivity reference"),
    ("EXP-2026-022", "Sulfur", 0.2, "kg", "Sensitivity reference"),
    ("EXP-2026-023", "Sodium Oxalate", 1.5, "kg", "Color donor"),
    ("EXP-2026-023", "Parlon (Chlorinated Rubber)", 1.0, "kg", "Chlorine donor"),
]

# (po_number, chemical_name, qty, unit, unit_cost, supplier, order_date,
#  expected_delivery, actual_delivery, status, requested_by, approved_by,
#  dot_class, notes)
PURCHASE_ORDERS = [
    ("PO-2026-0091", "Titanium Powder", 10.0, "kg", 86.00, "Northstar Pyrotechnic Materials",
     "2026-06-10", "2026-07-01", None, "Approved", "Priya Natarajan", "Dr. Marcus Lindqvist",
     "4.1", "Restock ahead of EXP-2026-015; current stock below threshold."),
    ("PO-2026-0092", "Potassium Chlorate", 15.0, "kg", 15.60, "Apex Oxidizer Solutions",
     "2026-06-12", "2026-07-03", None, "Submitted", "Dr. Marcus Lindqvist", None,
     "5.1", "Stock critically low after EXP-2026-022 prep usage."),
    ("PO-2026-0093", "Ammonium Perchlorate", 20.0, "kg", 22.00, "Cascade Energetic Supply Co.",
     "2026-06-14", "2026-07-15", None, "Approved", "Dr. Elena Vasquez", "Safety Committee",
     "1.1D", "Vault-controlled item; requires explosives transport permit on file."),
    ("PO-2026-0094", "Barium Chloride", 8.0, "kg", 17.90, "Apex Oxidizer Solutions",
     "2026-06-15", "2026-07-06", None, "Draft", "Priya Natarajan", None,
     "6.1", "Pending toxics handling sign-off before submission."),
    ("PO-2026-0095", "Strontium Nitrate", 50.0, "kg", 9.10, "Meridian Specialty Chemicals",
     "2026-05-20", "2026-06-10", "2026-06-09", "Received", "Dr. Elena Vasquez", "Dr. Marcus Lindqvist",
     "5.1", "Bulk restock for Q3 red-effects test series."),
    ("PO-2026-0096", "Dextrin", 25.0, "kg", 9.80, "Cascade Energetic Supply Co.",
     "2026-05-22", "2026-06-05", "2026-06-04", "Received", "Priya Natarajan", "Dr. Marcus Lindqvist",
     "None", "Routine binder restock."),
    ("PO-2026-0097", "Magnesium Powder", 12.0, "kg", 34.00, "Northstar Pyrotechnic Materials",
     "2026-06-18", "2026-07-09", None, "Submitted", "Dr. Marcus Lindqvist", None,
     "4.3", "Water-reactive item; confirm dry-cargo shipping rider."),
    ("PO-2026-0098", "Antimony Trisulfide", 6.0, "kg", 28.00, "Cascade Energetic Supply Co.",
     "2026-06-19", "2026-07-10", None, "Draft", "Priya Natarajan", None,
     "4.1", "Awaiting glitter-series budget approval."),
    ("PO-2026-0099", "Sodium Oxalate", 5.0, "kg", 20.10, "Cascade Energetic Supply Co.",
     "2026-06-20", "2026-07-11", None, "Submitted", "Dr. Elena Vasquez", None,
     "None", "For EXP-2026-023 color sweep series."),
    ("PO-2026-0100", "Potassium Perchlorate", 30.0, "kg", 18.40, "Apex Oxidizer Solutions",
     "2026-06-21", "2026-07-12", None, "Approved", "Dr. Marcus Lindqvist", "Dr. Marcus Lindqvist",
     "5.1", "General-use oxidizer, high consumption rate across active experiments."),
    ("PO-2026-0101", "Aluminum Powder (Dark)", 15.0, "kg", 19.50, "Northstar Pyrotechnic Materials",
     "2026-04-02", "2026-04-20", "2026-04-19", "Received", "Priya Natarajan", "Dr. Marcus Lindqvist",
     "4.1", "Closed PO, used for Q2 flitter series."),
    ("PO-2026-0102", "Sulfur", 18.0, "kg", 5.40, "Meridian Specialty Chemicals",
     "2026-06-22", "2026-07-13", None, "Backordered", "Dr. Marcus Lindqvist", "Dr. Marcus Lindqvist",
     "4.1", "Supplier reports delay; segregated-storage capacity confirmed for when it arrives."),
]

# (decision_type, related_chemical, related_schedule, related_po,
#  triggering_event, citations, inventory_summary, recommendation,
#  confidence, agent_model, human_reviewer, human_decision, outcome, rationale)
DECISIONS = [
    ("Reorder Recommendation", "Titanium Powder", None, "PO-2026-0091",
     "Quantity on hand (4.5 kg) fell below reorder threshold (3 kg buffer margin) "
     "after EXP-2026-015 allocation.",
     '["IPS Proc. 33rd Seminar (2007) p.88-102"]',
     "Titanium Powder: 4.5 kg on hand, 0.5 kg reserved for EXP-2026-015, "
     "reorder threshold 3 kg.",
     "Issue purchase order for 10 kg from Northstar Pyrotechnic Materials, "
     "current approved supplier with matching DOT 4.1 shipping profile.",
     0.91, "claude-sonnet-5", "Priya Natarajan", "Approved",
     "PO-2026-0091 issued and approved within 24 hours.",
     "Historical seminar data confirms coarse Ti sponge is the standard salute "
     "crackle fuel with no viable substitute in queued formulations."),
    ("Experiment Risk Assessment", "Titanium Powder", "EXP-2026-015", None,
     "New experiment scheduled involving Ti sponge + KClO4 flash blend, flagged Severe risk.",
     '["IPS Proc. 33rd Seminar (2007) p.88-102", "IPS Proc. 36th Seminar (2010) p.144-159"]',
     "No prior on-site sensitivity data for this specific Ti mesh/KClO4 ratio combination.",
     "Require remote-initiation sensitivity screen in Bunker 1 before any open-bench "
     "handling; cap batch size at 50g for first trial.",
     0.78, "claude-sonnet-5", "Dr. Marcus Lindqvist", "Approved",
     "Safety Committee adopted 50g cap as written into EXP-2026-015 protocol.",
     "Cited proceedings document comparable Ti/perchlorate blends as impact-sensitive "
     "below 10 J in similar mesh ranges; no on-site empirical data existed to override caution."),
    ("Storage Compatibility Flag", "Potassium Chlorate", None, None,
     "Routine storage matrix audit detected Sulfur and Potassium Chlorate "
     "stored in adjacent magazine sections (Bunker 4 vs Bunker 2, separation nominal).",
     '["IPS Proc. 30th Seminar (2004) p.233-248"]',
     "Potassium Chlorate: 6.0 kg, Bunker 2 Shelf A5. Sulfur: 22.0 kg, Bunker 4 Shelf C2.",
     "No action required; current separation (different magazines, >15m) exceeds "
     "historical incident-derived minimum of 5m. Recommend re-verification experiment "
     "to refresh local data.",
     0.85, "claude-sonnet-5", "Dr. Marcus Lindqvist", "Approved",
     "Scheduled EXP-2026-022 to refresh empirical margin data.",
     "Multiple proceedings papers document chlorate-sulfide friction-initiated incidents; "
     "current physical separation already exceeds the conservative threshold cited."),
    ("Schedule Conflict Resolution", "Potassium Perchlorate", "EXP-2026-020", None,
     "EXP-2026-014, EXP-2026-015, EXP-2026-018, EXP-2026-020 all draw on Potassium "
     "Perchlorate within a 16-day window; cumulative demand (5.5 kg) approaches on-hand stock.",
     "[]",
     "Potassium Perchlorate: 42.5 kg on hand, 5.5 kg cumulative committed across 4 "
     "scheduled experiments, no immediate shortfall.",
     "No reschedule needed; flag for monitoring only. Recommend PO-2026-0100 proceed "
     "as planned to maintain buffer above 30 kg.",
     0.88, "claude-sonnet-5", "Dr. Elena Vasquez", "Approved",
     "PO-2026-0100 approved same day; no schedule changes made.",
     "Cumulative draw is well within on-hand stock; flagged proactively due to "
     "four concurrent experiments sharing the same oxidizer."),
    ("Compliance Flag", "Ammonium Perchlorate", "EXP-2026-021", "PO-2026-0093",
     "EXP-2026-021 requires 4 kg Ammonium Perchlorate; vault withdrawal log "
     "shows no completed explosives-handling refresher for lead chemist this cycle.",
     '["IPS Proc. 45th Seminar (2019) p.12-27"]',
     "Ammonium Perchlorate: 12.0 kg on hand in Vault 1, all withdrawals require dual sign-off.",
     "Hold experiment approval pending lead chemist's explosives-handling "
     "refresher certification renewal.",
     0.94, "claude-sonnet-5", "Safety Committee", "Approved",
     "EXP-2026-021 status set to Pending until certification confirmed.",
     "Internal policy requires current certification for any 1.1D withdrawal; "
     "log gap is a hard compliance blocker, not a judgment call."),
    ("Composition Substitution", "Barium Chloride", "EXP-2026-017", None,
     "Toxics handling sign-off for Barium Chloride still outstanding; PO-2026-0094 in Draft.",
     '["IPS Proc. 44th Seminar (2018) p.55-69"]',
     "Barium Chloride: 5.5 kg on hand, sufficient for current trial but no incoming "
     "restock confirmed yet.",
     "Proceed with EXP-2026-017 using on-hand Barium Chloride stock; do not block on "
     "PO-2026-0094, but escalate sign-off separately so future batches aren't delayed.",
     0.72, "claude-sonnet-5", "Dr. Elena Vasquez", "Approved",
     "Experiment proceeded on schedule; toxics sign-off escalated to EHS separately.",
     "On-hand quantity already covers the planned trial; the open PO only affects "
     "future restocking, not this experiment."),
    ("Reorder Recommendation", "Sulfur", None, "PO-2026-0102",
     "Sulfur consumption trend across last 3 experiments projected to breach reorder "
     "threshold within 10 days; supplier reported delay on PO-2026-0102.",
     "[]",
     "Sulfur: 22.0 kg on hand, threshold 8 kg, average consumption 1.5 kg/week.",
     "Monitor weekly; current backorder still leaves approximately 6 weeks of buffer "
     "before threshold breach, no expedite needed.",
     0.69, "claude-sonnet-5", "Dr. Marcus Lindqvist", "Approved",
     "No expedite requested; flagged for weekly monitoring instead.",
     "Buffer calculation showed ample runway despite the backorder, so escalating "
     "shipping cost for an expedite was not justified."),
    ("Experiment Risk Assessment", "Aluminum Powder (Dark)", "EXP-2026-019", None,
     "ESD test on fine Al flake scheduled; historical IPS data flags flake aluminum "
     "as highly ESD-sensitive at low ambient humidity.",
     '["IPS Proc. 42nd Seminar (2016) p.401-415"]',
     "Aluminum Powder (Dark): 24.0 kg on hand, -325 mesh flake grade.",
     "Require grounding straps, humidity control (>40% RH in test cell), and "
     "antistatic flooring verification before test proceeds.",
     0.83, "claude-sonnet-5", "Priya Natarajan", "Approved",
     "Test cell humidity control verified; EXP-2026-019 protocol updated accordingly.",
     "Cited proceedings paper specifically links low-humidity ESD events to flake "
     "aluminum ignition incidents in comparable mesh ranges."),
    ("Storage Compatibility Flag", "Magnesium Powder", None, "PO-2026-0097",
     "Incoming Magnesium Powder shipment (12 kg) requires confirmation that Bunker 3 "
     "dry-storage humidity control is rated for the increased volume.",
     "[]",
     "Magnesium Powder: 18.0 kg currently on hand, Bunker 3 Shelf B1; incoming 12 kg "
     "would bring total to 30.0 kg.",
     "Confirm Bunker 3 desiccant capacity before shipment arrival; no storage "
     "relocation needed if capacity check passes.",
     0.76, "claude-sonnet-5", "Dr. Marcus Lindqvist", "Pending",
     None,
     "Water-reactive metal fuel; proceedings literature stresses moisture control "
     "as the dominant storage risk factor, not co-location with other chemicals."),
    ("Schedule Conflict Resolution", None, "EXP-2026-022", None,
     "EXP-2026-022 (storage re-verification) and EXP-2026-018 (whistle mix sensitivity) "
     "both request Bunker 1 - Sensitivity Lab on overlapping dates.",
     "[]",
     "Bunker 1 - Sensitivity Lab: single-occupancy test cell, no concurrent bookings allowed.",
     "Recommend shifting EXP-2026-022 to 2026-08-02 (already proposed date), confirming "
     "no overlap with EXP-2026-018 on 2026-07-18.",
     0.95, "claude-sonnet-5", "Priya Natarajan", "Approved",
     "Schedule confirmed with no overlap; both experiments retained their dates.",
     "Simple calendar check against the single-occupancy constraint resolved the "
     "apparent conflict without rescheduling either experiment."),
    ("Composition Substitution", "Potassium Chlorate", "EXP-2026-022", None,
     "Re-verification trial requests Potassium Chlorate, currently the lowest-stock "
     "oxidizer (6.0 kg) with an open low-priority restock PO.",
     '["IPS Proc. 30th Seminar (2004) p.233-248"]',
     "Potassium Chlorate: 6.0 kg on hand, only 0.2 kg required for this trial.",
     "Proceed without substitution; required quantity (0.2 kg) is negligible relative "
     "to on-hand stock despite the low overall reorder threshold.",
     0.90, "claude-sonnet-5", "Dr. Marcus Lindqvist", "Approved",
     "Trial proceeded using on-hand stock as recommended.",
     "Flagged automatically due to low absolute stock, but the trial's actual "
     "requirement is small enough that no substitution or delay was warranted."),
    ("Compliance Flag", "Barium Nitrate", None, None,
     "Quarterly toxics inventory audit cross-check: Barium Nitrate on-hand "
     "quantity (28.5 kg) exceeds the facility's reporting threshold for barium "
     "compounds under the local environmental permit.",
     "[]",
     "Barium Nitrate: 28.5 kg on hand, Bunker 2 Shelf A4.",
     "File quarterly environmental compliance report; no operational restriction "
     "triggered at current quantity.",
     0.81, "claude-sonnet-5", "Dr. Elena Vasquez", "Approved",
     "Compliance report filed on schedule.",
     "Reporting threshold is administrative, not a safety threshold; flagged to "
     "keep the facility's environmental permit current."),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = DB_PATH.with_name(DB_PATH.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())

    cur = conn.cursor()

    cur.executemany(
        """INSERT INTO Chemical (
            name, cas_number, chemical_formula, category, physical_form,
            particle_size_microns, purity_percent, un_number, hazard_class,
            storage_class, storage_location, quantity_on_hand, unit_of_measure,
            reorder_threshold, unit_cost_usd, supplier_name, expiration_date,
            last_inventory_check, sensitivity_impact_j, sensitivity_friction_n,
            msds_url, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        CHEMICALS,
    )

    cur.executemany(
        """INSERT INTO Experiment_Schedule (
            experiment_code, title, objective, lead_chemist, scheduled_date,
            duration_minutes, test_site, risk_level, status, approval_status,
            approved_by, ips_reference_citation
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        EXPERIMENTS,
    )

    chem_id = {
        name: cid
        for cid, name in cur.execute("SELECT chemical_id, name FROM Chemical")
    }
    schedule_id = {
        code: sid
        for sid, code in cur.execute(
            "SELECT schedule_id, experiment_code FROM Experiment_Schedule"
        )
    }

    cur.executemany(
        """INSERT INTO Experiment_Chemical (
            schedule_id, chemical_id, quantity_required, unit_of_measure, role_in_composition
        ) VALUES (?,?,?,?,?)""",
        [
            (schedule_id[code], chem_id[name], qty, unit, role)
            for code, name, qty, unit, role in EXPERIMENT_CHEMICALS
        ],
    )

    cur.executemany(
        """INSERT INTO Purchase_Order (
            po_number, chemical_id, quantity_ordered, unit_of_measure, unit_cost_usd,
            supplier_name, order_date, expected_delivery_date, actual_delivery_date,
            status, requested_by, approved_by, dot_hazmat_shipping_class, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (po_num, chem_id[name], qty, unit, cost, supplier, order_date,
             exp_delivery, act_delivery, status, requested_by, approved_by, dot_class, notes)
            for (po_num, name, qty, unit, cost, supplier, order_date, exp_delivery,
                 act_delivery, status, requested_by, approved_by, dot_class, notes)
            in PURCHASE_ORDERS
        ],
    )

    po_id = {
        num: pid for pid, num in cur.execute("SELECT po_id, po_number FROM Purchase_Order")
    }

    cur.executemany(
        """INSERT INTO Decision_Log (
            decision_type, related_chemical_id, related_schedule_id, related_po_id,
            triggering_event, vector_store_citations, inventory_snapshot_summary,
            recommended_action, confidence_score, agent_model, human_reviewer,
            human_decision, outcome, rationale
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                dtype,
                chem_id.get(chem_name) if chem_name else None,
                schedule_id.get(exp_code) if exp_code else None,
                po_id.get(po_num) if po_num else None,
                trigger, citations, inv_summary, recommendation, confidence,
                model, reviewer, human_decision, outcome, rationale,
            )
            for (
                dtype, chem_name, exp_code, po_num, trigger, citations, inv_summary,
                recommendation, confidence, model, reviewer, human_decision, outcome, rationale,
            ) in DECISIONS
        ],
    )

    cur.execute(
        "INSERT INTO Sim_State (id, sim_now, speed_factor) VALUES (1, ?, ?)",
        ("2026-06-30 00:00:00", 1440.0),
    )

    conn.commit()

    counts = {
        table: cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "Chemical", "Experiment_Schedule", "Experiment_Chemical",
            "Purchase_Order", "Decision_Log", "Sim_State", "Sim_Event_Log",
        )
    }
    conn.close()

    print(f"Built {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
