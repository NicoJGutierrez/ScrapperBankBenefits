"""
Extractor de datos desde los JSON generados por el scrapper.
Incluye:
- `extract_weekdays` (copiado del scrapper previo)
- normalización y extracción de descuentos
- funciones para procesar uno o varios archivos JSON y producir
  un JSON con campos normalizados listos para aplicar regex personalizados.

Uso:
  python extractor.py --inputs "./*.json" --out extracted.json

Opcional: pasar un archivo JSON con patrones para `--patterns`.
"""

import re
import json
import argparse
import glob
from typing import List, Dict, Optional
import os


def extract_weekdays(text: str) -> List[str]:
    text_l = (text or "").lower()
    # normalizar acentos para facilitar matching
    norm = text_l.replace("á", "a").replace("é", "e").replace(
        "í", "i").replace("ó", "o").replace("ú", "u")

    days_order = ["lunes", "martes", "miercoles",
                  "jueves", "viernes", "sabado", "domingo"]

    added: List[str] = []

    # Si aparece "todos los dias" o variantes, devolver toda la semana
    if re.search(r"\btodos(?: los)? dias?\b", norm):
        return [d.capitalize() for d in days_order]

    # detectar rangos: "lunes a viernes", "martes al sabado", "lunes - viernes"
    range_pattern = re.compile(
        r"\b(" + "|".join(days_order) + r")\s*(?:a|al|[-–—])\s*(" + "|".join(days_order) + r")\b")
    for m in range_pattern.finditer(norm):
        start = m.group(1)
        end = m.group(2)
        i = days_order.index(start)
        j = days_order.index(end)
        k = i
        while True:
            day = days_order[k]
            if day not in added:
                added.append(day)
            if k == j:
                break
            k = (k + 1) % len(days_order)

    # detectar días sueltos que no estén ya en added
    for d in days_order:
        if re.search(r"\b" + re.escape(d) + r"\b", norm) and d not in added:
            added.append(d)

    return [d.capitalize() for d in added]


def normalize_discount(text: str) -> Optional[str]:
    """Intenta extraer y normalizar un valor de descuento (p.ej. '40%')."""
    if not text:
        return None
    t = text.strip().lower()
    # eliminar palabras comunes
    t = re.sub(r"\b(dcto|dcto\.|descuento|dto\.|dto)\b", "", t)
    # buscar porcentaje
    m = re.search(r"(\d{1,3}(?:[.,]\d+)?%)", t)
    if m:
        # reemplazar coma por punto solo en parte numérica si hace falta
        val = m.group(1).replace(',', '.')
        return val
    # buscar montos (ej: $5.000 ó 5000)
    m2 = re.search(r"\$?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]+)?)", t)
    if m2:
        return m2.group(1).replace('.', '').replace(',', '.')
    return None


DEFAULT_PATTERNS = {
    # las claves pueden usarse para buscar dentro de title/description/discount
    # el usuario puede proporcionar su propio archivo de patterns JSON.
    "discount": r"(\d{1,3}(?:[.,]\d+)?%)",
}


def extract_fields_from_benefit(ben: Dict, patterns: Dict[str, str]) -> Dict:
    """Toma un benefit (como en los JSON generados por el scrapper)
    y devuelve una copia con campos normalizados: `parsed_discount`, `valid_days`.
    """
    out = ben.copy()
    # Primero intentar normalizar el campo discount puro
    parsed = None
    parsed = normalize_discount(out.get("discount", ""))
    if not parsed:
        # intentar buscar en title y description
        parsed = normalize_discount(out.get("company", "")) or normalize_discount(
            out.get("description", ""))

    out["parsed_discount"] = parsed or ""

    # obtener dias válidos usando extract_weekdays sobre description
    days = extract_weekdays(out.get("description", ""))
    # si no hay días en description, intentar en company
    if not days:
        days = extract_weekdays(out.get("company", ""))
    out["valid_days_parsed"] = days

    # aplicar patrones adicionales provistos por el usuario (regex que extraen grupos)
    for key, pat in (patterns or {}).items():
        if key == "discount":
            continue
        try:
            regex = re.compile(pat, re.IGNORECASE)
        except re.error:
            continue
        # buscar en description, title y discount
        txt = " ".join([out.get("company", ""), out.get(
            "description", ""), out.get("discount", "")])
        m = regex.search(txt)
        out[f"pattern_{key}"] = m.group(0) if m else ""

    return out


def process_files(input_glob: str, out_path: str, patterns: Optional[Dict[str, str]] = None):
    files = glob.glob(input_glob)
    if not files:
        # si el usuario pasó un directorio, procesar todos los *.json en él
        if os.path.isdir(input_glob):
            files = glob.glob(os.path.join(input_glob, "*.json"))
    results = []
    for fp in sorted(files):
        with open(fp, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                continue
        # data puede ser una lista con un solo banco
        banks = data if isinstance(data, list) else [data]
        for bank in banks:
            bank_id = bank.get("id") or bank.get(
                "name") or os.path.basename(fp)
            for ben in bank.get("benefits", []):
                parsed = extract_fields_from_benefit(ben, patterns or {})
                parsed_entry = {
                    "bank_id": bank_id,
                    "bank_name": bank.get("name", ""),
                    **parsed,
                }
                results.append(parsed_entry)
    # guardar resultados
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Extracción guardada en {out_path} (elementos: {len(results)})")


def load_patterns_from_file(path: str) -> Dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(
        description="Extractor: normaliza campos y aplica regex a los JSON de scrapper")
    ap.add_argument("--inputs", default="./*.json",
                    help="Glob o ruta (o directorio) con JSONs a procesar")
    ap.add_argument("--out", default="extracted.json",
                    help="Archivo de salida con resultados")
    ap.add_argument("--patterns", default=None,
                    help="Archivo JSON con patrones adicionales")
    args = ap.parse_args()

    patterns = {}
    if args.patterns:
        patterns = load_patterns_from_file(args.patterns)
    # fusionar con defaults (no sobrescribir si ya definidos)
    merged = dict(DEFAULT_PATTERNS)
    merged.update(patterns or {})

    process_files(args.inputs, args.out, merged)


if __name__ == "__main__":
    main()
