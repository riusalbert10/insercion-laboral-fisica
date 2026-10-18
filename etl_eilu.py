"""
ETL: microdatos EILU 2019 (INE) -> MySQL (base de datos `eilu`) para Grafana.

Fuente: Encuesta de Inserción Laboral de Titulados Universitarios 2019, INE.
  Cohorte: titulados del curso 2013-2014, entrevistados en 2019 (~5 años después).
  https://www.ine.es/ftp/microdatos/eilu/datos_2019.zip

Genera `eilu.sql` (esquema + datos) que se carga con el cliente mysql.
Uso:  python etl_eilu.py   (descarga el zip si no está en data/)
"""
import io
import os
import urllib.request
import zipfile

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
ZIP_URL = "https://www.ine.es/ftp/microdatos/eilu/datos_2019.zip"
ZIP_PATH = os.path.join(DATA, "datos_2019.zip")
OUT_SQL = os.path.join(BASE, "eilu.sql")


def load_microdata():
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(ZIP_PATH):
        urllib.request.urlretrieve(ZIP_URL, ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read("EILU_GRADUADOS.zip")))
    csv = inner.read("CSV/EILU_GRAD_2019.csv")
    dr = inner.read("dr_EILU_GRAD_2019.xlsx")
    df = pd.read_csv(io.BytesIO(csv), sep="\t", dtype=str, encoding="latin-1")
    df = df.apply(lambda s: s.str.strip()).replace("", None)
    return df, io.BytesIO(dr)


def load_dictionaries(dr_bytes):
    """Lee las hojas Tablas1-3 del diseño de registro -> {nombre_tabla: {codigo: descripcion}}."""
    dicts, current = {}, None
    xl = pd.read_excel(dr_bytes, sheet_name=None, header=None, dtype=str)
    for name, sheet in xl.items():
        if not name.startswith("Tablas"):
            continue
        rows = [(str(r.iloc[0]).strip() if pd.notna(r.iloc[0]) else None,
                 str(r.iloc[1]).strip() if len(r) > 1 and pd.notna(r.iloc[1]) else None)
                for _, r in sheet.iterrows()]
        for i, (a, b) in enumerate(rows):
            # La cabecera de cada diccionario va seguida de la fila "Código | Descripción"
            if i + 1 < len(rows) and rows[i + 1][0] == "Código":
                current = a
                dicts[current] = {}
            elif a and a != "Código" and current and b:
                dicts[current][a] = b
    return dicts


# Etiquetas cortas (legibles en un gráfico) para ocupación CNO-11 a 2 dígitos
OCUPACION_CORTA = {
    "11": "Directivos Adm. Pública", "12": "Directores administrativos y comerciales",
    "13": "Directores de producción", "14": "Gerentes hostelería y comercio",
    "15": "Gerentes otras empresas", "21": "Profesionales de la salud",
    "22": "Profesores (secundaria, universidad...)", "23": "Otros profesionales de la enseñanza",
    "24": "Físicos, químicos, matemáticos e ingenieros", "25": "Profesionales del derecho",
    "26": "Especialistas en finanzas y gestión", "27": "Profesionales TIC (software, datos)",
    "28": "Profesionales ciencias sociales", "29": "Profesionales cultura y espectáculo",
    "31": "Técnicos de ciencias e ingenierías", "32": "Supervisores industria y construcción",
    "33": "Técnicos sanitarios", "34": "Apoyo en finanzas y matemáticas",
    "35": "Agentes comerciales", "36": "Apoyo a la gestión administrativa",
    "37": "Apoyo servicios jurídicos/sociales/culturales", "38": "Técnicos TIC",
    "41": "Empleados contables y financieros", "42": "Empleados bibliotecas y correos",
    "43": "Otros administrativos", "44": "Recepcionistas y atención al cliente",
    "45": "Administrativos con atención al público", "50": "Hostelería (propietarios)",
    "51": "Camareros y cocineros", "52": "Dependientes", "53": "Comerciantes propietarios",
    "54": "Vendedores (no tienda)", "55": "Cajeros", "56": "Auxiliares sanitarios",
    "57": "Cuidadores", "58": "Servicios personales", "59": "Seguridad y protección",
    "61": "Agricultura", "62": "Ganadería", "63": "Agropecuario", "64": "Forestal y pesca",
    "71": "Construcción", "72": "Acabados de construcción", "73": "Soldadores y montadores",
    "74": "Mecánicos", "75": "Electricistas", "76": "Mecánicos de precisión y artesanos",
    "77": "Industria alimentaria", "78": "Madera, textil y otros oficios",
    "81": "Operadores de maquinaria", "82": "Montadores en fábricas", "83": "Maquinistas",
    "84": "Conductores", "91": "Empleados domésticos", "92": "Limpieza",
    "93": "Ayudantes de cocina", "94": "Repartidores y otras elementales",
    "95": "Peones agrarios", "96": "Peones construcción", "97": "Peones industria",
    "98": "Peones transporte", "00": "Militares", "99": "NS/NC",
}

SECTOR_CORTO = {
    "AA": "Agricultura y pesca", "BB": "Industrias extractivas", "CC": "Industria manufacturera",
    "DD": "Energía (electricidad, gas)", "EE": "Agua y residuos", "FF": "Construcción e ingeniería civil",
    "GG": "Comercio", "HH": "Transporte y logística", "II": "Hostelería",
    "JJ": "Información y comunicaciones (TIC)", "KK": "Finanzas y seguros", "LL": "Inmobiliarias",
    "M1": "Act. profesionales, científicas y técnicas (I+D, consultoría)", "M2": "Fotografía",
    "M3": "Veterinaria", "N1": "Alquiler", "N2": "Empleo (ETT, selección)", "N3": "Agencias de viajes",
    "N4": "Seguridad e investigación", "N5": "Servicios a edificios", "N6": "Servicios administrativos",
    "OO": "Administración Pública y defensa", "PP": "Educación", "QQ": "Sanidad y servicios sociales",
    "RR": "Cultura, ocio y deporte", "S1": "Asociaciones y sindicatos", "S2": "Reparación de ordenadores",
    "S3": "Servicios personales", "S4": "Mantenimiento físico", "TT": "Hogares como empleadores",
    "UU": "Organismos extraterritoriales", "99": "NS/NC",
}

SIT_PROF_CORTA = {
    "1": "Becario / predoctoral", "2": "Contrato indefinido", "3": "Contrato temporal",
    "4": "Empresario con asalariados", "5": "Autónomo sin asalariados", "6": "Ayuda en negocio familiar",
}

SUELDO_CORTO = {
    "1": "< 700 €", "2": "700-999 €", "3": "1.000-1.499 €", "4": "1.500-1.999 €",
    "5": "2.000-2.499 €", "6": "2.500-2.999 €", "7": "3.000 € o más", "9": "NS/NC",
}

RAMA_CORTA = {
    "1": "Artes y humanidades", "2": "Ciencias", "3": "CC. sociales y jurídicas",
    "4": "Ingeniería y arquitectura", "5": "Ciencias de la salud", "9": "NS/NC",
}

NIVEL_CORTO = {
    "1": "Doctorado", "2": "Máster", "3": "Grado/licenciatura", "4": "FP superior",
    "5": "FP medio / bachiller", "6": "FP básica", "7": "ESO, EGB o inferior", "9": "NS/NC",
}

TIEMPO_CORTO = {
    "0": "Ya trabajaba y siguió", "1": "Menos de 3 meses", "2": "De 3 a 6 meses",
    "3": "De 6 meses a 1 año", "4": "De 1 año a 1,5 años", "5": "De 1,5 a 2 años",
    "6": "2 años o más", "9": "NS/NC",
}

# Agrupación CNO 1 dígito (gran grupo)
GRAN_GRUPO = {
    "0": "Militares", "1": "Directores y gerentes", "2": "Técnicos y profesionales científicos",
    "3": "Técnicos y profesionales de apoyo", "4": "Empleados administrativos",
    "5": "Servicios y comercio", "6": "Agricultura", "7": "Artesanos e industria cualificada",
    "8": "Operadores de maquinaria", "9": "Ocupaciones elementales",
}


def build(df, dicts):
    lab = lambda col, dic: df[col].map(dicts[dic]) if dic in dicts else None
    out = pd.DataFrame({
        "ident": df.IDENT.astype(int),
        "factor": df.FACTOR.astype(float),
        "titulacion_cod": df.TITU,
        "titulacion": lab("TITU", "TTITULA"),
        "rama": lab("RAMA", "TRAMA"),
        "ambito": lab("AMBITO", "TAMBITO"),
        "sexo": lab("SEXO", "TSEXO"),
        "edad": lab("EDAD", "TEDAD"),
        "tiene_master": df.EST_B11_2.eq("1").astype(int),
        "tiene_doctorado": df.EST_B11_3.eq("1").astype(int),
        "rama_master": df.EST_B17_M1.map(RAMA_CORTA),
        "estudios_en_curso": lab("EST2_NC", "TESTCRS"),
        "situacion": lab("TRBPRN1", "T1TRBPN"),
        "situacion_inactividad": lab("TRBPRN2", "T2TRBPN"),
        "ocupacion_cod": df.TRABOC,
        "ocupacion": df.TRABOC.map(OCUPACION_CORTA),
        "ocupacion_gran_grupo": df.TRABOC.str[0].map(GRAN_GRUPO).where(df.TRABOC.ne("99")),
        "sector_cod": df.TR_CNAE,
        "sector": df.TR_CNAE.map(SECTOR_CORTO),
        "situacion_profesional": df.SIT_PRO.map(SIT_PROF_CORTA),
        "jornada": lab("JORNADA", "TJornad"),
        "sueldo": df.TR_SUELDO.map(SUELDO_CORTO),
        "sueldo_cod": pd.to_numeric(df.TR_SUELDO, errors="coerce"),
        "nivel_apropiado": df.TR_D19.map(NIVEL_CORTO),
        "area_apropiada": lab("TR_D20", "TAreEst"),
        "usa_conocimientos": lab("TR_D21", "T2SINO"),
        "pais_trabajo": lab("LUG_TRAB_PAIS", "T1PAIS"),
        "ha_trabajado": df.HA_TRAB.eq("1").astype(int),
        "tiempo_primer_empleo": df.HATR_E11.map(TIEMPO_CORTO),
        "tiempo_primer_empleo_cod": pd.to_numeric(df.HATR_E11, errors="coerce"),
        "primera_ocupacion_cod": df.PR_OCU,
        "primera_ocupacion": df.PR_OCU.map(OCUPACION_CORTA),
        "primera_situacion_profesional": df.PR_SIT_PR.map(SIT_PROF_CORTA),
        "primer_nivel_apropiado": df.PR_NIVEL.map(NIVEL_CORTO),
        "primer_sueldo": df.PR_SUELDO.map(SUELDO_CORTO),
        "primer_sueldo_cod": pd.to_numeric(df.PR_SUELDO, errors="coerce"),
        "titulo_sirvio": lab("HATR_E27", "T2SINO"),
        "practicas": lab("HL_E1", "TPRAC"),
    })
    out.insert(10, "formacion", out.tiene_doctorado.map({1: "Doctorado"}).fillna(
        out.tiene_master.map({1: "Máster", 0: "Solo grado/licenciatura"})))
    return out


SCHEMA = """
DROP DATABASE IF EXISTS eilu;
CREATE DATABASE eilu CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE eilu;

CREATE TABLE graduados (
  ident INT PRIMARY KEY,
  factor DOUBLE NOT NULL COMMENT 'Factor de elevación: nº de titulados que representa la persona',
  titulacion_cod CHAR(6), titulacion VARCHAR(120), rama VARCHAR(80), ambito VARCHAR(120),
  sexo VARCHAR(10), edad VARCHAR(40),
  tiene_master TINYINT, tiene_doctorado TINYINT, formacion VARCHAR(30),
  rama_master VARCHAR(80), estudios_en_curso VARCHAR(160),
  situacion VARCHAR(20), situacion_inactividad VARCHAR(80),
  ocupacion_cod CHAR(2), ocupacion VARCHAR(80), ocupacion_gran_grupo VARCHAR(60),
  sector_cod CHAR(2), sector VARCHAR(80),
  situacion_profesional VARCHAR(120), jornada VARCHAR(30),
  sueldo VARCHAR(40), sueldo_cod TINYINT,
  nivel_apropiado VARCHAR(80), area_apropiada VARCHAR(60), usa_conocimientos VARCHAR(10),
  pais_trabajo VARCHAR(80),
  ha_trabajado TINYINT, tiempo_primer_empleo VARCHAR(90), tiempo_primer_empleo_cod TINYINT,
  primera_ocupacion_cod CHAR(2), primera_ocupacion VARCHAR(80),
  primera_situacion_profesional VARCHAR(120), primer_nivel_apropiado VARCHAR(80),
  primer_sueldo VARCHAR(40), primer_sueldo_cod TINYINT,
  titulo_sirvio VARCHAR(10), practicas VARCHAR(120),
  KEY (titulacion_cod), KEY (rama)
) COMMENT='EILU 2019 (INE). Graduados universitarios curso 2013-14, situación en 2019';
"""

VIEWS = """
-- Físicos: KPIs principales (todas las cifras ponderadas con el factor de elevación)
CREATE VIEW v_fisica_kpi AS
SELECT COUNT(*) AS muestra,
       ROUND(SUM(factor)) AS titulados,
       SUM(factor*(situacion='Trabajando'))/SUM(factor) AS tasa_empleo,
       SUM(factor*(situacion='En desempleo'))/SUM(factor*(situacion<>'Inactivo')) AS tasa_paro,
       SUM(factor*(formacion='Solo grado/licenciatura'))/SUM(factor) AS pct_solo_grado,
       SUM(factor*(formacion='Máster'))/SUM(factor) AS pct_master,
       SUM(factor*(formacion='Doctorado'))/SUM(factor) AS pct_doctorado,
       SUM(factor*(situacion='Trabajando' AND formacion='Solo grado/licenciatura'))
         / SUM(factor*(formacion='Solo grado/licenciatura')) AS tasa_empleo_solo_grado,
       SUM(factor*(situacion='Trabajando' AND pais_trabajo<>'España'))
         / SUM(factor*(situacion='Trabajando')) AS pct_trabaja_extranjero
FROM graduados WHERE titulacion_cod='053301';

CREATE VIEW v_fisica_situacion_formacion AS
SELECT formacion, situacion, COUNT(*) AS muestra, SUM(factor) AS titulados,
       SUM(factor)/SUM(SUM(factor)) OVER (PARTITION BY formacion) AS pct
FROM graduados WHERE titulacion_cod='053301'
GROUP BY formacion, situacion;

CREATE VIEW v_fisica_ocupacion AS
SELECT ocupacion, formacion, COUNT(*) AS muestra, SUM(factor) AS titulados
FROM graduados WHERE titulacion_cod='053301' AND situacion='Trabajando' AND ocupacion_cod<>'99'
GROUP BY ocupacion, formacion;

CREATE VIEW v_fisica_sector AS
SELECT sector, formacion, COUNT(*) AS muestra, SUM(factor) AS titulados
FROM graduados WHERE titulacion_cod='053301' AND situacion='Trabajando' AND sector_cod<>'99'
GROUP BY sector, formacion;

CREATE VIEW v_comparativa_titulaciones AS
SELECT titulacion AS grupo,
       COUNT(*) AS muestra,
       SUM(factor*(situacion='Trabajando'))/SUM(factor) AS tasa_empleo,
       SUM(factor*(formacion<>'Solo grado/licenciatura'))/SUM(factor) AS pct_con_posgrado,
       SUM(factor*(situacion='Trabajando' AND formacion='Solo grado/licenciatura'))
         / SUM(factor*(formacion='Solo grado/licenciatura')) AS tasa_empleo_solo_grado,
       SUM(factor*(situacion='Trabajando' AND sueldo_cod BETWEEN 5 AND 7))
         / SUM(factor*(situacion='Trabajando' AND sueldo_cod<>9)) AS pct_mas_2000_eur
FROM graduados
WHERE titulacion_cod IN ('053301','054101','053101','054201')
GROUP BY titulacion
UNION ALL
SELECT 'Todos los graduados', COUNT(*),
       SUM(factor*(situacion='Trabajando'))/SUM(factor),
       SUM(factor*(formacion<>'Solo grado/licenciatura'))/SUM(factor),
       SUM(factor*(situacion='Trabajando' AND formacion='Solo grado/licenciatura'))
         / SUM(factor*(formacion='Solo grado/licenciatura')),
       SUM(factor*(situacion='Trabajando' AND sueldo_cod BETWEEN 5 AND 7))
         / SUM(factor*(situacion='Trabajando' AND sueldo_cod<>9))
FROM graduados;
"""


def sql_value(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def main():
    df, dr = load_microdata()
    dicts = load_dictionaries(dr)
    out = build(df, dicts)
    cols = ", ".join(out.columns)
    rows = out.astype(object).where(out.notna(), None).itertuples(index=False)
    with open(OUT_SQL, "w", encoding="utf-8") as f:
        f.write(SCHEMA)
        batch = []
        for r in rows:
            batch.append("(" + ", ".join(sql_value(v) for v in r) + ")")
            if len(batch) == 1000:
                f.write(f"INSERT INTO graduados ({cols}) VALUES\n" + ",\n".join(batch) + ";\n")
                batch = []
        if batch:
            f.write(f"INSERT INTO graduados ({cols}) VALUES\n" + ",\n".join(batch) + ";\n")
        f.write(VIEWS)
    fis = out[out.titulacion_cod == "053301"]
    print(f"{len(out)} graduados, {len(fis)} físicos en la muestra -> {OUT_SQL}")
    missing = {c: out[c].isna().sum() for c in ("titulacion", "situacion", "formacion")}
    print("nulos en columnas clave:", missing)


if __name__ == "__main__":
    main()
