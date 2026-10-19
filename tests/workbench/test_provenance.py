from ehr_migration_engine.workbench.facts import Fact
from ehr_migration_engine.workbench.provenance import link_facts, scale_bbox, source_frame


def test_matches_a_medication_and_leaves_an_unknown_string_unresolved() -> None:
    ocr = {
        "source": "packet_001_scanned_page_001.pdf",
        "image_bbox": [0, 0, 1000, 1400],
        "blocks": [
            {
                "bbox": [10, 10, 200, 40],
                "html": "<p>Header</p>",
                "reading_order": 0,
                "label": "SectionHeader",
                "confidence": 0.5,
            },
            {
                "bbox": [10, 50, 400, 120],
                "html": "<p>Start Lisinopril 10 mg daily for blood pressure.</p>",
                "reading_order": 1,
                "label": "Text",
                "confidence": 0.2,
                "text_lines": [
                    {
                        "text": "Start Lisinopril 10 mg daily",
                        "bbox": [12, 52, 380, 80],
                        "confidence": 0.88,
                    },
                    {"text": "for blood pressure.", "bbox": [12, 84, 200, 110], "confidence": 0.9},
                ],
            },
        ],
    }
    facts = [
        Fact("medications[0].name", "Medication", "Lisinopril", True, dosage="10 mg"),
        Fact("medications[1].name", "Medication", "Metformin", True),
    ]

    links = link_facts(
        ocr,
        facts,
        source_file="packet_001_scanned_page_001.pdf",
        page_number=1,
    )
    matched = links[0]
    missing = links[1]

    assert matched.resolved is True
    assert matched.block_index == 1
    assert matched.bbox == (12.0, 52.0, 380.0, 80.0)
    assert matched.confidence == 0.88
    assert matched.block_text is not None
    assert "Lisinopril" in matched.block_text

    assert missing.resolved is False
    assert missing.bbox is None
    assert missing.confidence is None
    assert missing.block_text is None


def test_uses_block_confidence_when_surya_did_not_emit_lines() -> None:
    ocr = {
        "image_bbox": [0, 0, 2176, 2816],
        "blocks": [
            {
                "bbox": [130.56, 627.968, 1431.808, 808.192],
                "html": "<ol><li>Allergy / Immunology -- Chronic Sinusitis</li></ol>",
                "reading_order": 7,
                "label": "ListGroup",
                "confidence": 0.96,
            }
        ],
    }
    facts = [Fact("conditions[0].diagnosis", "Condition", "Chronic Sinusitis", True)]

    link = link_facts(ocr, facts, source_file="packet_001_scanned_page_001.pdf", page_number=1)[0]

    assert link.resolved is True
    assert link.block_index == 0
    assert link.bbox == (130.56, 627.968, 1431.808, 808.192)
    assert link.confidence == 0.96
    assert source_frame(ocr) == ((0.0, 0.0), (2176.0, 2816.0))


def test_scale_bbox_maps_ocr_pixels_onto_the_rendered_page() -> None:
    scaled = scale_bbox((10, 20, 110, 220), (0, 0), (1000, 2000), (100, 200))

    assert scaled == (1.0, 2.0, 11.0, 22.0)
