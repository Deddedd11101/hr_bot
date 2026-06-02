import unittest

from fastapi.testclient import TestClient

from app.main import app


class OpenApiSchemaTests(unittest.TestCase):
    def test_swagger_alias_redirects_to_fastapi_docs(self) -> None:
        client = TestClient(app)

        response = client.get("/swagger", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers.get("location"), "/docs")

    def test_swagger_schema_is_limited_to_json_api_routes(self) -> None:
        schema = app.openapi()
        paths = schema["paths"]

        self.assertIn("/api/employees", paths)
        self.assertIn("/api/flows/workspace", paths)
        self.assertIn("/api/bulk-actions/workspace", paths)
        self.assertIn("/api/settings/workspace", paths)
        self.assertNotIn("/login", paths)
        self.assertNotIn("/swagger", paths)
        self.assertNotIn("/app/employees", paths)
        self.assertNotIn("/employees", paths)
        self.assertNotIn("/flows/{scenario_id}", paths)

    def test_swagger_schema_groups_api_routes_by_domain(self) -> None:
        schema = app.openapi()

        self.assertEqual(schema["paths"]["/api/employees"]["get"]["tags"], ["Employees"])
        self.assertEqual(schema["paths"]["/api/flows/workspace"]["get"]["tags"], ["Flows and surveys"])
        self.assertEqual(schema["paths"]["/api/bulk-actions/workspace"]["get"]["tags"], ["Bulk actions"])
        self.assertEqual(schema["paths"]["/api/settings/workspace"]["get"]["tags"], ["Settings"])
        self.assertEqual(schema["paths"]["/api/accounts"]["post"]["tags"], ["Admin accounts"])


if __name__ == "__main__":
    unittest.main()
