#token engine 

import secrets

def generate_token(length=12):
    return secrets.token_urlsafe(length)
