"""Genera dashboard_fisica.json (Grafana) a partir de la base `eilu` en MySQL."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DS = {"type": "mysql", "uid": "eilu-mysql"}

# Paleta categórica (dark steps, validada): azul, naranja, aqua
BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"
FISICA = "titulacion_cod='053301'"
# Grafana calcula el ancho de las etiquetas del eje un carácter corto y recorta la izquierda;
# unos espacios duros delante absorben ese recorte.
PAD = "'" + " " * 4 + "'"
FILTRO = f"{FISICA} AND formacion IN (${{formacion:sqlstring}})"

panels = []


def place(w, h, x, y):
    return {"w": w, "h": h, "x": x, "y": y}


def target(sql):
    return {"refId": "A", "datasource": DS, "format": "table", "rawQuery": True,
            "editorMode": "code", "rawSql": sql.strip()}


def text(title, md, pos):
    panels.append({"type": "text", "title": title, "gridPos": pos,
                   "options": {"mode": "markdown", "content": md.strip()}})


def stat(title, sql, pos, unit="percentunit", desc="", decimals=0):
    panels.append({
        "type": "stat", "title": title, "description": desc, "datasource": DS, "gridPos": pos,
        "targets": [target(sql)],
        "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals,
                                     "color": {"mode": "fixed", "fixedColor": BLUE}},
                        "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "value", "graphMode": "none", "textMode": "value",
                    "justifyMode": "center"},
    })


def hbar(title, sql, pos, desc="", unit="percentunit", color=BLUE, stacked=False, overrides=None,
         normalize=True, orientation="horizontal"):
    # Eje de valores oculto: cada barra ya lleva su % (y el tooltip lo repite).
    label_axis = {"matcher": {"id": "byName", "options": "categoria"},
                  "properties": [{"id": "custom.axisPlacement", "value": "left"}]}
    panels.append({
        "type": "barchart", "title": title, "description": desc, "datasource": DS, "gridPos": pos,
        "targets": [target(sql)],
        "fieldConfig": {
            "defaults": {"unit": unit, "decimals": 0, "min": 0, **({"max": 1} if stacked and normalize else {}),
                         "color": {"mode": "fixed", "fixedColor": color},
                         "custom": {"fillOpacity": 90, "lineWidth": 0, "gradientMode": "none",
                                    "axisGridShow": unit == "none", "axisPlacement": "auto" if unit == "none" else "hidden"}},
            "overrides": [label_axis] + (overrides or [])},
        "options": {"orientation": orientation, "xField": "categoria",
                    "showValue": "always" if not stacked else "never",
                    "stacking": "normal" if stacked else "none",
                    "groupWidth": 0.7, "barWidth": 0.85, "barRadius": 0.05,
                    "legend": {"showLegend": stacked, "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single" if not stacked else "multi", "sort": "none"},
                    "xTickLabelMaxLength": 100},
    })


def table(title, sql, pos, desc=""):
    pct_cols = ["Tasa de empleo", "Con máster o doctorado",
                "Empleo sin máster", "Gana > 2.000 €/mes"]
    panels.append({
        "type": "table", "title": title, "description": desc, "datasource": DS, "gridPos": pos,
        "targets": [target(sql)],
        "fieldConfig": {"defaults": {"custom": {"align": "auto"}},
                        "overrides": [{"matcher": {"id": "byName", "options": c},
                                       "properties": [{"id": "unit", "value": "percentunit"},
                                                      {"id": "decimals", "value": 0}]}
                                      for c in pct_cols]},
        "options": {"showHeader": True, "cellHeight": "sm"},
    })


def color_by_name(mapping):
    return [{"matcher": {"id": "byName", "options": k},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": v}}]}
            for k, v in mapping.items()]


def pct_dist(col, where, order="pct DESC", limit=10, label_n=True):
    """% ponderado de cada categoría de `col` dentro del subconjunto `where`."""
    label = f"CONCAT({PAD}, {col}, ' (', COUNT(*), ' encuestados)')" if label_n else f"CONCAT({PAD}, {col})"
    return f"""
SELECT {label} AS categoria, SUM(factor)/SUM(SUM(factor)) OVER () AS pct
FROM graduados WHERE {where} AND {col} IS NOT NULL AND {col} NOT LIKE 'NS/NC%'
GROUP BY {col} ORDER BY {order} LIMIT {limit}"""


TRABAJANDO = f"{FILTRO} AND situacion='Trabajando'"

# ---------- Cabecera ----------
text("", """
### Inserción laboral de los graduados en Física en España
Fuente: **INE, Encuesta de Inserción Laboral de Titulados Universitarios (EILU) 2019**. Los datos son microdatos de **186 físicos**
que representan a **914 titulados** del curso 2013-14, entrevistados en 2019, unos 5 años después de terminar.
**Cómo leer las barras:** el % es la estimación del INE para *todos* los físicos, no el recuento de encuestados. Cada encuestado
pesa según su factor de elevación (de media representa a ~5 titulados, pero algunos a 12 o más). Por eso 3 encuestados pueden
suponer un 22 %. El número entre paréntesis es cuántas personas respondieron: **con menos de 10 encuestados, la cifra es poco fiable**.
El filtro *Formación* de arriba se aplica a los paneles marcados con ▾.
""", place(24, 5, 0, 0))

# ---------- KPIs ----------
kpi = "SELECT {} AS v FROM v_fisica_kpi"
stat("Tasa de empleo", kpi.format("tasa_empleo"), place(4, 4, 0, 5),
     desc="% de físicos que trabajan en 2019, sobre el total de titulados")
stat("Tasa de paro", kpi.format("tasa_paro"), place(4, 4, 4, 5),
     desc="Desempleados / población activa", decimals=1)
stat("Empleo sin máster", kpi.format("tasa_empleo_solo_grado"), place(4, 4, 8, 5),
     desc="% que trabaja entre quienes no tienen ni máster ni doctorado (36 encuestados, orientativo)")
stat("Sin máster", kpi.format("pct_solo_grado"), place(4, 4, 12, 5),
     desc="% de físicos sin máster ni doctorado 5 años después de titularse")
stat("Con máster", kpi.format("pct_master"), place(4, 4, 16, 5),
     desc="% con máster pero sin doctorado")
stat("Doctores", kpi.format("pct_doctorado"), place(4, 4, 20, 5))

# ---------- Máster sí / no ----------
hbar("¿Encuentran trabajo sin máster? Situación laboral según formación", f"""
SELECT CONCAT({PAD}, formacion, ' (', SUM(muestra), ' encuestados)') AS categoria,
       SUM(titulados*(situacion='Trabajando'))/SUM(titulados)   AS Trabajando,
       SUM(titulados*(situacion='En desempleo'))/SUM(titulados) AS `En desempleo`,
       SUM(titulados*(situacion='Inactivo'))/SUM(titulados)     AS Inactivo
FROM v_fisica_situacion_formacion GROUP BY formacion
ORDER BY FIELD(formacion,'Solo grado/licenciatura','Máster','Doctorado')""",
     place(24, 7, 0, 9), stacked=True,
     desc="Barras al 100 %. 'Inactivo' incluye a quienes estudian o preparan oposiciones.",
     overrides=color_by_name({"Trabajando": BLUE, "En desempleo": ORANGE, "Inactivo": AQUA}))

hbar("Rama del máster que cursan los físicos", f"""
SELECT CONCAT({PAD}, rama_master, ' (', COUNT(*), ' encuestados)') AS categoria, SUM(factor)/SUM(SUM(factor)) OVER () AS pct
FROM graduados WHERE {FISICA} AND tiene_master=1 AND rama_master IS NOT NULL AND rama_master NOT LIKE 'NS/NC%'
GROUP BY rama_master ORDER BY pct DESC""", place(12, 8, 0, 16),
     desc="Rama del primer máster. Para un físico, un máster de Ciencias Sociales suele ser el Máster de Profesorado (MAES).")
hbar("▾ Tipo de contrato (actual)", pct_dist("situacion_profesional", TRABAJANDO, limit=6),
     place(12, 8, 12, 16), desc="'Becario / predoctoral' recoge sobre todo a los doctorandos con contrato predoctoral.")

# ---------- Tipo de trabajo y sector (ancho completo: etiquetas largas) ----------
hbar("▾ Ocupación actual (2019)", pct_dist("ocupacion", TRABAJANDO), place(24, 10, 0, 24),
     desc="Ocupación CNO-11 a 2 dígitos de quienes trabajan. Top 10.")
hbar("▾ Ocupación en el primer empleo tras la carrera", pct_dist("primera_ocupacion", f"{FILTRO} AND ha_trabajado=1"),
     place(24, 10, 0, 34), desc="Lo más parecido a 'qué encuentra un recién graduado'. Top 10.")
hbar("▾ Sector de la empresa donde trabajan", pct_dist("sector", TRABAJANDO), place(24, 10, 0, 44),
     desc="Actividad principal del establecimiento (CNAE). Top 10.")

# ---------- Calidad del empleo ----------
hbar("▾ Nivel de formación que requiere su puesto", pct_dist(
    "nivel_apropiado", TRABAJANDO, order="FIELD(nivel_apropiado,'Doctorado','Máster','Grado/licenciatura',"
    "'FP superior','FP medio / bachiller','FP básica','ESO, EGB o inferior')"),
     place(10, 9, 0, 54), desc="Según el propio graduado. Mide la sobrecualificación.")
hbar("▾ Sueldo mensual neto actual", f"""
SELECT CONCAT({PAD}, sueldo) AS categoria, SUM(factor)/SUM(SUM(factor)) OVER () AS pct
FROM graduados WHERE {TRABAJANDO} AND sueldo_cod BETWEEN 1 AND 7
GROUP BY sueldo, sueldo_cod ORDER BY sueldo_cod""", place(7, 9, 10, 54))
hbar("▾ Tiempo hasta el primer empleo", f"""
SELECT CONCAT({PAD}, tiempo_primer_empleo) AS categoria, SUM(factor)/SUM(SUM(factor)) OVER () AS pct
FROM graduados WHERE {FILTRO} AND tiempo_primer_empleo_cod BETWEEN 0 AND 6
GROUP BY tiempo_primer_empleo, tiempo_primer_empleo_cod ORDER BY tiempo_primer_empleo_cod""",
     place(7, 9, 17, 54), desc="Desde que terminaron la carrera.")

# ---------- Comparativa ----------
table("Física frente a otras titulaciones de ciencias", """
SELECT grupo AS `Titulación`, muestra AS `Encuestados`, tasa_empleo AS `Tasa de empleo`,
       pct_con_posgrado AS `Con máster o doctorado`, tasa_empleo_solo_grado AS `Empleo sin máster`,
       pct_mas_2000_eur AS `Gana > 2.000 €/mes`
FROM v_comparativa_titulaciones ORDER BY muestra""", place(24, 7, 0, 63),
      desc="Mismas definiciones para todas las titulaciones. 'Empleo sin máster' = tasa de empleo de quienes no tienen ni máster ni doctorado. 'Todos los graduados' = toda la EILU 2019.")

# ---------- Evolución 2015-2025 (SEPE) ----------
GRAY = "#8e8e8e"
TECH = {"I+D (investigación)": BLUE, "Informática y datos": ORANGE, "Ingeniería y servicios técnicos": AQUA}

text("", """
### Evolución de la contratación de físicos, 2015-2025
Fuente: **SEPE, Observatorio de las Ocupaciones**, *Información anual de mercado de trabajo de titulados universitarios*
(Licenciatura + Grado en Física), y **Ministerio de Ciencia, Innovación y Universidades** para los graduados.

**Cuidado al leer los contratos:** el SEPE solo registra los contratos de físicos **inscritos como demandantes de empleo** en los
servicios públicos de empleo, no los de todos los físicos. Cuenta **contratos, no personas**, y cada ficha lista solo las 10 actividades que más
contratan (por eso la industria casi nunca aparece y no se muestra). No hay datos por sector antes de 2015.

**¿Por qué bajan los contratos totales (1.489 en 2015 → 1.171 en 2025) si cada año se gradúan más físicos?** No es que haya menos físicos trabajando.
La caída se reparte en dos efectos:

① **Menos físicos pasan por el SEPE (≈ 80 % de la caída).** Las personas contratadas a través del SEPE bajan de 1.059 a 876 y los inscritos de 2.011 a 1.432,
mientras los graduados se duplican y el **paro registrado baja** de 1.325 a 903. La mayoría de los nuevos graduados encuentra trabajo sin inscribirse,
y la Licenciatura se extingue: sus titulados ya tienen 35-45 años y empleo estable.

② **La reforma laboral de 2022 redujo el número de contratos por persona (≈ 20 % de la caída).** El SEPE cuenta **contratos, no personas**:
antes, un físico con un trabajo temporal que se renovaba varias veces sumaba varios contratos; desde la reforma predominan los indefinidos, y un indefinido es
un solo contrato. Los indefinidos pasan del 22 % (2021) al 43 % (2022) de golpe, y los contratos por persona bajan de 1,39 a 1,33.
En **Grado en Física** se ve claramente: en 2016, 15 indefinidos (9 %) y 146 temporales; en 2025, **365 indefinidos (48 %)** y 393 temporales.
""", place(24, 10, 0, 70))

panels.append({
    "type": "trend", "title": "% de los contratos a físicos que van a cada sector", "datasource": DS,
    "description": "Contratos del sector / total de contratos a físicos de ese año. Educación (gris, discontinua) como referencia.",
    "gridPos": place(14, 11, 0, 80),
    "targets": [target("""
SELECT anio,
  SUM(contratos*(sector='I+D (investigación)'))/MAX(total)             AS `I+D (investigación)`,
  SUM(contratos*(sector='Informática y datos'))/MAX(total)             AS `Informática y datos`,
  SUM(contratos*(sector='Ingeniería y servicios técnicos'))/MAX(total) AS `Ingeniería y servicios técnicos`,
  SUM(contratos*(sector='Educación'))/MAX(total)                       AS `Educación`
FROM v_sepe_fisica_sector_anual GROUP BY anio ORDER BY anio""")],
    "fieldConfig": {
        "defaults": {"unit": "percentunit", "decimals": 1, "min": 0, "max": 0.4,
                     "custom": {"drawStyle": "line", "lineWidth": 2, "pointSize": 8, "showPoints": "always",
                                "fillOpacity": 0, "axisGridShow": True, "axisPlacement": "left"}},
        "overrides": color_by_name(TECH) + [
            {"matcher": {"id": "byName", "options": "Educación"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": GRAY}},
                            {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 10]}}]},
            {"matcher": {"id": "byName", "options": "anio"},
             "properties": [{"id": "unit", "value": "none"}, {"id": "decimals", "value": 0},
                            {"id": "min", "value": 2015}, {"id": "max", "value": 2025.4},
                            {"id": "displayName", "value": "Año"}]}]},
    "options": {"xField": "anio", "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "multi", "sort": "desc"}},
})

hbar("Contratos a físicos por año y sector", """
SELECT CAST(anio AS CHAR) AS categoria,
  SUM(contratos*(sector='I+D (investigación)'))             AS `I+D (investigación)`,
  SUM(contratos*(sector='Informática y datos'))             AS `Informática y datos`,
  SUM(contratos*(sector='Ingeniería y servicios técnicos')) AS `Ingeniería y servicios técnicos`,
  SUM(contratos*(sector='Educación'))                       AS `Educación`,
  SUM(contratos*(sector IN ('Otras actividades','Industria y energía'))) AS `Otras actividades`
FROM v_sepe_fisica_sector_anual GROUP BY anio ORDER BY anio""",
     place(10, 11, 14, 80), unit="none", stacked=True, normalize=False,
     desc="Número de contratos (no de personas), sumando Licenciatura y Grado en Física. El total baja: ver la explicación de arriba y los tres gráficos de debajo.",
     overrides=color_by_name({**TECH, "Educación": GRAY, "Otras actividades": "#4a4a4a"}))

# ---------- Por qué bajan los contratos: tres explicaciones ----------
def trend(title, sql, pos, colors, desc="", unit="percentunit", ymax=None, extra=None):
    panels.append({
        "type": "trend", "title": title, "description": desc, "datasource": DS, "gridPos": pos,
        "targets": [target(sql)],
        "fieldConfig": {
            "defaults": {"unit": unit, "decimals": 0 if unit == "none" else 1, "min": 0,
                         **({"max": ymax} if ymax else {}),
                         "custom": {"drawStyle": "line", "lineWidth": 2, "pointSize": 7, "showPoints": "always",
                                    "fillOpacity": 0, "axisGridShow": True, "axisPlacement": "left",
                                    "spanNulls": True}},
            "overrides": color_by_name(colors) + (extra or []) + [
                {"matcher": {"id": "byName", "options": "anio"},
                 "properties": [{"id": "unit", "value": "none"}, {"id": "decimals", "value": 0},
                                {"id": "min", "value": 2015}, {"id": "max", "value": 2025.4},
                                {"id": "displayName", "value": "Año"}]}]},
        "options": {"xField": "anio", "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    })


trend("① Graduados vs. inscritos SEPE", """
SELECT t.anio, e.graduados AS `Graduados del año`, t.demandantes AS `Inscritos en el SEPE`,
       t.parados AS `Parados registrados`
FROM (SELECT anio, SUM(demandantes) AS demandantes, SUM(parados) AS parados
      FROM sepe_contratos_total GROUP BY anio) t
LEFT JOIN (SELECT anio, SUM(egresados) AS graduados FROM egresados_fisica GROUP BY anio) e USING (anio)
ORDER BY t.anio""", place(6, 10, 0, 91), unit="none",
      colors={"Graduados del año": BLUE, "Inscritos en el SEPE": GRAY, "Parados registrados": ORANGE},
      desc="Inscritos y parados a 31 de diciembre. Los graduados se duplican mientras el paro registrado de físicos baja. "
           "El pico de 2020 es la COVID. Graduados: Ministerio de Universidades (desde 2016).")

trend("② Indefinidos (% de contratos)", """
SELECT anio, SUM(indefinidos)/SUM(indefinidos + temporales) AS `Indefinidos`
FROM sepe_contratos_total GROUP BY anio ORDER BY anio""", place(6, 10, 12, 91), ymax=0.6,
      colors={"Indefinidos": AQUA},
      desc="La reforma laboral (RDL 32/2021, en vigor en 2022) limitó los temporales. Menos renovaciones = menos "
           "contratos registrados por la misma gente trabajando.")

trend("② Contratos por persona", """
SELECT anio, SUM(contratos)/SUM(personas) AS `Contratos por persona`
FROM sepe_contratos_total GROUP BY anio ORDER BY anio""", place(6, 10, 18, 91), unit="none", ymax=1.6,
      colors={"Contratos por persona": ORANGE},
      extra=[{"matcher": {"id": "byName", "options": "Contratos por persona"},
              "properties": [{"id": "decimals", "value": 2}, {"id": "min", "value": 1.2}]}],
      desc="Contratos registrados / personas distintas contratadas en el año. Baja de ~1,40 a ~1,33 con la reforma "
           "laboral de 2022: menos renovaciones de temporales. Explica ≈ 20 % de la caída de contratos.")

trend("① Contratos Licenciatura/Grado", """
SELECT anio,
  SUM(contratos*(titulacion='LICENCIATURA EN FÍSICA'))          AS `Licenciatura`,
  SUM(contratos*(titulacion IN ('GRADO EN FÍSICA','GRADO EN FÍSICA APLICADA'))) AS `Grado`
FROM sepe_contratos_total GROUP BY anio ORDER BY anio""", place(6, 10, 6, 91), unit="none",
      colors={"Licenciatura": GRAY, "Grado": BLUE},
      desc="Los contratos de licenciados caen al estabilizarse (ya tienen 35-45 años). Los de graduados suben, pero no lo "
           "compensan porque la mayoría de graduados encuentra trabajo sin pasar por el SEPE.")

# ---------- Egresados en Física (Ministerio de Universidades) ----------
hbar("Graduados en Física por año (todas las universidades españolas)", """
SELECT CONCAT(anio, ': ', FORMAT(SUM(egresados), 0, 'de_DE')) AS categoria,
  SUM(egresados*(tipo='Grado en Física'))        AS `Grado en Física`,
  SUM(egresados*(tipo='Doble grado con Física')) AS `Doble grado con Física`,
  SUM(egresados*(tipo='Ingeniería Física'))      AS `Ingeniería Física`,
  SUM(egresados*(tipo='Licenciatura en Física')) AS `Licenciatura (a extinguir)`
FROM egresados_fisica GROUP BY anio ORDER BY anio""",
     place(24, 10, 0, 101), unit="none", stacked=True, normalize=False, orientation="vertical",
     desc="Egresados por curso académico (2024-25 = 2025). Fuente: Ministerio de Ciencia, Innovación y Universidades, "
          "Estadística de Estudiantes Universitarios. Los dobles grados (p. ej. Física + Matemáticas) cuentan una vez.",
     overrides=color_by_name({"Grado en Física": BLUE, "Doble grado con Física": ORANGE,
                              "Ingeniería Física": AQUA, "Licenciatura (a extinguir)": GRAY}))

dashboard = {
    "uid": "eilu-fisica",
    "title": "Inserción laboral de graduados en Física (INE EILU 2019)",
    "tags": ["INE", "EILU", "física", "empleo"],
    "timezone": "browser",
    "editable": True,
    "schemaVersion": 41,
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"hidden": True},
    "templating": {"list": [{
        "type": "custom", "name": "formacion", "label": "Formación",
        "query": "Solo grado/licenciatura,Máster,Doctorado",
        "multi": True, "includeAll": True,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "options": [],
    }]},
    "panels": [dict(p, id=i + 1) for i, p in enumerate(panels)],
}

with open(os.path.join(BASE, "dashboard_fisica.json"), "w", encoding="utf-8") as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)
print(f"{len(panels)} paneles -> dashboard_fisica.json")
