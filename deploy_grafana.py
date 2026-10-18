"""Crea/actualiza el datasource MySQL y el dashboard en el Grafana local vía API.

Necesita un token de service account (rol Admin) en el fichero .grafana_token.
"""
import json
import os
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
GRAFANA = "http://localhost:3000"
TOKEN = open(os.path.join(BASE, ".grafana_token"), encoding="utf-8").read().strip()
MYSQL_PASS = open(os.path.join(BASE, ".mysql_grafana_pass"), encoding="utf-8").read().strip()


def api(method, path, body=None):
    req = urllib.request.Request(GRAFANA + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


datasource = {
    "uid": "eilu-mysql", "name": "MySQL - EILU (INE)", "type": "mysql", "access": "proxy",
    "url": "localhost:3306", "user": "grafana",
    "jsonData": {"database": "eilu", "maxOpenConns": 5},
    "secureJsonData": {"password": MYSQL_PASS},
}
status, _ = api("GET", "/api/datasources/uid/eilu-mysql")
if status == 200:
    print("datasource update:", api("PUT", "/api/datasources/uid/eilu-mysql", datasource)[0])
else:
    print("datasource create:", api("POST", "/api/datasources", datasource)[0])

print("datasource health:", api("GET", "/api/datasources/uid/eilu-mysql/health")[1].get("message"))

dashboard = json.load(open(os.path.join(BASE, "dashboard_fisica.json"), encoding="utf-8"))
status, res = api("POST", "/api/dashboards/db", {"dashboard": dashboard, "overwrite": True})
print("dashboard:", status, GRAFANA + res.get("url", "") if status == 200 else res)
