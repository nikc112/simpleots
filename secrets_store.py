# -*- coding: utf-8 -*-

import os
import hashlib
import base64

import redis
from cryptography.fernet import Fernet


def _build_fernet_key():
    """
    Aus MASTER_KEY einen gueltigen Fernet-Key ableiten.
    So gibt es nur einen Key in der Config, aber eine eigene
    Ableitung fuer die Verschluesselung.
    """
    master = os.getenv("MASTER_KEY")
    if not master:
        raise RuntimeError("MASTER_KEY ist nicht gesetzt! Bitte in der Umgebung konfigurieren.")

    if isinstance(master, str):
        master = master.encode("utf-8")

    # Kontext "crypt" -> unterscheidet sich von APP_SECRET
    digest = hashlib.sha256(master + b"crypt").digest()
    return base64.urlsafe_b64encode(digest)


class SecretsStore:
    def __init__(self):
        host = os.getenv("REDIS_HOST", "redis")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))

        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=False)
        self.fernet = Fernet(_build_fernet_key())

    def save(self, token, value, ttl):
        """
        Passwort verschluesselt nach Redis schreiben.
        Key:   secret:<token>
        Value: verschluesselter Text
        TTL:   ueber Redis-Expire
        """
        key = f"secret:{token}"
        if isinstance(value, str):
            value = value.encode("utf-8")

        ciphertext = self.fernet.encrypt(value)
        self.redis.setex(key, int(ttl), ciphertext)

    def read(self, token):
        """
        Passwort lesen und danach loeschen (One-Time).
        Versucht GETDEL, faellt bei alten Versionen auf GET+DEL zurueck.
        """
        key = f"secret:{token}"

        value = None
        try:
            value = self.redis.getdel(key)
        except AttributeError:
            pipe = self.redis.pipeline()
            pipe.get(key)
            pipe.delete(key)
            value, _ = pipe.execute()

        if not value:
            return None

        try:
            plaintext = self.fernet.decrypt(value)
        except Exception:
            return None

        return plaintext.decode("utf-8")

    def clear_all(self):
        """
        Alle Secrets loeschen (Factory Reset).
        Achtung: loescht die komplette Redis-DB fuer diese App.
        """
        self.redis.flushdb()
