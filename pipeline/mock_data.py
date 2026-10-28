"""Offline fixtures used only when FM_MOCK=1 (for testing without network/keys).
Everything here is clearly labelled [SAMPLE] so it can never be mistaken for real literature."""

PROFILE = {
    "field_summary": "Ecosystem services valuation and governance in the Global South",
    "areas": [
        "Foundations of ecosystem services", "Valuation methods", "Governance & policy",
        "Payments for ecosystem services", "Land-use change", "Remote sensing & GIS",
        "Social-ecological systems", "Equity & justice", "Biodiversity policy", "Methods & statistics",
    ],
    "queries": ["ecosystem services global south", "payments for ecosystem services", "nature's contributions to people"],
    "must_terms": ["ecosystem service", "payments for ecosystem", "land-use", "valuation"],
    "region_terms": ["africa", "south asia", "latin america", "global south", "smallholder"],
    "policy_queries": ["biodiversity regulation deforestation", "ecosystem services policy"],
    "event_queries": ["call for papers ecosystem services conference"],
    "debates": [
        {"title": "Should nature be given a monetary value?", "query": "monetary valuation of nature critique"},
        {"title": "Do payments for ecosystem services work?", "query": "payments for ecosystem services effectiveness"},
    ],
}

WORKS = [
    {
        "id": "W1001", "doi": "https://doi.org/10.0000/sample.1", "title": "[SAMPLE] Do payments keep wetlands intact after funding ends?",
        "date": "2026-10-26", "venue": "Ecosystem Services", "authors": ["A. Sample", "B. Example"], "n_authors": 2,
        "abstract": "We followed 400 smallholder farms for six years. Half received payments for wetland protection. Wetland cover stayed stable for two years after payments ended and then declined.",
        "cited_by": 0, "oa": True, "url": "https://example.org/sample1", "type": "article",
    },
    {
        "id": "W1002", "doi": None, "title": "[SAMPLE] Mapping cultural ecosystem services with participatory GIS in South Asia",
        "date": "2026-10-25", "venue": "Global Environmental Change", "authors": ["C. Demo"], "n_authors": 1,
        "abstract": "Participatory mapping with 120 households identified cultural services valued by communities. Results differed strongly by gender and caste group.",
        "cited_by": 1, "oa": False, "url": "https://example.org/sample2", "type": "article",
    },
    {
        "id": "W1003", "doi": None, "title": "[SAMPLE] Land-use change and pollinator services in Latin America",
        "date": "2026-10-24", "venue": "Ecological Economics", "authors": ["D. Test", "E. Case"], "n_authors": 2,
        "abstract": "Satellite data and field surveys show pollinator-dependent crop yields fall near rapidly converted land. Effects were largest for coffee.",
        "cited_by": 2, "oa": True, "url": "https://example.org/sample3", "type": "article",
    },
]

DIGEST = {
    "headline": "[SAMPLE] Payments help, but effects fade",
    "bullets": ["Followed 400 farms for 6 years", "Wetlands held 2 years after payments stopped", "Short payments may not last"],
    "plain": {
        "question": "Do farmers keep protecting wetlands after payments stop?",
        "method": "They tracked 400 farms for six years; half were paid, half were not.",
        "finding": "Wetland cover held for two years after payments ended, then fell.",
        "why": "Short-term payments may not create lasting change.",
    },
    "explainer": "This is a sample explanation. A real run rewrites each abstract in simple language so you can follow it without being an expert in the sub-topic.",
    "caveats": ["Sample data only"],
    "jargon": [{"term": "payments for ecosystem services", "definition": "Money paid to land users to protect nature that benefits others."}],
    "fit": "Shows how a sample paper would be connected to your field.",
    "relevance": 4,
}

RSS = [
    {"title": "[SAMPLE] EU delays deforestation rules by another year - Example News", "link": "https://example.org/n1",
     "date": "2026-10-27", "source": "Example News", "desc": ""},
    {"title": "[SAMPLE] Call for abstracts: Ecosystem Services Conference 2027 - Example Society", "link": "https://example.org/n2",
     "date": "2026-10-26", "source": "Example Society", "desc": ""},
    {"title": "[SAMPLE] New funding call for biodiversity research in Africa - Example Funder", "link": "https://example.org/n3",
     "date": "2026-10-25", "source": "Example Funder", "desc": ""},
]

RELEASE = {"tag_name": "v9.9.9-sample", "name": "Sample release", "published_at": "2026-10-20T10:00:00Z",
           "html_url": "https://example.org/release", "body": "Adds a new sample model and fixes bugs."}

CANDIDATE_AUTHORS = [("A5000000001", "Sample Researcher One"), ("A5000000002", "Sample Researcher Two")]
AUTHOR = {"id": "https://openalex.org/A5000000001", "display_name": "Sample Researcher One",
          "last_known_institutions": [{"display_name": "Sample University", "country_code": "XX"}],
          "works_count": 120, "cited_by_count": 15000, "summary_stats": {"h_index": 40},
          "topics": [{"display_name": "Ecosystem services"}, {"display_name": "Environmental valuation"}]}
TOP_WORKS = [
    {"id": "https://openalex.org/W2001", "title": "[SAMPLE] A foundational sample paper", "publication_date": "2015-01-01",
     "cited_by_count": 3000, "doi": None},
    {"id": "https://openalex.org/W2002", "title": "[SAMPLE] Another influential sample paper", "publication_date": "2019-05-05",
     "cited_by_count": 1200, "doi": None},
]
