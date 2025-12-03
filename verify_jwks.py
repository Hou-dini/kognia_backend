import jwt
import os
import sys
from jwt import PyJWKClient

def verify_token(token, jwks_url):
    print(f"Verifying token against JWKS URL: {jwks_url}")
    
    audience = os.environ.get("JWT_AUDIENCE", "authenticated")
    issuer = os.environ.get("JWT_ISSUER", "")
    
    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                "verify_aud": True,
                "verify_iss": True,
            }
        )
        
        print("\nSUCCESS: Token verified successfully!")
        print(f"User ID (sub): {payload.get('sub')}")
        print(f"Payload: {payload}")
        return True
        
    except jwt.ExpiredSignatureError:
        print("\nERROR: Token has expired.")
    except jwt.InvalidSignatureError as e:
        print(f"\nERROR: Invalid signature: {e}")
    except jwt.PyJWTError as e:
        print(f"\nERROR: JWT Error: {e}")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")
    
    return False

if __name__ == "__main__":
    print("--- JWKS Verification Tool ---")
    
    jwks_url = os.environ.get("JWKS_URL")
    if not jwks_url:
        jwks_url = input("Enter JWKS URL (e.g., https://<project>.supabase.co/auth/v1/.well-known/jwks.json): ").strip()
    
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = input("Enter JWT Token: ").strip()
        
    if not jwks_url:
        print("Error: JWKS URL is required.")
        exit(1)
        
    if not token:
        print("Error: Token is required.")
        exit(1)
        
    verify_token(token, jwks_url)
