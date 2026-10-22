"""
OxigenNative — Pipeline de compilación

Lleva el código fuente desde el texto hasta la salida del programa:

    fuente -> parser -> AST -> generar() -> ensamblador ARM64
           -> aarch64-linux-gnu-as   -> .o
           -> aarch64-linux-gnu-ld   -> ejecutable (con io.s)
           -> qemu-aarch64           -> salida en consola
"""

import os
import subprocess
import tempfile
import time
from . import reportes

from .errores import errores
from .generador import Generador
from .parser import analizar


# La carpeta del proyecto es la de arriba de compilador/
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IO_S = os.path.join(RAIZ, 'io.s')
RUNTIME_S = os.path.join(RAIZ, 'runtime.s')
RUNTIME_S = os.path.join(RAIZ, 'runtime.s')

ENSAMBLADOR = 'aarch64-linux-gnu-as'
ENLAZADOR = 'aarch64-linux-gnu-ld'
EMULADOR = 'qemu-aarch64'

LIMITE = 5          # segundos antes de matar el programa del usuario
LIMITE_HERRAMIENTA = 20


class FalloDeHerramienta(Exception):
    """Falló as, ld o qemu: no es un error del programa del usuario."""


def _correr_orden(orden, limite, entrada=''):
    """Lanza un proceso externo y traduce sus fallos a algo legible."""
    try:
        return subprocess.run(orden, input=entrada, capture_output=True,
                              text=True, timeout=limite)
    except FileNotFoundError:
        raise FalloDeHerramienta(
            f"No se encontro '{orden[0]}'.\n"
            'Instala la cadena de herramientas con:\n'
            '  sudo apt install binutils-aarch64-linux-gnu qemu-user')
    except subprocess.TimeoutExpired:
        raise FalloDeHerramienta(
            f'El programa paso de {limite} segundos y se detuvo.\n'
            'Puede que haya un bucle infinito.')


def ensamblar_y_correr(asm, entrada=''):
    """Ensambla, enlaza con io.s y ejecuta en QEMU. Devuelve lo que imprimio."""
    for ruta in (IO_S, RUNTIME_S):
        if not os.path.exists(ruta):
            raise FalloDeHerramienta(
                f'No se encontro la libreria de rutinas en {ruta}')

    with tempfile.TemporaryDirectory(prefix='oxigen_') as carpeta:
        ruta_s = os.path.join(carpeta, 'programa.s')
        obj_programa = os.path.join(carpeta, 'programa.o')
        obj_io = os.path.join(carpeta, 'io.o')
        obj_runtime = os.path.join(carpeta, 'runtime.o')
        ejecutable = os.path.join(carpeta, 'programa')

        with open(ruta_s, 'w', encoding='utf-8') as archivo:
            archivo.write(asm + '\n')

        paso = _correr_orden([ENSAMBLADOR, '-o', obj_programa, ruta_s],
                             LIMITE_HERRAMIENTA)
        if paso.returncode != 0:
            raise FalloDeHerramienta(
                'El ensamblador rechazo el codigo generado:\n' + paso.stderr)

        paso = _correr_orden([ENSAMBLADOR, '-o', obj_io, IO_S],
                             LIMITE_HERRAMIENTA)
        if paso.returncode != 0:
            raise FalloDeHerramienta(
                'No se pudo ensamblar io.s:\n' + paso.stderr)

        paso = _correr_orden([ENSAMBLADOR, '-o', obj_runtime, RUNTIME_S],
                             LIMITE_HERRAMIENTA)
        if paso.returncode != 0:
            raise FalloDeHerramienta(
                'No se pudo ensamblar runtime.s:\n' + paso.stderr)

        paso = _correr_orden([ENLAZADOR, '-o', ejecutable, obj_programa,
                              obj_runtime, obj_io], LIMITE_HERRAMIENTA)
        if paso.returncode != 0:
            raise FalloDeHerramienta('El enlazado fallo:\n' + paso.stderr)

        paso = _correr_orden([EMULADOR, ejecutable], LIMITE, entrada)

        salida = paso.stdout
        if paso.stderr:
            salida += '\n' + paso.stderr
        if paso.returncode != 0:
            salida += f'\n[el programa termino con codigo {paso.returncode}]'
        return salida


def compilar(codigo, entrada='', ejecutar=True):
    """fuente -> {salida, ensamblador, errores, ...} listo para el JSON."""
    inicio = time.perf_counter()

    arbol = analizar(codigo)        # analizar() limpia la lista de errores

    generador = Generador()
    ensamblador = ''
    if arbol is not None and not errores.hay_errores():
        try:
            arbol.generar(generador)
            ensamblador = generador.codigo()
        except Exception as fallo:
            errores.semantico(
                f'Error interno del compilador: '
                f'{type(fallo).__name__}: {fallo}', 0, 0)
            ensamblador = ''

    salida = ''
    if ejecutar and ensamblador and not errores.hay_errores():
        try:
            salida = ensamblar_y_correr(ensamblador, entrada)
        except FalloDeHerramienta as fallo:
            salida = str(fallo)

    ast_texto = reportes.arbol_a_texto(arbol)
    archivos, ast_svg = reportes.guardar(arbol, generador.simbolos)

    return {
        'salida': salida,
        'ensamblador': ensamblador,
        'errores': [e.como_dict() for e in errores.ordenados()],
        'simbolos': generador.simbolos,
        'ast': ast_texto,
        'ast_svg': ast_svg or '',
        'archivos': archivos,
        'tiempo': round(time.perf_counter() - inicio, 4),
    }


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8') as archivo:
            fuente = archivo.read()
    else:
        fuente = sys.stdin.read()

    resultado = compilar(fuente)

    if resultado['errores']:
        print('--- errores ---')
        for error in resultado['errores']:
            print(error)
        print()

    print('--- ensamblador ---')
    print(resultado['ensamblador'])
    print('--- salida ---')
    print(resultado['salida'], end='')
