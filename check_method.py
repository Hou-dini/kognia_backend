from jwt import PyJWKClient

client = PyJWKClient("http://example.com")
if hasattr(client, "get_signing_key_from_jwt"):
    print("get_signing_key_from_jwt exists")
else:
    print("get_signing_key_from_jwt does NOT exist")

if hasattr(client, "get_signing_key"):
    print("get_signing_key exists")
else:
    print("get_signing_key does NOT exist")
