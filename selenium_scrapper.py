"""
Scrapper central: itera por los parsers registrados y guarda un JSON
por banco en el directorio de salida.
"""

from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
from itertools import zip_longest
import argparse
import json
import os
from typing import List, Dict, Optional, Tuple


class BankParser:
    """Base parser class. Subclases deben definir selectores y parsear textos.

    Nota: la extracción fina (regex, días válidos, normalización) se delega
    a `extractor.py`.
    """

    bank_id = "banco_000"
    bank_name = "Generic Bank"
    selector_title: Optional[str] = None
    selector_discount: Optional[str] = None
    selector_extra: Optional[str] = None
    bank_url: Optional[str] = None
    scroller: bool = False

    def __init__(self):
        pass
    # Nota: se ha eliminado el parseo específico por beneficio.
    # Ahora el scrapper devuelve el `bank_id` y la lista de atributos
    # recogidos por cada beneficio (crudos). El procesamiento y normalización
    # se delega a `extractor.py`.


class BankChileParser(BankParser):
    bank_id = "banco_001"
    bank_name = "Banco de Chile"
    selector_title = ".font-700.text-3.text-gray-dark.mb-2.overflow-ellipsis"
    selector_discount = ".font-700.text-3.text-primary.mb-2.overflow-ellipsis"
    selector_extra = ".overflow-ellipsis.mb-2.text-2.text-gray"
    bank_url = "https://sitiospublicos.bancochile.cl/personas/beneficios/beneficios-del-dia"


class BankFalabellaParser(BankParser):
    bank_id = "banco_002"
    bank_name = "Banco Falabella"
    selector_title = ".NewCardBenefits_title__fpDao"
    selector_discount = ".NewCardBenefits_text-uppercase__DRpVQ"
    selector_extra = ".NewCardBenefits_days__XZpWE"
    bank_url = "https://www.bancofalabella.cl/descuentos/todos"
    scroller = True


class BankSantanderParser(BankParser):
    bank_id = "banco_003"
    bank_name = "Banco Santander"
    selector_title = ".fw-bold f-large"
    selector_discount = ".text-primary-mediumgrey f-small fw-normal mb-12"
    bank_url = "https://www.santander.cl/personas/beneficios"
    scroller = False
    nextpage = ".text-primary-santander str-chevron-right f-20"


def scrape_with_parser(parser: BankParser, headless: bool = False) -> Tuple[str, List[Dict[str, str]]]:
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    scroller = parser.scroller
    if headless:
        options.add_argument("--headless=new")

    driver = Chrome(service=service, options=options)

    url = parser.bank_url or "about:blank"
    driver.get(url)
    time.sleep(2)

    def scroll_to_bottom(drv, pause: float = 1.0, max_scrolls: int = 30):
        try:
            last_height = drv.execute_script(
                "return document.body.scrollHeight")
        except Exception:
            return
        for _ in range(max_scrolls):
            drv.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            try:
                new_height = drv.execute_script(
                    "return document.body.scrollHeight")
            except Exception:
                break
            if new_height == last_height:
                break
            last_height = new_height

    if scroller:
        scroll_to_bottom(driver)
        time.sleep(1)

    def _get_texts(selector: Optional[str]):
        if not selector:
            return []
        els = driver.find_elements(by=By.CSS_SELECTOR, value=selector)
        return [e.text.strip() for e in els]

    titles = _get_texts(parser.selector_title)
    discounts = _get_texts(parser.selector_discount)
    extras = _get_texts(parser.selector_extra)

    items = []
    for t, d, e in zip_longest(titles, discounts, extras, fillvalue=None):
        items.append({
            "title": t or "",
            "discount": d or "",
            "extra": e or "",
        })

    driver.quit()

    # Devolver el id del banco y la lista cruda de items recogidos.
    return parser.bank_id, items


def main():
    parser_map = {
        "banco_de_chile": BankChileParser,
        "banco_falabella": BankFalabellaParser,
    }

    ap = argparse.ArgumentParser(
        description="Scrapper: itera parsers y guarda JSON por banco")
    ap.add_argument("--banks", default="all",
                    help="Comma-separated bank keys to scrape or 'all' (default: all)")
    ap.add_argument("--headless", action="store_true",
                    help="Ejecutar Chrome en headless")
    ap.add_argument("--out-dir", default=".",
                    help="Directorio de salida para JSON por banco")
    args = ap.parse_args()

    requested = [b.strip() for b in args.banks.split(
        ",")] if args.banks != "all" else list(parser_map.keys())

    os.makedirs(args.out_dir, exist_ok=True)

    for bank_key in requested:
        if bank_key not in parser_map:
            print(f"Aviso: '{bank_key}' no soportado. Omitiendo.")
            continue
        parser_cls = parser_map[bank_key]
        parser = parser_cls()
        print(f"Scrappeando {bank_key} ({parser.bank_name})...")
        bank_id, items = scrape_with_parser(parser, headless=args.headless)

        out_path = os.path.join(args.out_dir, f"{bank_key}.json")
        # Guardar una lista con un solo banco: id y lista cruda de items
        out_obj = {"id": bank_id, "items": items}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([out_obj], f, ensure_ascii=False, indent=2)

        print(f"Guardado: {out_path}")


if __name__ == "__main__":
    main()
