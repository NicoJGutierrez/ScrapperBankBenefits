"""
Convierte JSONs de un banco (formato scrapper) al formato de ejemplo en `formato.txt`.

Uso:
  python convert_to_formato.py scotiabank.json

Salida: mismo archivo con sufijo `_formated.json` en el mismo directorio.

Se reutiliza la lógica de `extractor.py` para parsear días y normalizar descuentos.
"""

import json
import os
import argparse
from typing import List

from extractor import extract_weekdays, normalize_discount


def convert_bank_object(bank: dict) -> dict:
    bank_id = bank.get("id") or bank.get("name") or "bank_unknown"
    bank_name = bank.get("name") or bank_id

    # El scrapper original usa "items" en algunos outputs
    items = bank.get("items") or bank.get("benefits") or []

    benefits = []
    for i, item in enumerate(items, start=1):
        # generar id consistente: ben_<bankid>_<nnn>
        safe_bank = bank_id.replace(" ", "_")
        ben_id = f"ben_{safe_bank}_{i:03d}"

        company = item.get("title") or item.get("company") or ""
        discount = item.get("discount") or ""
        description = item.get("extra") or item.get("description") or ""

        valid_days = extract_weekdays(description)
        parsed_discount = normalize_discount(discount) or ""

        ben = {
            "id": ben_id,
            "company": company,
            "discount": discount,
            "category": "",
            "description": description,
            "valid_until": "",
            "valid_days": valid_days,
            "requirements": "",
            "parsed_discount": parsed_discount,
        }
        benefits.append(ben)

    return {
        "id": bank_id,
        "name": bank_name,
        "benefits": benefits,
    }


def convert_file(input_path: str, output_path: str = None) -> str:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    banks = data if isinstance(data, list) else [data]
    converted = [convert_bank_object(b) for b in banks]

    out_obj = converted[0] if len(converted) == 1 else converted

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = base + "_formated" + ext

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    ap = argparse.ArgumentParser(
        description="Convertir JSON scrapper a formato ejemplo")
    ap.add_argument("input", help="Archivo JSON de entrada (un banco)")
    ap.add_argument("--out", help="Archivo JSON de salida opcional")
    args = ap.parse_args()

    out = convert_file(args.input, args.out)
    # Resumen conciso
    print(f"Archivo generado: {out}")


if __name__ == "__main__":
    main()
