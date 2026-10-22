import json
from pathlib import Path
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[3]
NORMALIZED_DIR = ROOT / "data" / "04_normalized"

class ClinicalGraph:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        # Default credentials for local docker-compose neo4j
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def ingest_document(self, filename: str, data: dict):
        patient_name = data.get("patient_name") or "Unknown Patient"
        
        with self.driver.session() as session:
            # 1. Merge Patient Node
            session.run(
                """
                MERGE (p:Patient {name: $name})
                SET p.age = $age, p.gender = $gender
                """,
                name=patient_name,
                age=data.get("age"),
                gender=data.get("gender")
            )

            # 2. Merge Encounter/Document Node
            session.run(
                """
                MATCH (p:Patient {name: $name})
                MERGE (d:Document {id: $doc_id})
                MERGE (p)-[:HAS_RECORD]->(d)
                """,
                name=patient_name,
                doc_id=filename
            )

            # 3. Ingest Conditions
            for cond in data.get("conditions", []):
                coding = cond.get("coding", {})
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MERGE (c:Condition {code: $code, system: $system})
                    ON CREATE SET c.display = $display
                    MERGE (d)-[r:RECORDS_DIAGNOSIS]->(c)
                    SET r.status = $status, r.raw_text = $raw_text
                    """,
                    doc_id=filename,
                    code=coding.get("code", "UNKNOWN"),
                    system=coding.get("system", "UNKNOWN"),
                    display=coding.get("display", cond.get("diagnosis", "")),
                    status=cond.get("status", ""),
                    raw_text=cond.get("diagnosis", "")
                )

            # 4. Ingest Observations (Labs)
            for obs in data.get("observations", []):
                coding = obs.get("coding", {})
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MERGE (o:Observation {code: $code, system: $system})
                    ON CREATE SET o.display = $display
                    MERGE (d)-[r:RECORDS_LAB]->(o)
                    SET r.value = $value, r.units = $units, r.flag = $flag, r.raw_text = $raw_text
                    """,
                    doc_id=filename,
                    code=coding.get("code", "UNKNOWN"),
                    system=coding.get("system", "UNKNOWN"),
                    display=coding.get("display", obs.get("test_name", "")),
                    value=obs.get("value", ""),
                    units=obs.get("units", ""),
                    flag=obs.get("flag", ""),
                    raw_text=obs.get("test_name", "")
                )

            # 5. Ingest Medications
            for med in data.get("medications", []):
                coding = med.get("coding", {})
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MERGE (m:Medication {code: $code, system: $system})
                    ON CREATE SET m.display = $display
                    MERGE (d)-[r:RECORDS_PRESCRIPTION]->(m)
                    SET r.dosage = $dosage, r.raw_text = $raw_text
                    """,
                    doc_id=filename,
                    code=coding.get("code", "UNKNOWN"),
                    system=coding.get("system", "UNKNOWN"),
                    display=coding.get("display", med.get("name", "")),
                    dosage=med.get("dosage", ""),
                    raw_text=med.get("name", "")
                )

    def patient_timeline(self, name: str) -> list[dict]:
        """Documents for one patient, with the coded facts recorded on each page."""
        query = """
        MATCH (p:Patient {name: $name})-[:HAS_RECORD]->(d:Document)
        OPTIONAL MATCH (d)-[dx:RECORDS_DIAGNOSIS]->(c:Condition)
        OPTIONAL MATCH (d)-[lab:RECORDS_LAB]->(o:Observation)
        OPTIONAL MATCH (d)-[rx:RECORDS_PRESCRIPTION]->(m:Medication)
        RETURN d.id AS document,
               [x IN collect(DISTINCT {display: c.display, status: dx.status, raw: dx.raw_text, code: c.code})
                WHERE x.display IS NOT NULL] AS conditions,
               [x IN collect(DISTINCT {display: o.display, value: lab.value, units: lab.units, flag: lab.flag, raw: lab.raw_text, code: o.code})
                WHERE x.display IS NOT NULL] AS observations,
               [x IN collect(DISTINCT {display: m.display, dosage: rx.dosage, raw: rx.raw_text, code: m.code})
                WHERE x.display IS NOT NULL] AS medications
        ORDER BY d.id
        """
        with self.driver.session() as session:
            records = session.run(query, name=name)
            return [record.data() for record in records]


def build_graph():
    json_files = sorted(NORMALIZED_DIR.glob("*.json"))
    if not json_files:
        print(f"[!] No normalized JSON files found in {NORMALIZED_DIR}")
        return

    print(f"[*] Building Knowledge Graph from {len(json_files)} documents...")
    
    graph = ClinicalGraph()
    success_count = 0
    
    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            graph.ingest_document(json_path.stem, data)
            success_count += 1
        except Exception as e:
            print(f"  [X] Failed to ingest {json_path.name}: {e}")

    graph.close()
    print(f"[*] Graph build complete. Ingested {success_count} documents into Neo4j.")

if __name__ == "__main__":
    build_graph()
