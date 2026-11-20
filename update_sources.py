#!/usr/bin/env python3
"""Update incident card sources and downgrade claims on paraphrase sources."""

import json
from pathlib import Path

DATA_DIR = Path("data/incidents")

# Mapping: incident_id -> list of (old_ref, new_ref, new_type)
SOURCE_UPDATES = {
    "kochhar_icici_2018": [
        ("data/incidents/kochhar_icici_2018/sources/icici_2018_8k.md",
         "data/incidents/kochhar_icici_2018/sources/icici_2018_6k.md",
         "sec_filing"),
        ("data/incidents/kochhar_icici_2018/sources/cbi_2020_chargesheet.md",
         "data/incidents/kochhar_icici_2018/sources/cbi_2020_chargesheet.md",
         "paraphrase"),
    ],
    "easterbrook_mcdonalds_2019": [
        ("data/incidents/easterbrook_mcdonalds_2019/sources/mcdonalds_2019_8k.md",
         "data/incidents/easterbrook_mcdonalds_2019/sources/mcdonalds_2019_8k.md",
         "sec_filing"),
        ("data/incidents/easterbrook_mcdonalds_2019/sources/mcdonalds_2020_complaint.md",
         "data/incidents/easterbrook_mcdonalds_2019/sources/mcdonalds_2020_complaint.md",
         "paraphrase"),
    ],
    "hayward_bp_2010": [
        ("data/incidents/hayward_bp_2010/sources/bp_2010_8k.md",
         "data/incidents/hayward_bp_2010/sources/bp_2010_6k.md",
         "sec_filing"),
        ("data/incidents/hayward_bp_2010/sources/bp_2011_penalty.md",
         "data/incidents/hayward_bp_2010/sources/bp_2011_penalty.md",
         "paraphrase"),
    ],
    "wells_fargo_2016": [
        ("data/incidents/wells_fargo_2016/sources/wells_fargo_2016_8k.md",
         "data/incidents/wells_fargo_2016/sources/wells_fargo_2016_8k.md",
         "sec_filing"),
        ("data/incidents/wells_fargo_2016/sources/cfpb_2016_penalty.md",
         "data/incidents/wells_fargo_2016/sources/cfpb_2016_consentorder.md",
         "regulatory_order"),
    ],
    "petraeus_cia_2012": [
        ("data/incidents/petraeus_cia_2012/sources/cia_2012_8k.md",
         "data/incidents/petraeus_cia_2012/sources/obama_2012_statement.md",
         "government_statement"),
        ("data/incidents/petraeus_cia_2012/sources/petraeus_2012_plea.md",
         "data/incidents/petraeus_cia_2012/sources/petraeus_2012_plea.md",
         "paraphrase"),
    ],
    "panama_papers_2016": [
        ("data/incidents/panama_papers_2016/sources/iceland_2016_resignation.md",
         "data/incidents/panama_papers_2016/sources/icij_20160405_iceland.md",
         "investigative_journalism"),
        ("data/incidents/panama_papers_2016/sources/panama_papers_2016_leak.md",
         "data/incidents/panama_papers_2016/sources/panama_papers_2016_leak.md",
         "paraphrase"),
    ],
    "ghosn_nissan_2018": [
        ("data/incidents/ghosn_nissan_2018/sources/ghosn_2018_arrest.md",
         "data/incidents/ghosn_nissan_2018/sources/sec_2019_183.md",
         "sec_press_release"),
        ("data/incidents/ghosn_nissan_2018/sources/nissan_2018_8k.md",
         "data/incidents/ghosn_nissan_2018/sources/nissan_2018_8k.md",
         "paraphrase"),
    ],
    "strauss_kahn_imf_2011": [
        ("data/incidents/strauss_kahn_imf_2011/sources/dsk_2011_arrest.md",
         "data/incidents/strauss_kahn_imf_2011/sources/dsk_2011_arrest.md",
         "paraphrase"),
        ("data/incidents/strauss_kahn_imf_2011/sources/dsk_2011_dismissal.md",
         "data/incidents/strauss_kahn_imf_2011/sources/dsk_2011_dismissal.md",
         "paraphrase"),
    ],
    "kalanick_uber_2017": [
        ("data/incidents/kalanick_uber_2017/sources/uber_2017_8k.md",
         "data/incidents/kalanick_uber_2017/sources/uber_2017_8k.md",
         "paraphrase"),
        ("data/incidents/kalanick_uber_2017/sources/uber_2018_settlement.md",
         "data/incidents/kalanick_uber_2017/sources/uber_2018_settlement.md",
         "paraphrase"),
    ],
    "volkswagen_2015": [
        ("data/incidents/volkswagen_2015/sources/epa_2015_violation.md",
         "data/incidents/volkswagen_2015/sources/epa_2015_nov.md",
         "regulatory_order"),
        ("data/incidents/volkswagen_2015/sources/volkswagen_2015_8k.md",
         "data/incidents/volkswagen_2015/sources/vw_2015_winterkorn.md",
         "company_press_release"),
    ],
}

# Paraphrase source IDs that should trigger claim downgrades
PARAPHRASE_SOURCE_IDS = {
    "kochhar_icici_2018": {"s2"},
    "easterbrook_mcdonalds_2019": {"s2"},
    "hayward_bp_2010": {"s2"},
    "wells_fargo_2016": set(),  # s2 is regulatory_order, not paraphrase
    "petraeus_cia_2012": {"s2"},
    "panama_papers_2016": {"s2"},
    "ghosn_nissan_2018": {"s2"},
    "strauss_kahn_imf_2011": {"s1", "s2"},
    "kalanick_uber_2017": {"s1", "s2"},
}

def update_card(incident_id: str):
    path = DATA_DIR / f"{incident_id}.json"
    with open(path) as f:
        card = json.load(f)

    # Update top-level sources
    if incident_id in SOURCE_UPDATES:
        # Build mapping from old ref to (new ref, new type)
        ref_map = {}
        for old_ref, new_ref, new_type in SOURCE_UPDATES[incident_id]:
            ref_map[old_ref] = (new_ref, new_type)

        # Update sources arrays (both top-level and outcome.sources)
        for source_list in [card.get("sources", []), card.get("outcome", {}).get("sources", [])]:
            for src in source_list:
                old_ref = src.get("ref", "")
                if old_ref in ref_map:
                    new_ref, new_type = ref_map[old_ref]
                    src["ref"] = new_ref
                    src["type"] = new_type

    # Downgrade claims referencing paraphrase sources
    paraphrase_ids = PARAPHRASE_SOURCE_IDS.get(incident_id, set())
    if paraphrase_ids:
        for claim in card.get("claims", []):
            claim_source_ids = set(claim.get("source_ids", []))
            if claim_source_ids & paraphrase_ids:
                claim["tag"] = "reported_unconfirmed"

    # Write back
    with open(path, "w") as f:
        json.dump(card, f, indent=2, sort_keys=True, ensure_ascii=False)

    print(f"Updated {incident_id}")

if __name__ == "__main__":
    for incident_id in SOURCE_UPDATES:
        update_card(incident_id)
    print("Done!")