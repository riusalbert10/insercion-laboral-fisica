"""
Egresados en Física por curso (Ministerio de Ciencia, Innovación y Universidades, SIIU).

Fuente: Estadística de Estudiantes Universitarios, "Serie de estudiantes egresados por rama de
enseñanza, comunidad autónoma, universidad y titulación" (Egresados.xlsx, hoja Egresados_Grado).
Cursos 2015-2016 a 2024-2025. El curso 2024-2025 se asigna al año 2025 (año en que se titulan).

Uso:  python egresados_fisica.py   -> egresados_fisica.sql (tabla eilu.egresados_fisica)
"""
import os
import re
import urllib.request

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(BASE, "data", "universidades", "Egresados.xlsx")
URL = "https://www.ciencia.gob.es/dam/jcr:decc2024-82d0-4063-9202-9be6885bd34a/Egresados.xlsx"
OUT_SQL = os.path.join(BASE, "egresados_fisica.sql")


def tipo(titulacion):
    """Clasifica una titulación como de Física (o None si no lo es)."""
    t = titulacion
    if re.search(r"Ingenier[ií]a (Matem[aá]tica y )?F[ií]sica|Engineering Physics", t):
        return "Ingeniería Física"
    if t.startswith("PCEO") and re.search(r"F[ií]sica", t):
        return "Doble grado con Física"
    if re.match(r"Licenciad[oa] en F[ií]sica", t):
        return "Licenciatura en Física"
    if re.match(r"Graduado o Graduada en F[ií]sica", t):
        return "Grado en Física"
    return None


def main():
    if not os.path.exists(XLSX):
        os.makedirs(os.path.dirname(XLSX), exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        open(XLSX, "wb").write(urllib.request.urlopen(req).read())
    raw = pd.read_excel(XLSX, sheet_name="Egresados_Grado", header=None)
    cursos = [c for c in raw.iloc[2, 6:] if isinstance(c, str)]  # fila de cabecera con los cursos
    df = raw.iloc[4:, :6 + 2 * len(cursos)]
    df.columns = ["nivel", "ccaa", "univ", "cod", "titulacion", "rama"] + \
                 [f"{c}|{k}" for c in cursos for k in ("total", "pct_mujeres")]
    df = df[df.titulacion.notna()].copy()
    df["tipo"] = df.titulacion.map(tipo)
    df = df[df.tipo.notna()]

    long = df.melt(id_vars=["tipo"], value_vars=[f"{c}|total" for c in cursos],
                   var_name="curso", value_name="egresados")
    long["curso"] = long.curso.str.split("|").str[0]
    long["egresados"] = pd.to_numeric(long.egresados, errors="coerce").fillna(0)
    out = long.groupby(["curso", "tipo"], as_index=False).egresados.sum()
    out["anio"] = out.curso.str[-4:].astype(int)

    with open(OUT_SQL, "w", encoding="utf-8") as f:
        f.write("USE eilu;\nDROP TABLE IF EXISTS egresados_fisica;\n"
                "CREATE TABLE egresados_fisica (curso CHAR(9), anio SMALLINT, tipo VARCHAR(40), egresados INT,"
                " PRIMARY KEY (curso, tipo)) COMMENT='Ministerio de Universidades: egresados en titulaciones de Física';\n")
        f.write("INSERT INTO egresados_fisica VALUES\n" + ",\n".join(
            f"('{r.curso}', {r.anio}, '{r.tipo}', {int(r.egresados)})" for r in out.itertuples()) + ";\n")
    print(out.pivot(index="anio", columns="tipo", values="egresados").fillna(0).astype(int)
          .assign(Total=lambda d: d.sum(axis=1)).to_string())
    print("titulaciones incluidas:", df.titulacion.nunique())


if __name__ == "__main__":
    main()
