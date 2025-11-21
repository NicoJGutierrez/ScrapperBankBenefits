from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
from itertools import zip_longest
import argparse
import json
import re
from typing import List, Dict, Optional


class BankParser:
    """Base parser class. Subclases deben definir selectores y parsear textos."""

    bank_id = "banco_000"
    bank_name = "Generic Bank"
    # selectores CSS para las partes que queremos extraer
    selector_title: Optional[str] = None
    selector_discount: Optional[str] = None
    selector_extra: Optional[str] = None

    def __init__(self):
        pass

    def parse_items(self, items: List[Dict[str, str]]) -> Dict:
        """Recibe lista de dicts con keys 'title','discount','extra' y devuelve dict del banco."""
        benefits = []
        for i, it in enumerate(items, start=1):
            ben = self._parse_benefit(i, it)
            benefits.append(ben)

        return {
            "id": self.bank_id,
            "name": self.bank_name,
            "benefits": benefits,
        }

    def _parse_benefit(self, index: int, it: Dict[str, str]) -> Dict:
        """Generador simple de benefit. Subclases pueden sobreescribirlo."""
        company = it.get("title", "").strip()
        discount = it.get("discount", "").strip().strip(" dcto.")
        extra = it.get("extra", "").strip()

        # extra: usarlo como descripción y extraer días si aparecen
        valid_days = extract_weekdays(extra)

        return {
            "id": f"ben_{index:03d}",
            "company": company,
            "discount": discount,
            "category": "",
            "description": extra,
            "valid_until": "",
            "valid_days": valid_days,
            "requirements": "",
        }


class BankChileParser(BankParser):
    bank_id = "banco_001"
    bank_name = "Banco de Chile"
    selector_title = ".font-700.text-3.text-gray-dark.mb-2.overflow-ellipsis"
    selector_discount = ".font-700.text-3.text-primary.mb-2.overflow-ellipsis"
    selector_extra = ".overflow-ellipsis.mb-2.text-2.text-gray"


def extract_weekdays(text: str) -> List[str]:
    text_l = (text or "").lower()
    # normalizar acentos para facilitar matching
    norm = text_l.replace("á", "a").replace("é", "e").replace(
        "í", "i").replace("ó", "o").replace("ú", "u")

    # orden fijo de días para poder expandir rangos
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
        # incluir hasta que lleguemos a j (soporta wrap-around)
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

    # devolver con primera letra mayúscula y sin acentos (consistente con el resto)
    return [d.capitalize() for d in added]


def scrape_with_parser(parser: BankParser, headless: bool = False) -> Dict:
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")

    driver = Chrome(service=service, options=options)

    # Si el parser es Banco de Chile abrimos la url conocida, otras clases pueden definir otra url
    if isinstance(parser, BankChileParser):
        url = "https://sitiospublicos.bancochile.cl/personas/beneficios/beneficios-del-dia"
    else:
        url = "about:blank"

    driver.get(url)
    time.sleep(4)

    # recolectar textos usando los selectores del parser (si existen)
    def _get_texts(selector: Optional[str]):
        if not selector:
            return []
        els = driver.find_elements(by=By.CSS_SELECTOR, value=selector)
        return [e.text.strip() for e in els]

    titles = _get_texts(parser.selector_title)
    discounts = _get_texts(parser.selector_discount)
    extras = _get_texts(parser.selector_extra)

    # zip_longest para emparejar
    items = []
    for t, d, e in zip_longest(titles, discounts, extras, fillvalue=None):
        items.append({
            "title": t or "",
            "discount": d or "",
            "extra": e or "",
        })

    driver.quit()

    return parser.parse_items(items)


def main():
    parser_map = {
        "banco_de_chile": BankChileParser,
        # aquí puede agregarse más bancos, por ejemplo: 'banco_x': BancoXParser
    }

    ap = argparse.ArgumentParser(
        description="Scrapper de beneficios con parsers por banco")
    ap.add_argument("--bank", default="banco_de_chile",
                    help="Identificador del banco (parser)")
    ap.add_argument("--headless", action="store_true",
                    help="Ejecutar Chrome en headless")
    ap.add_argument("--out", default="output.json",
                    help="Archivo de salida JSON")
    args = ap.parse_args()

    bank_key = args.bank
    if bank_key not in parser_map:
        print(
            f"Banco '{bank_key}' no soportado. Bancos disponibles: {', '.join(parser_map.keys())}")
        return

    parser_cls = parser_map[bank_key]
    parser = parser_cls()

    result = scrape_with_parser(parser, headless=args.headless)

    # Guardar como lista de bancos para mantener compatibilidad con formato.txt
    output = [result]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Salida guardada en {args.out}")


if __name__ == "__main__":
    main()
