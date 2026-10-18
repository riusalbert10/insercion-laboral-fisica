"""
Contratos registrados a físicos por actividad económica (SEPE, Observatorio de las Ocupaciones).

Fuente: "Información anual de mercado de trabajo de titulados universitarios", un PDF por año
con una ficha por titulación (área Ciencias experimentales). De cada ficha de Física se extraen:
  - total de contratos del año
  - las actividades económicas (CNAE a 2 dígitos) más contratadas, con su nº de contratos
  - demandantes de empleo y parados inscritos a 31 de diciembre
  - contratos indefinidos y temporales
Titulaciones sumadas: Licenciatura en Física, Grado en Física y Grado en Física Aplicada.

OJO: solo cuenta contratos firmados por físicos inscritos como demandantes de empleo en los
servicios públicos de empleo (no todos los físicos), y cada ficha lista solo las actividades
más contratadas; el resto queda en "Otras actividades".

Uso:  python sepe_contratos.py   -> sepe_contratos.sql (tabla eilu.sepe_contratos_sector)
"""
import html
import os
import re
import urllib.request
from http.cookiejar import CookieJar
from urllib.parse import urlencode

import fitz  # PyMuPDF

BASE = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE, "data", "sepe")
OUT_SQL = os.path.join(BASE, "sepe_contratos.sql")
FORM = ("https://www.sepe.es/HomeSepe/que-es-observatorio/informacion-titulaciones/"
        "informacion-titulaciones-universitarias.html")
TITULACIONES = {"LICENCIATURA EN FÍSICA", "GRADO EN FÍSICA", "GRADO EN FÍSICA APLICADA"}
YEARS_PDF = range(2015, 2025)

# 2016: el PDF es un escaneo sin texto; valores transcritos de las págs. 47-48 y 95-96.
# {año: {titulación: ficha}}; ficha = dict(contratos, demandantes, parados, indefinidos,
# temporales, sectores={actividad: contratos})
MANUAL = {2016: {
    "GRADO EN FÍSICA": dict(contratos=161, personas=111, demandantes=118, parados=90, indefinidos=15, temporales=146, sectores={
        "Educación": 48,
        "Programación, consultoría y otras actividades relacionadas con la informática": 18,
        "Investigación y desarrollo": 17,
        "Servicios de comidas y bebidas": 16,
        "Actividades de creación, artísticas y espectáculos": 12,
        "Actividades administrativas de oficina y otras actividades auxiliares a las empresas": 5,
        "Fabricación de productos informáticos, electrónicos y ópticos": 5,
        "Actividades jurídicas y de contabilidad": 4,
        "Publicidad y estudios de mercado": 4,
        "Servicios técnicos de arquitectura e ingeniería; ensayos y análisis técnicos": 4,
    }),
    "LICENCIATURA EN FÍSICA": dict(contratos=1268, personas=921, demandantes=1641, parados=1062, indefinidos=248, temporales=1020,
                                   sectores={
        "Educación": 412,
        "Programación, consultoría y otras actividades relacionadas con la informática": 145,
        "Investigación y desarrollo": 97,
        "Servicios técnicos de arquitectura e ingeniería; ensayos y análisis técnicos": 55,
        "Servicios de comidas y bebidas": 47,
        "Comercio al por menor, excepto de vehículos de motor y motocicletas": 41,
        "Comercio al por mayor e intermediarios del comercio, excepto de vehículos de motor y motocicletas": 35,
        "Actividades administrativas de oficina y otras actividades auxiliares a las empresas": 33,
        "Otras actividades profesionales, científicas y técnicas": 33,
        "Actividades sanitarias": 29,
    }),
}}

# Desde 2025 las fichas están en la web nueva del SEPE (HTML), no en PDF.
HTML_URL = ("https://www.sepe.es/HomeSepe/que-es-observatorio/informacion-titulaciones/buscador-titulaciones/"
            "titulacion-detalle-anual~__titulaciones-uni__{year}_{slug}~.html")
HTML_SLUGS = {"GRADO EN FÍSICA": "594410053301-Grado-en-f-sica",
              "LICENCIATURA EN FÍSICA": "554410053301-Licenciatura-en-f-sica"}
YEARS_HTML = [2025]


# Agrupa las actividades (CNAE a 2 dígitos) en sectores; lo que no entra en el top 10 de la
# ficha queda en 'Otras actividades' (total del año - suma de las actividades listadas).
VIEW = """
CREATE OR REPLACE VIEW v_sepe_fisica_sector_anual AS
WITH agrupado AS (
  SELECT anio,
         CASE
           WHEN actividad = 'Investigación y desarrollo' THEN 'I+D (investigación)'
           WHEN actividad LIKE 'Programación, consultoría%' OR actividad LIKE 'Servicios de información%'
                OR actividad = 'Telecomunicaciones' THEN 'Informática y datos'
           WHEN actividad LIKE 'Servicios técnicos de arquitectura e ingeniería%'
                OR actividad = 'Otras actividades profesionales, científicas y técnicas'
                THEN 'Ingeniería y servicios técnicos'
           WHEN actividad LIKE 'Fabricación%' OR actividad LIKE 'Industria%'
                OR actividad LIKE 'Suministro de energía%' THEN 'Industria y energía'
           WHEN actividad = 'Educación' THEN 'Educación'
           ELSE 'Otras actividades'
         END COLLATE utf8mb4_0900_ai_ci AS sector,  -- explícita: Grafana conecta con otra collation
         contratos
  FROM sepe_contratos_sector
),
totales AS (SELECT anio, SUM(contratos) AS total FROM sepe_contratos_total GROUP BY anio),
listados AS (SELECT anio, SUM(contratos) AS listados FROM sepe_contratos_sector GROUP BY anio)
SELECT a.anio, a.sector, SUM(a.contratos) + IF(a.sector = 'Otras actividades', t.total - l.listados, 0) AS contratos,
       t.total
FROM agrupado a JOIN totales t USING (anio) JOIN listados l USING (anio)
GROUP BY a.anio, a.sector, t.total, l.listados;
"""


def download_pdfs():
    os.makedirs(PDF_DIR, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", "Mozilla/5.0"), ("Referer", FORM)]
    opener.open(FORM).read()
    for year in YEARS_PDF:
        path = os.path.join(PDF_DIR, f"titulados_ciencias_exp_{year}.pdf")
        if os.path.exists(path):
            continue
        data = urlencode({"category": "ciencias_experimentales", "month": 13, "year": year}).encode()
        html = opener.open(FORM, data).read().decode("utf-8", "replace")
        link = re.search(r'href="(/dctm/[^"]*ESTUDIO_TITULADOS_FI_5\.pdf)"', html).group(1)
        with open(path, "wb") as f:
            f.write(opener.open("https://www.sepe.es" + link).read())


def to_int(s):
    return int(s.replace(".", ""))


def parse_sectors(lines):
    """Bloque 'ACTIVIDADES ECONÓMICAS MÁS CONTRATADAS': nombre (1-3 líneas), contratos, %, variación."""
    start = next(i for i, l in enumerate(lines) if l.upper().startswith("ACTIVIDADES ECON"))
    body = lines[start + 1:]
    # salta la cabecera "Total / Contratos / % / s/t / % variación / anual(*)"
    while body and not body[0].lower().startswith("anual"):
        body = body[1:]
    body = body[1:]
    out, name = {}, []
    i = 0
    while i < len(body):
        l = body[i]
        if re.fullmatch(r"\d[\d.]*", l) and i + 1 < len(body) and "%" in body[i + 1]:
            out[" ".join(name).strip()] = to_int(l)
            name = []
            i += 3  # contratos, % s/t, % variación
            continue
        if l.isupper() or l.startswith(("OCUPACIONES", "PROVINCIAS", "DISTRIBUCI", "TITULADOS")):
            break
        name.append(l)
        i += 1
    return out


SUMMARY = {
    "contratos": r"se comunicaron un total de ([\d.]+) contratos",
    "personas": r"contratos para un total de ([\d.]+) personas",
    "demandantes": r"registrados ([\d.]+)\s+demandantes de empleo",
    "parados": r"de los cuales ([\d.]+) son\s+parados",
    "indefinidos": r"([\d.]+) contratos han sido de duración indefinida",
    "temporales": r"indefinida\s+y ([\d.]+) de duración temporal",
}


def parse_summary(text, ficha):
    """Cifras de los recuadros DEMANDANTES y CONTRATOS de la ficha."""
    for key, pat in SUMMARY.items():
        m = re.search(pat, text)
        if m:
            ficha[key] = to_int(m.group(1))


def parse_pdf(path):
    doc = fitz.open(path)
    fichas = {}
    for page in doc:
        lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
        for j, l in enumerate(lines):
            if re.fullmatch(r"AÑO \d{4}", l) and j + 1 < len(lines) and lines[j + 1] in TITULACIONES:
                ficha = fichas.setdefault(lines[j + 1], {"sectores": {}})
                parse_summary(" ".join(lines), ficha)
                if any(x.upper().startswith("ACTIVIDADES ECON") for x in lines):
                    ficha["sectores"] = parse_sectors(lines)
    return fichas


def parse_html(year):
    fichas = {}
    for tit, slug in HTML_SLUGS.items():
        req = urllib.request.Request(HTML_URL.format(year=year, slug=slug), headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req).read().decode("utf-8")
        page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
        lines = [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", page)).splitlines() if l.strip()]
        ficha = {}
        parse_summary(" ".join(lines), ficha)
        start = next(i for i, l in enumerate(lines) if l.lower().startswith("actividades econ"))
        sectors, i = {}, start + 4  # salta cabecera (Total Contratos / % / % variación)
        while i + 1 < len(lines) and re.fullmatch(r"\d[\d.]*", lines[i + 1]):
            sectors[lines[i]] = to_int(lines[i + 1])
            i += 4  # nombre, contratos, %, variación
        ficha["sectores"] = sectors
        fichas[tit] = ficha
    return fichas


def main():
    download_pdfs()
    for year in YEARS_HTML:
        MANUAL[year] = parse_html(year)
    por_anio = {y: parse_pdf(os.path.join(PDF_DIR, f"titulados_ciencias_exp_{y}.pdf"))
                for y in YEARS_PDF if y not in MANUAL}
    por_anio.update(MANUAL)
    rows = []  # (año, titulación, actividad, contratos)
    totals = []  # (año, titulación, ficha)
    for year, fichas in sorted(por_anio.items()):
        for tit, ficha in fichas.items():
            totals.append((year, tit, ficha))
            rows += [(year, tit, act, n) for act, n in ficha["sectores"].items()]

    q = lambda s: "'" + s.replace("'", "''") + "'"
    with open(OUT_SQL, "w", encoding="utf-8") as f:
        f.write("USE eilu;\nDROP TABLE IF EXISTS sepe_contratos_sector;\nDROP TABLE IF EXISTS sepe_contratos_total;\n")
        f.write("CREATE TABLE sepe_contratos_total (anio SMALLINT, titulacion VARCHAR(60), contratos INT,"
                " personas INT COMMENT 'personas distintas que firmaron esos contratos', demandantes INT COMMENT 'inscritos a 31-dic', parados INT COMMENT 'parados a 31-dic',"
                " indefinidos INT, temporales INT,"
                " PRIMARY KEY (anio, titulacion)) COMMENT='SEPE: contratos a demandantes con titulación de Física';\n")
        f.write("CREATE TABLE sepe_contratos_sector (anio SMALLINT, titulacion VARCHAR(60), actividad VARCHAR(200),"
                " contratos INT) COMMENT='SEPE: actividades económicas más contratadas (top N por ficha)';\n")
        f.write("INSERT INTO sepe_contratos_total VALUES\n" +
                ",\n".join(f"({y}, {q(t)}, " + ", ".join(str(fi.get(k, "NULL")) for k in SUMMARY) + ")"
                           for y, t, fi in totals) + ";\n")
        f.write("INSERT INTO sepe_contratos_sector VALUES\n" +
                ",\n".join(f"({y}, {q(t)}, {q(a)}, {n})" for y, t, a, n in rows) + ";\n")
        f.write(VIEW)
    for y, t, fi in totals:
        print(y, t, {k: fi.get(k) for k in SUMMARY},
              "| en top actividades", sum(r[3] for r in rows if r[0] == y and r[1] == t))


if __name__ == "__main__":
    main()
