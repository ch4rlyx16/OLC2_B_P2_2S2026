"""
Capa de servicios: la API REST que expone nos da el interprete
"""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from interprete.interprete import ejecutar


def editor(request):
    """La única página de la aplicación."""
    return render(request, 'web/editor.html')


@require_POST
def api_ejecutar(request):
    """POST {"codigo": "..."} -> {salida, errores, simbolos, ast, tiempo}"""
    try:
        datos = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'detalle': 'El cuerpo no es JSON válido.'},
                            status=400)

    codigo = datos.get('codigo', '')
    if not isinstance(codigo, str):
        return JsonResponse({'detalle': "El campo 'codigo' debe ser texto."},
                            status=400)

    
    return JsonResponse(ejecutar(codigo))
