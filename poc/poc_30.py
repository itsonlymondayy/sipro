#!/usr/bin/env python3
"""POC Fase 30b — kompresi + watermark + thumbnail foto (ISOLASI, tanpa server).

Membuktikan bagian paling berisiko dulu: apakah pipeline Pillow benar-benar
(1) menghemat kuota, (2) membuang metadata EXIF/GPS, (3) mencetak watermark yang
terlihat, (4) membuat thumbnail, dan (5) tidak pernah menggagalkan unggahan.
"""
import io
import sys

sys.path.insert(0, "/app/backend")

from PIL import Image  # noqa: E402
import photo_utils as pu  # noqa: E402

passed, failed = 0, 0


def check(name, cond, info=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}" + (f" — {info}" if info else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {info}" if info else ""))


def camera_photo(w=3024, h=4032) -> bytes:
    """Foto ala kamera HP: gradien + derau supaya JPEG-nya besar & realistis."""
    import random
    img = Image.new("RGB", (w, h))
    px = img.load()
    random.seed(7)
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            base = (int(x * 255 / w), int(y * 255 / h), 128)
            jitter = random.randint(-28, 28)
            col = tuple(max(0, min(255, c + jitter)) for c in base)
            for dy in range(4):
                for dx in range(4):
                    if x + dx < w and y + dy < h:
                        px[x + dx, y + dy] = col
    buf = io.BytesIO()
    exif = img.getexif()
    exif[274] = 6                      # Orientation: butuh diputar
    exif[271] = "SIPRO-CAM"            # Make
    gps = exif.get_ifd(0x8825)         # GPS palsu (yang WAJIB dibuang demi privasi)
    gps[1] = "S"
    gps[2] = (6.0, 10.0, 30.0)
    img.save(buf, format="JPEG", quality=95, exif=exif.tobytes())
    return buf.getvalue()


def main():
    print("\n=== POC 30b: kompresi + watermark foto lapangan ===\n")
    raw = camera_photo()
    print(f"  foto sumber: {len(raw) / 1024:.0f} KB, 3024x4032, ada EXIF orientation+GPS")

    lines = pu.context_lines(org_name="PT SIPRO Land",
                             context="Cluster Asri Blok A · Kavling A-01")
    res = pu.optimize(raw, watermark_lines=lines)
    check("optimize() mengembalikan hasil", bool(res))
    if not res:
        sys.exit(1)

    check("sisi terpanjang <= 1600 px", max(res["width"], res["height"]) <= 1600,
          f'{res["width"]}x{res["height"]}')
    # EXIF Orientation=6 berarti "putar 90° saat ditampilkan": piksel tersimpan potrait,
    # tampilan seharusnya LANDSCAPE. Setelah transpose, hasil harus benar-benar landscape.
    check("orientasi EXIF diterapkan (potrait tersimpan -> landscape tampil)",
          res["width"] > res["height"], f'{res["width"]}x{res["height"]}')
    hemat = pu.saving_pct(res["original_size"], res["size"])
    check("hemat kuota >= 70%", hemat >= 70,
          f'{res["original_size"] / 1024:.0f} KB -> {res["size"] / 1024:.0f} KB (hemat {hemat}%)')

    out = Image.open(io.BytesIO(res["data"]))
    check("metadata EXIF/GPS dibuang", not dict(out.getexif()),
          f"exif keys={list(dict(out.getexif()).keys())}")
    check("format keluaran JPEG", out.format == "JPEG" and res["content_type"] == "image/jpeg")

    # Watermark: bilah bawah harus jauh lebih gelap daripada bagian tengah gambar.
    px = out.convert("RGB").load()
    bar = [sum(px[x, out.height - 12]) / 3 for x in range(0, out.width, 40)]
    mid = [sum(px[x, out.height // 2]) / 3 for x in range(0, out.width, 40)]
    check("bilah watermark tercetak di bawah", (sum(mid) / len(mid)) - (sum(bar) / len(bar)) > 25,
          f"terang tengah={sum(mid) / len(mid):.0f} vs bilah={sum(bar) / len(bar):.0f}")
    check("teks watermark memuat kavling + tanggal WIB",
          "A-01" in (res["watermark"] or "") and "WIB" in (res["watermark"] or ""),
          res["watermark"])

    thumb = Image.open(io.BytesIO(res["thumb"]))
    check("thumbnail <= 480 px", max(thumb.size) <= 480, f"{thumb.size}")
    check("thumbnail lebih kecil dari foto penuh", res["thumb_size"] < res["size"],
          f'{res["thumb_size"] / 1024:.0f} KB vs {res["size"] / 1024:.0f} KB')

    # PNG transparan (tangkapan layar) tidak boleh error & harus jadi JPEG putih.
    png = Image.new("RGBA", (900, 600), (0, 0, 0, 0))
    b = io.BytesIO()
    png.save(b, format="PNG")
    r2 = pu.optimize(b.getvalue(), watermark_lines=lines)
    check("PNG transparan diproses tanpa error", bool(r2) and r2["content_type"] == "image/jpeg")

    # Gambar sangat kecil: tetap dikompres, watermark dilewati (tidak menutupi gambar).
    tiny = Image.new("RGB", (120, 90), (200, 30, 30))
    b = io.BytesIO()
    tiny.save(b, format="PNG")
    r3 = pu.optimize(b.getvalue(), watermark_lines=lines)
    check("gambar mungil tetap diproses", bool(r3) and max(r3["width"], r3["height"]) == 120)

    # Berkas rusak / bukan gambar: HARUS None (pemanggil menyimpan berkas asli).
    check("berkas rusak -> None (unggahan tidak gagal)",
          pu.optimize(b"bukan-gambar-sama-sekali", watermark_lines=lines) is None)
    check("PDF tidak dianggap gambar", not pu.is_image("application/pdf", "slik.pdf"))
    check("JPEG dikenali gambar", pu.is_image("image/jpeg", "foto.jpg"))

    print(f"\n=== HASIL POC: {passed} PASS, {failed} FAIL ===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
