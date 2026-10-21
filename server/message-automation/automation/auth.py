"""Bearer OIDC; nenhum token em cookie, URL ou persistência da aplicação."""
import hashlib
import secrets
import jwt
from .domain import Invalid

class Verifier:
    def __init__(self,issuer='',audience='',jwks='',google_domain='',key_client=None):
        self.issuer=issuer;self.audience=audience;self.domain=google_domain
        self.client=key_client
        if issuer and audience and jwks:
            if not issuer.startswith('https://') or not jwks.startswith('https://'): raise Invalid('OIDC exige HTTPS.')
            self.client=key_client or jwt.PyJWKClient(jwks,timeout=5,lifespan=300)
    def verify(self,token,expected_nonce=None):
        if not self.client or not self.issuer or not self.audience: raise Invalid('Login ainda não configurado.')
        try:
            key=self.client.get_signing_key_from_jwt(token).key
            issuers=[self.issuer,'accounts.google.com'] if self.issuer=='https://accounts.google.com' else self.issuer
            claims=jwt.decode(token,key,algorithms=['RS256'],issuer=issuers,audience=self.audience,options={'require':['exp','iat','iss','sub','aud']},leeway=30)
            if not isinstance(claims['sub'],str) or not claims['sub'] or len(claims['sub'])>255: raise ValueError()
            if self.domain and (claims.get('hd')!=self.domain or claims.get('email_verified') is not True): raise ValueError()
            if claims.get('azp',self.audience)!=self.audience: raise ValueError()
            if expected_nonce is not None:
                actual=claims.get('nonce')
                if not isinstance(expected_nonce,str) or not 32<=len(expected_nonce)<=128 or not isinstance(actual,str) or not secrets.compare_digest(actual,expected_nonce): raise ValueError()
        except Exception: raise Invalid('Credencial inválida ou expirada.') from None
        return hashlib.sha256((self.issuer+'\0'+claims['sub']).encode()).hexdigest()
