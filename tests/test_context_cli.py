from __future__ import annotations
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pa_biodiv.cli import main,parser,run
from pa_biodiv.context import build_context,verify_resources,resources
from pa_biodiv.bulk import aggregate_biodiversity,iter_tsv_records,BulkDataError
from test_client import Response,Session

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"tests/fixtures/pagos-small.tsv"

class ContextTests(unittest.TestCase):
    def test_deterministic_with_limit_and_references(self):
        a=build_context()
        self.assertEqual(a,build_context())
        self.assertLessEqual(len(re.findall(r"\S+",a)),3000)
        self.assertEqual(list(verify_resources()["reference_counts"].values()),[144,144])
        self.assertIn("byte a byte",a)

    def test_readme_links_exist(self):
        for p in [ROOT/"README.md"]:
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
                if not link.startswith("https://"):
                    self.assertTrue((p.parent/link).exists(),link)

    def test_commands_in_docs_parse(self):
        examples=[
        ["sample","--year","2025","--where",'{"partida":"25","capitulo":"01"}',"--limit","1"],
        ["catalog","--year","2025","--where",'{"partida":"25"}',"--group-by","capitulo,nombre_capitulo"],
        ["aggregate","--year","2025","--where",'{"partida":"25"}',"--group-by","subtitulo,nombre_subtitulo"],
        ["payees","--year","2025","--query","Primer Tribunal Ambiental"],
        ["scan","--input",str(FIXTURE),"--year","2025"],
        ["context","build"],["verify"],["verify","--live","--year","2025"],
        ["download","--year","2025","--dataset","pagos"]]
        for args in examples:
            parser().parse_args(args)

    def test_offline_verify_and_context_do_not_call_network(self):
        with patch("requests.Session.get",side_effect=AssertionError("network")):
            self.assertEqual(run(parser().parse_args(["verify"]))["network"],False)
            with tempfile.TemporaryDirectory() as d:
                target=Path(d)/"context.md"
                run(parser().parse_args(["context","build","--output",str(target)]))
                self.assertEqual(target.read_text(),build_context())

    def test_scan_no_attribution_and_hashes(self):
        result=run(parser().parse_args(["scan","--input",str(FIXTURE),"--year","2025"]))
        self.assertEqual(result["observed"]["total_devengo"],1250)
        self.assertIsNone(result["attribution"])
        self.assertFalse(result["sources"][0]["references_applied"])
        self.assertEqual(len(result["sources"][0]["sha256"]),64)

    def test_wrong_year_rejected(self):
        with self.assertRaises(BulkDataError):
            aggregate_biodiversity(FIXTURE,year=2024)

    def test_negative_adjustments_kept(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"negative.tsv"
            text=FIXTURE.read_text().replace("\t1000\t1000\t1000\t1000\t","\t-100\t-100\t-100\t-100\t")
            p.write_text(text)
            self.assertEqual(aggregate_biodiversity(p)["total_devengo"],150)

    def test_invalid_or_empty_stream_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"empty.tsv"
            p.write_text(FIXTURE.read_text().splitlines()[0]+"\n")
            self.assertIsNone(aggregate_biodiversity(p)["total_devengo"])
            p.write_text(FIXTURE.read_text().replace("\t1000\t1000\t1000\t1000\t","\t1000\t1000\t1000\tinvalid\t"))
            self.assertIsNone(aggregate_biodiversity(p)["total_devengo"])

    def test_bad_headers_and_short_rows_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.tsv"
            for text in ("partida\n25\n","periodo\tdevengo\n2025\n","periodo\tperiodo\tdevengo\n"):
                p.write_text(text)
                with self.assertRaises(BulkDataError):
                    list(iter_tsv_records(p))

    def test_empty_query_no_zero_and_catalog_no_sum(self):
        with tempfile.TemporaryDirectory() as d:
            for command,body in [("sample",[]),("catalog",[{"capitulo":"01","sum":42}])]:
                transport=Session([Response(body)])
                with patch("pa_biodiv.evidence._build_session",return_value=transport):
                    result=run(parser().parse_args([command,"--year","2025","--where",'{"partida":"25"}',"--cache-dir",d]))
                if command=="sample":
                    self.assertEqual(result["completeness"],"empty_not_zero")
                    self.assertIn("no implica gasto cero"," ".join(result["warnings"]))
                else:
                    self.assertNotIn("sum",result["observed"][0])

    def test_cli_structured_output(self):
        buffer=io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(["verify"]),0)
        self.assertEqual(json.loads(buffer.getvalue())["version"],"0.1.0")
