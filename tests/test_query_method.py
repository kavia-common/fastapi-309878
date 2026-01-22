from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: Optional[float] = None


@app.query("/items/{item_id}")
def query_item(item_id: str, item: Item):
    # Body parsing should work the same as with other methods when a body is declared.
    return {"item_id": item_id, "item": item}


client = TestClient(app)


def test_query_routing_and_body():
    response = client.request("QUERY", "/items/foo", json={"name": "Foo"})
    assert response.status_code == 200, response.text
    assert response.json() == {"item_id": "foo", "item": {"name": "Foo", "price": None}}


def test_query_405_allow_header_includes_query():
    # A GET against a path that only supports QUERY should return 405 and include
    # QUERY in the Allow header.
    response = client.get("/items/foo")
    assert response.status_code == 405, response.text
    assert "allow" in response.headers
    # Allow header ordering is not guaranteed across stacks; assert inclusion.
    assert "QUERY" in response.headers["allow"]


def test_openapi_includes_query_operation_and_request_body():
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["paths"]["/items/{item_id}"]["query"]["x-fastapi-method"] == "QUERY"
    assert data["paths"]["/items/{item_id}"]["query"]["requestBody"]["required"] is True
    assert data["paths"]["/items/{item_id}"]["query"]["requestBody"]["content"] == {
        "application/json": {"schema": {"$ref": "#/components/schemas/Item"}}
    }
