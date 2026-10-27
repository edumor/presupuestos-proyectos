# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Eduardo José Moreno. Desarrollo e Implementación: Lic. Eduardo J. Moreno
"""Firma Ed25519 en Python puro, según el código de referencia de RFC 8032 (sección 6).

Se usa solo para validar claves de licencia (y generarlas con scripts/generar_licencia.py);
no es una implementación de tiempo constante, así que no debe usarse para otros fines.
"""
import hashlib

p = 2 ** 255 - 19
q = 2 ** 252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, p - 2, p) % p
modp_sqrt_m1 = pow(2, (p - 1) // 4, p)


def _sha512(s: bytes) -> bytes:
    return hashlib.sha512(s).digest()


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(_sha512(s), "little") % q


def _add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % p, (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C, D = 2 * P[3] * Q[3] * d % p, 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F, G * H, F * G, E * H)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _recover_x(y: int, sign: int):
    if y >= p:
        return None
    x2 = (y * y - 1) * pow(d * y * y + 1, p - 2, p)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p != 0:
        x = x * modp_sqrt_m1 % p
    if (x * x - x2) % p != 0:
        return None
    if (x & 1) != sign:
        x = p - x
    return x


g_y = 4 * pow(5, p - 2, p) % p
g_x = _recover_x(g_y, 0)
G = (g_x, g_y, 1, g_x * g_y % p)


def _compress(P) -> bytes:
    zinv = pow(P[2], p - 2, p)
    x, y = P[0] * zinv % p, P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % p)


def _expand(secret: bytes):
    if len(secret) != 32:
        raise ValueError("La clave privada debe tener 32 bytes")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def clave_publica(secret: bytes) -> bytes:
    a, _ = _expand(secret)
    return _compress(_mul(a, G))


def firmar(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(secret)
    A = _compress(_mul(a, G))
    r = _sha512_modq(prefix + msg)
    Rs = _compress(_mul(r, G))
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % q
    return Rs + int.to_bytes(s, 32, "little")


def verificar(public: bytes, msg: bytes, firma: bytes) -> bool:
    if len(public) != 32 or len(firma) != 64:
        return False
    A = _decompress(public)
    if not A:
        return False
    R = _decompress(firma[:32])
    if not R:
        return False
    s = int.from_bytes(firma[32:], "little")
    if s >= q:
        return False
    h = _sha512_modq(firma[:32] + public + msg)
    return _equal(_mul(s, G), _add(R, _mul(h, A)))
