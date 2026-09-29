from __future__ import annotations
import unittest
from pa_biodiv.workflows import payees_all
from pa_biodiv.client import ApiError, ValidationError

def page(total, start, count):
    return {"total":total,"items":[{"_id":str(i),"nombre_beneficiario":"ENTIDAD FICTICIA","persona":0} for i in range(start,start+count)]}

class Client:
    def __init__(self,pages):
        self.pages,self.offsets=list(pages),[]
    def search_payees(self,query,**kwargs):
        self.offsets.append(kwargs["offset"])
        p=self.pages.pop(0)
        if isinstance(p,Exception):
            raise p
        return p

class WorkflowTests(unittest.TestCase):
    def test_complete_pagination(self):
        c=Client([page(122,0,100),page(122,100,22)])
        result=payees_all(c,"Primer Tribunal Ambiental",year=2025)
        self.assertEqual(c.offsets,[0,100])
        self.assertTrue(result["pagination_complete"])
        self.assertEqual(result["returned"],122)
        self.assertIn("gasto propio"," ".join(result["warnings"]))

    def test_max_pages_partial(self):
        r=payees_all(Client([page(122,0,100)]),"tribunal",year=2025,max_pages=1)
        self.assertFalse(r["pagination_complete"])

    def test_error_after_first_page_is_partial(self):
        r=payees_all(Client([page(122,0,100),ApiError("HTTP 504")]),"tribunal",year=2025)
        self.assertFalse(r["pagination_complete"])
        self.assertEqual(r["returned"],100)

    def test_duplicate_or_changed_total_not_complete(self):
        for pp in ([page(122,0,100),page(122,0,22)],[page(122,0,100),page(123,100,23)]):
            self.assertFalse(payees_all(Client(pp),"tribunal",year=2025)["pagination_complete"])

    def test_empty_index_is_complete_not_gasto_zero(self):
        r=payees_all(Client([page(0,0,0)]),"tribunal",year=2025)
        self.assertTrue(r["pagination_complete"])
        self.assertNotIn("total_devengo",r)

    def test_bad_page_limit(self):
        with self.assertRaises(ValidationError):
            payees_all(Client([]),"tribunal",year=2025,max_pages=0)
