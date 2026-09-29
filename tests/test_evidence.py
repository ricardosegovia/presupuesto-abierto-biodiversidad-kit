from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from pa_biodiv.evidence import EvidenceSession,sanitize,public_params
from test_client import Session,Response

URL="https://api.presupuestoabierto.gob.cl/api/v1/data/pagos.json"

class EvidenceTests(unittest.TestCase):
    def test_cache_reuses_valid_response_preserves_time(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session([Response([{"periodo":2025}])])
            first=EvidenceSession(Path(d),session=s)
            first.get(URL,params={"where":'{"periodo":2025}'})
            second=EvidenceSession(Path(d),session=Session([]))
            second.get(URL,params={"where":'{"periodo":2025}'})
            self.assertEqual(first.records[0]["queried_at_utc"],second.records[0]["queried_at_utc"])
            self.assertTrue(second.records[0]["cache_hit"])
            self.assertEqual(len(s.calls),1)

    def test_corrupt_cache_redownloads(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session([Response([{"periodo":2025}]),Response([])])
            EvidenceSession(Path(d),session=s).get(URL,params={})
            cache=next((Path(d)/"queries").glob("*.json"))
            data=json.loads(cache.read_text());data["body"]=["tampered"]
            cache.write_text(json.dumps(data))
            fresh=EvidenceSession(Path(d),session=s)
            fresh.get(URL,params={})
            self.assertFalse(fresh.records[0]["cache_hit"])
            self.assertEqual(len(s.calls),2)

    def test_refresh_preserves_history(self):
        with tempfile.TemporaryDirectory() as d:
            s=Session([Response([]),Response([{"periodo":2025}])])
            EvidenceSession(Path(d),session=s).get(URL,params={})
            EvidenceSession(Path(d),session=s,refresh=True).get(URL,params={})
            self.assertEqual(len(list((Path(d)/"responses").glob("*.json"))),2)

    def test_person_and_blocked_order_are_redacted(self):
        r=sanitize({"items":[{"persona":1,"_id":"private","beneficiario":"SECRET","nombre_beneficiario":"SECRET","numero_documento":"SECRET","orden_de_compra":"SECRET"}]})
        self.assertNotIn("SECRET",json.dumps(r))
        self.assertNotIn("private",json.dumps(r))
        self.assertEqual(sanitize({"persona":0,"bloqueo_oc":1,"orden_de_compra":"SECRET"})["orden_de_compra"],"[OMITIDO]")

    def test_public_params_omit_payee_filters(self):
        p=public_params({"where":'{"periodo":2025,"beneficiario":"SECRET"}'})
        self.assertNotIn("SECRET",json.dumps(p))
