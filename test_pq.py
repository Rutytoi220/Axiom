from axiom.server.pq_mesh import PQEncryptionLayer

def test_crypto():
    alice = PQEncryptionLayer()
    bob = PQEncryptionLayer()
    
    alice.derive_shared_key(bob.get_public_bytes())
    bob.derive_shared_key(alice.get_public_bytes())
    
    msg = b"Hello Post-Quantum World!"
    encrypted = alice.encrypt(msg)
    decrypted = bob.decrypt(encrypted)
    
    print("Crypto Test Success:", msg == decrypted)

test_crypto()
