"""
OxigenScript — Reportes
"""

import html
import shutil
import subprocess
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / 'reportes'


# ---------------------------------------------------------------------------
# AST -> DOT
# ---------------------------------------------------------------------------

def _texto_dot(etiqueta):
    """Deja una etiqueta segura para meterla entre comillas en un DOT.

    Hay que escapar la barra invertida ANTES que las comillas: si se hiciera al
    revés, la barra que agrega el escape de la comilla se volvería a escapar.
    """
    limpio = str(etiqueta).replace('\\', '\\\\').replace('"', '\\"')
    limpio = limpio.replace('\n', '\\n')
    # Un literal muy largo desarma el diagrama; se recorta.
    return limpio if len(limpio) <= 40 else limpio[:37] + '...'


def ast_a_dot(arbol):
    """Devuelve el código fuente DOT del árbol."""
    lineas = [
        'digraph AST {',
        '    rankdir=TB;',
        '    bgcolor="white";',
        '    node [shape=box, style="rounded,filled", fillcolor="#eef2f7",',
        '          color="#7f9ac0", fontname="Helvetica", fontsize=10,',
        '          margin="0.12,0.06"];',
        '    edge [color="#7f9ac0", arrowsize=0.7];',
    ]

    contador = [0]

    def recorrer(nodo, padre=None):
        if nodo is None:
            return
        mio = f'n{contador[0]}'
        contador[0] += 1
        lineas.append(f'    {mio} [label="{_texto_dot(nodo.etiqueta())}"];')
        if padre is not None:
            lineas.append(f'    {padre} -> {mio};')
        for hijo in nodo.hijos():
            recorrer(hijo, mio)

    if arbol is not None:
        recorrer(arbol)

    lineas.append('}')
    return '\n'.join(lineas)


def hay_graphviz():
    return shutil.which('dot') is not None


def renderizar(dot, formato='svg'):
    """Convierte el DOT a imagen llamando al binario `dot`.

    Devuelve el contenido (str para svg, bytes para png) o None si Graphviz no
    está instalado o falla. Nunca lanza: si no se puede dibujar, la GUI cae de
    vuelta al árbol en texto.
    """
    if not hay_graphviz():
        return None
    try:
        resultado = subprocess.run(
            ['dot', f'-T{formato}'],
            input=dot.encode('utf-8'),
            capture_output=True,
            timeout=20,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return (resultado.stdout.decode('utf-8', 'replace')
            if formato == 'svg' else resultado.stdout)


# ---------------------------------------------------------------------------
# Tabla de símbolos -> HTML
# ---------------------------------------------------------------------------

_ESTILO = """
    body { font-family: system-ui, sans-serif; margin: 24px; color: #24292f; }
    h1 { font-size: 18px; }
    table { border-collapse: collapse; width: 100%; font-size: 13px; }
    th, td { border: 1px solid #d4d8dd; padding: 6px 9px; text-align: left; }
    th { background: #eef2f7; }
    tr:nth-child(even) td { background: #fafbfc; }
    code { font-family: Consolas, monospace; }
"""


def tabla_simbolos_html(simbolos):
    filas = []
    for i, s in enumerate(simbolos, 1):
        # html.escape en cada celda: los valores vienen del programa del
        # usuario y podrían traer < o & y romper el documento.
        celdas = ''.join(
            f'<td>{html.escape(str(s[c]))}</td>'
            for c in ('identificador', 'categoria', 'tipo',
                      'ambito', 'linea', 'valor'))
        filas.append(f'<tr><td>{i}</td>{celdas}</tr>')

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Tabla de símbolos</title>
<style>{_ESTILO}</style></head>
<body>
<h1>Tabla de símbolos — OxigenScript</h1>
<table>
<thead><tr><th>No.</th><th>Identificador</th><th>Categoría</th><th>Tipo</th>
<th>Ámbito</th><th>Línea</th><th>Valor</th></tr></thead>
<tbody>{''.join(filas) or '<tr><td colspan="7">Sin símbolos.</td></tr>'}</tbody>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Escritura a disco
# ---------------------------------------------------------------------------

def guardar(arbol, simbolos, carpeta=CARPETA):
    """Escribe ast.dot, ast.svg y simbolos.html. Devuelve qué se pudo generar.

    El enunciado pide que los reportes se generen "automáticamente al finalizar
    la ejecución", así que esto lo llama el intérprete, no la GUI.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    generados = {}

    dot = ast_a_dot(arbol)
    ruta_dot = carpeta / 'ast.dot'
    ruta_dot.write_text(dot, encoding='utf-8')
    generados['dot'] = str(ruta_dot)

    svg = renderizar(dot, 'svg')
    if svg is not None:
        ruta_svg = carpeta / 'ast.svg'
        ruta_svg.write_text(svg, encoding='utf-8')
        generados['svg'] = str(ruta_svg)

    ruta_html = carpeta / 'simbolos.html'
    ruta_html.write_text(tabla_simbolos_html(simbolos), encoding='utf-8')
    generados['simbolos'] = str(ruta_html)

    return generados, svg
