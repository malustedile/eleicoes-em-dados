"""Decodificador BER mínimo, só para inspecionar/ler o bu.dat da urna."""
def tlv(b, i=0, end=None):
    end = len(b) if end is None else end
    while i < end:
        t0 = b[i]; i += 1
        cls, cons, tag = t0 >> 6, bool(t0 & 0x20), t0 & 0x1F
        if tag == 0x1F:
            tag = 0
            while True:
                x = b[i]; i += 1
                tag = (tag << 7) | (x & 0x7F)
                if not x & 0x80: break
        l = b[i]; i += 1
        if l & 0x80:
            n = l & 0x7F
            l = int.from_bytes(b[i:i+n], "big") if n else None
            i += n
        if l is None:  # indefinido
            raise ValueError("comprimento indefinido não suportado")
        yield cls, cons, tag, b[i:i+l]
        i += l

def dump(b, depth=0, maxd=6):
    for cls, cons, tag, v in tlv(b):
        pad = "  " * depth
        if cons and depth < maxd:
            print(f"{pad}[{cls}:{tag}] {{"); dump(v, depth+1, maxd); print(f"{pad}}}")
        else:
            try: s = v.decode("ascii") if v and all(32 <= c < 127 for c in v) else v.hex()
            except Exception: s = v.hex()
            if len(v) <= 8 and not s.isprintable(): s = f"{s} (int={int.from_bytes(v,'big')})"
            print(f"{pad}[{cls}:{tag}] {s[:80]}")
