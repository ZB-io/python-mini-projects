
import json
import yaml
from jsonschema import (
    Draft202012Validator,
    Draft7Validator,
    Draft4Validator,
    ValidationError,
)
from referencing import Registry, Resource
from typing import Dict, Any
import requests


class SwaggerSchemaValidator:
    """
    Validates JSON, XML, and text responses 
    """

    def __init__(self, swagger_source: str):
        self.spec = self._load_spec(swagger_source)
        self.is_swagger2 = False
        self.schemas = self._extract_schemas()
        self.registry = Registry()

        for name, schema in self.schemas.items():
            pointer = (
                f"#/definitions/{name}" if self.is_swagger2 
                else f"#/components/schemas/{name}"
            )

            wrapped = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                **schema,
            }
            self.registry = self.registry.with_resource(
                pointer,
                Resource.from_contents(wrapped)
            )

    def _load_spec(self, source: str) -> Dict[str, Any]:
        if source.startswith(("http://", "https://")):
            resp = requests.get(source)
            resp.raise_for_status()
            text = resp.text

            try:
                return yaml.safe_load(text)
            except yaml.YAMLError:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    raise ValueError("URL does not contain valid YAML or JSON")

        with open(source, "r") as f:
            text = f.read()

        if source.endswith((".yaml", ".yml")):
            return yaml.safe_load(text)
        if source.endswith(".json"):
            return json.loads(text)

        raise ValueError("File must be YAML or JSON")

    def _extract_schemas(self):
        if "components" in self.spec and "schemas" in self.spec["components"]:
            self.is_swagger2 = False
            return self.spec["components"]["schemas"]

        if "definitions" in self.spec:
            self.is_swagger2 = True
            return self.spec["definitions"]

        raise ValueError("No schemas found under components/schemas or definitions")

    def get_version(self):
        return self.spec.get("openapi") or self.spec.get("swagger") or ""

    def select_validator(self):
        v = self.get_version()

        if v.startswith("2."):
            return Draft4Validator          
        if v.startswith("3.0"):
            return Draft7Validator          
        if v.startswith("3.1"):
            return Draft202012Validator     

        return Draft202012Validator

    def resolve_ref(self, ref):
        if ref.startswith("#/"):
            parts = ref.lstrip("#/").split("/")
            node = self.spec
            for p in parts:
                node = node[p]
            return node

        raise ValueError(f"External refs not supported: {ref}")

    def deref(self, schema):
        if isinstance(schema, dict):
            if "$ref" in schema:
                resolved = self.resolve_ref(schema["$ref"])
                return self.deref(resolved)
            return {k: self.deref(v) for k, v in schema.items()}

        if isinstance(schema, list):
            return [self.deref(v) for v in schema]

        return schema

    def detect_format(self, response):
        ctype = response.headers.get("Content-Type", "").lower()
        if "json" in ctype:
            return "json"
        if "xml" in ctype:
            return "xml"
        if "text" in ctype:
            return "text"
        return "binary"

    def parse_body(self, response, fmt):
        if fmt == "json":
            return json.loads(response.text)

        if fmt == "xml":
            import xmltodict
            return xmltodict.parse(response.text)

        if fmt == "text":
            return response.text

        return response.content  

    def extract_schema_for_media_type(self, response_block, content_type):
        content = response_block.get("content", {})

        if content_type in content:
            return content[content_type].get("schema")

        if "json" in content_type:
            for k, v in content.items():
                if k == "application/json" or k.endswith("+json"):
                    return v.get("schema")

        if "xml" in content_type:
            for k, v in content.items():
                if "xml" in k:
                    return v.get("schema")

        if "text/plain" in content:
            return content["text/plain"].get("schema")

        return None


    def validate_schema_by_response(self, endpoint, method, status_code, response):
        fmt = self.detect_format(response)

        paths = self.spec.get("paths", {})
        op = paths.get(endpoint, {}).get(method.lower())

        if not op:
            return {"valid": False, "message": f"Method {method} not found at path {endpoint}"}

        responses = op.get("responses", {})
        response_block = responses.get(status_code)

        if not response_block:
            return {"valid": False, "message": f"No response block for {status_code}"}

        ctype = response.headers.get("Content-Type", "").split(";")[0].strip()

        if "content" in response_block:
            schema = self.extract_schema_for_media_type(response_block, ctype)
        else:
            schema = response_block.get("schema")

        if schema is None:
            return {"valid": True, "message": "No schema defined for this content type"}

        try:
            data = self.parse_body(response, fmt)
        except Exception as e:
            return {"valid": False, "message": f"Body parsing failed: {e}"}

        schema = self.deref(schema)

        validator_cls = self.select_validator()
        validator = validator_cls(schema, registry=self.registry)

        try:
            validator.validate(data)
            return {"valid": True}
        except ValidationError as e:
            return {
                "valid": False,
                "message": e.message,
                "path": list(e.path),
                "schema_path": list(e.schema_path),
            }  
