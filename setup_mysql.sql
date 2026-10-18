-- Usuario de solo lectura con el que Grafana consulta la base `eilu`.
-- Cambia la contraseña y guárdala en .mysql_grafana_pass (deploy_grafana.py la lee de ahí).
DROP USER IF EXISTS 'grafana'@'localhost';
CREATE USER 'grafana'@'localhost' IDENTIFIED BY 'cambia-esta-contraseña';
GRANT SELECT ON eilu.* TO 'grafana'@'localhost';
