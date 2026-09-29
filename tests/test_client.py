from __future__ import annotations
import unittest
from pa_biodiv.client import PresupuestoAbiertoClient, ValidationError, ApiError, _validate_api_url

class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

class ClientTests(unittest.TestCase):
    def test_sample_get_and_leading_zeros_no_implicit_filters(self):
        s = Session([Response([{"partida":"25","capitulo":"01"}])])
        c = PresupuestoAbiertoClient(session=s)
        c.search_records(where={"periodo":2025,"partida":"25","capitulo":"01"}, limit=1)
        import json
        params = s.calls[0][1]["params"]
        self.assertEqual(json.loads(params["where"])["capitulo"],"01")
        self.assertNotIn("where-not",params)
        self.assertNotIn("deuda_flotante",json.loads(params["where"]))
        self.assertFalse(s.calls[0][1]["allow_redirects"])

    def test_year_required_and_codes_not_numbers(self):
        c = PresupuestoAbiertoClient(session=Session([]))
        for where in ({}, {"periodo":"2025"}, {"periodo":True},
                      {"periodo":2025,"capitulo":1}, {"periodo":2025,"partida":[25]}):
            with self.assertRaises(ValidationError):
                c.search_records(where=where)
        self.assertEqual(c.session.calls,[])

    def test_no_custom_urls(self):
        for url in ("http://api.presupuestoabierto.gob.cl/api/v1/data/pagos.json",
                    "https://evil.example/api/v1/data/pagos.json",
                    "https://api.presupuestoabierto.gob.cl/api/v1/data/aprobados",
                    "https://api.presupuestoabierto.gob.cl/api/v1/data/pagos.json?x=1"):
            with self.assertRaises(ValidationError):
                _validate_api_url(url)

    def test_aggregate_compatible_contract_unknown_metric(self):
        s = Session([Response([{"subtitulo":"21","sum":5}])])
        c = PresupuestoAbiertoClient(session=s)
        self.assertEqual(c.summarize(where={"periodo":2025,"partida":"25"},group_by=["subtitulo"])[0]["sum"],5)
        self.assertEqual(set(s.calls[0][1]["params"]),{"where","group-by","limit","offset"})
        with self.assertRaises(ValidationError):
            c.summarize(where={"periodo":2025,"partida":"25"},group_by=["subtitulo"],metric="devengo")
        with self.assertRaises(ValidationError):
            c.summarize(where={"periodo":2025},group_by=["partida"])

    def test_invalid_fields_limits_operators(self):
        c = PresupuestoAbiertoClient(session=Session([]))
        for kwargs in ({"limit":1001}, {"select":["secret"]}, {"where":{"periodo":2025,"partida":{"gt":0}}},
                       {"where_not":{"devengo":0}}, {"apply_display_rules":True}):
            with self.assertRaises(ValidationError):
                c.search_records(where={"periodo":2025}, **{k:v for k,v in kwargs.items() if k!="where"}) if "where" not in kwargs else c.search_records(**kwargs)

    def test_dataset_specific_fields(self):
        c = PresupuestoAbiertoClient(session=Session([]))
        with self.assertRaises(ValidationError):
            c.search_records(dataset="municipios",where={"periodo":2025,"partida":"25"})
        with self.assertRaises(ValidationError):
            c.search_records(dataset="../private",where={"periodo":2025})

    def test_http_errors_are_sanitized(self):
        for response in (Response({"internal":"password"},500), Response(ValueError("bad"))):
            with self.assertRaises(ApiError) as error:
                PresupuestoAbiertoClient(session=Session([response])).search_records(where={"periodo":2025})
            self.assertNotIn("password",str(error.exception))
            self.assertNotIn("internal",str(error.exception))

    def test_institution_name_variants_in_list(self):
        s = Session([Response([])])
        PresupuestoAbiertoClient(session=s).search_records(where={"periodo":2025,"nombre_beneficiario":["PRIMER TRIBUNAL AMBIENTAL","ILUSTRE PRIMER TRIBUNAL AMBIENTAL"]})
        import json
        self.assertEqual(len(json.loads(s.calls[0][1]["params"]["where"])["nombre_beneficiario"]),2)
