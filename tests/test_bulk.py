from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from pa_biodiv.bulk import (
    aggregate_biodiversity,
    annual_download_url,
    download_annual,
    iter_tsv_records,
    load_biodiversity_profile,
)
from pa_biodiv.client import ValidationError


FIXTURE = Path(__file__).parent / "fixtures" / "pagos-small.tsv"


class DownloadResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
        self.closed = False

    def iter_content(self, chunk_size):
        for index in range(0, len(self.body), max(1, chunk_size // 2)):
            yield self.body[index : index + max(1, chunk_size // 2)]

    def close(self):
        self.closed = True


class DownloadSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class BulkTests(unittest.TestCase):
    def test_iter_tsv_streams_fixture(self):
        rows = list(iter_tsv_records(FIXTURE))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["partida"], "25")
        self.assertEqual(rows[-1]["devengo"], "250")

    def test_profile_is_unicode_normalised_and_budget_only(self):
        profile = load_biodiversity_profile()
        matches = profile.match({"nombre_asignacion": "ÁREAS MARINAS PROTEGIDAS"})
        self.assertIn("areas_protegidas", matches)
        self.assertEqual(
            profile.match({"nombre_beneficiario": "Fundación Biodiversidad"}),
            [],
        )

    def test_aggregate_applies_portal_display_rules(self):
        result = aggregate_biodiversity(FIXTURE, sample_limit=2)
        self.assertEqual(result["dataset_rows"], 5)
        self.assertEqual(result["eligible_rows"], 3)
        self.assertEqual(result["matched_rows"], 2)
        self.assertEqual(result["total_devengo"], 1250)
        self.assertEqual(
            [row["partida"] for row in result["by_partida"]], ["25", "12"]
        )
        self.assertEqual(len(result["examples"]), 2)
        self.assertNotIn("beneficiario", result["examples"][0])
        self.assertTrue(
            result["classification_coverage"]["estimate_available"]
        )

    def test_aggregate_can_explicitly_include_hidden_rows(self):
        result = aggregate_biodiversity(FIXTURE, mimic_api=False, sample_limit=0)
        self.assertEqual(result["eligible_rows"], 5)
        self.assertEqual(result["matched_rows"], 4)
        self.assertEqual(result["total_devengo"], 1750)

    def test_iter_tsv_handles_large_field_values(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "large-field.tsv"
            huge = "X" * 200_000
            target.write_text(
                f"periodo\tdevengo\tnombre_partida\n2025\t150\t{huge}\n",
                encoding="utf-8",
            )
            rows = list(iter_tsv_records(target))
            self.assertEqual(rows[0]["nombre_partida"], huge)
            self.assertEqual(rows[0]["devengo"], "150")

    def test_download_is_gzip_validated_atomic_and_cached(self):
        content = gzip.compress(FIXTURE.read_bytes())
        response = DownloadResponse(content)
        session = DownloadSession(response)
        with tempfile.TemporaryDirectory() as directory:
            target = download_annual(
                2025,
                directory,
                session=session,
                chunk_size=16 * 1024,
            )
            self.assertEqual(target.name, "pagos-2025.gz")
            self.assertEqual(list(iter_tsv_records(target))[0]["periodo"], "2025")
            self.assertTrue(response.closed)
            cached = download_annual(
                2025,
                directory,
                session=DownloadSession(DownloadResponse(b"not used")),
            )
            self.assertEqual(cached, target)
            self.assertEqual(len(session.calls), 1)
            self.assertFalse(session.calls[0][1]["allow_redirects"])

    def test_annual_url_has_no_arbitrary_path_escape(self):
        self.assertEqual(
            annual_download_url(2025),
            "https://api.presupuestoabierto.gob.cl/data/pagos-2025.gz",
        )
        with self.assertRaises(ValidationError):
            annual_download_url(2015)
        with self.assertRaises(ValidationError):
            annual_download_url(2025, dataset="../../private")


if __name__ == "__main__":
    unittest.main()
