/* OxigenScript — lógica de la interfaz. */

const codigo   = document.getElementById('codigo');
const numeros  = document.getElementById('numeros');
const consola  = document.getElementById('consola');
const archivo  = document.getElementById('archivo');
const btnEjecutar = document.getElementById('btn-ejecutar');

let nombreArchivo = 'programa.oxs';

/* ---------- numeración de líneas ---------- */

function pintarNumeros() {
    const total = codigo.value.split('\n').length;
    let texto = '';
    for (let i = 1; i <= total; i++) texto += i + '\n';
    numeros.textContent = texto;
   
    numeros.scrollTop = codigo.scrollTop;
}

codigo.addEventListener('input', pintarNumeros);
codigo.addEventListener('scroll', () => { numeros.scrollTop = codigo.scrollTop; });

// Tab dentro del textarea indenta en vez de saltar al siguiente control.
codigo.addEventListener('keydown', (evento) => {
    if (evento.key !== 'Tab') return;
    evento.preventDefault();
    const ini = codigo.selectionStart, fin = codigo.selectionEnd;
    codigo.value = codigo.value.slice(0, ini) + '    ' + codigo.value.slice(fin);
    codigo.selectionStart = codigo.selectionEnd = ini + 4;
    pintarNumeros();
});

/* ---------- consola ---------- */

function limpiarConsola() { consola.textContent = ''; }

function escribir(texto, clase) {
    const linea = document.createElement('span');
    if (clase) linea.className = clase;
    linea.textContent = texto + '\n';
    consola.appendChild(linea);
    consola.scrollTop = consola.scrollHeight;
}

/* ---------- utilidades ---------- */


function seguro(texto) {
    const nodo = document.createElement('div');
    nodo.textContent = texto === null || texto === undefined ? '' : String(texto);
    return nodo.innerHTML;
}

function mostrarPanel(id, html) {
    document.getElementById(id).innerHTML = html;
}

/* ---------- pestañas ---------- */

document.querySelectorAll('.pestana').forEach((pestana) => {
    pestana.addEventListener('click', () => {
        document.querySelectorAll('.pestana').forEach(p => p.classList.remove('activa'));
        document.querySelectorAll('.contenido').forEach(c => c.classList.remove('visible'));
        pestana.classList.add('activa');
        document.getElementById(pestana.dataset.panel).classList.add('visible');
    });
});

/* ---------- reportes ---------- */

function pintarErrores(errores) {
    const chip = document.getElementById('conteo-errores');
    chip.textContent = errores.length;
    chip.classList.toggle('hay', errores.length > 0);

    if (errores.length === 0) {
        mostrarPanel('p-errores', '<p class="vacio">No se encontraron errores.</p>');
        return;
    }

    const filas = errores.map((e, i) => `
        <tr class="error">
            <td class="num">${i + 1}</td>
            <td class="tipo">${seguro(e.tipo)}</td>
            <td>${seguro(e.descripcion)}</td>
            <td class="num">${e.linea}</td>
            <td class="num">${e.columna}</td>
        </tr>`).join('');

    mostrarPanel('p-errores', `<table>
        <thead><tr><th>No.</th><th>Tipo</th><th>Descripción</th>
                   <th>Línea</th><th>Columna</th></tr></thead>
        <tbody>${filas}</tbody></table>`);
}

function pintarSimbolos(simbolos) {
    if (simbolos.length === 0) {
        mostrarPanel('p-simbolos', '<p class="vacio">No hay símbolos registrados.</p>');
        return;
    }

    const filas = simbolos.map((s, i) => `
        <tr>
            <td class="num">${i + 1}</td>
            <td><code>${seguro(s.identificador)}</code></td>
            <td>${seguro(s.categoria)}</td>
            <td><code>${seguro(s.tipo)}</code></td>
            <td>${seguro(s.ambito)}</td>
            <td class="num">${s.linea}</td>
            <td><code>${seguro(s.valor)}</code></td>
        </tr>`).join('');

    mostrarPanel('p-simbolos', `<table>
        <thead><tr><th>No.</th><th>Identificador</th><th>Categoría</th>
                   <th>Tipo</th><th>Ámbito</th><th>Línea</th><th>Valor</th></tr></thead>
        <tbody>${filas}</tbody></table>`);
}

function pintarAst(datos) {
    if (datos.ast_svg) {
        // El SVG viene de Graphviz, que ya escapa las etiquetas al generarlo.
        // Se inserta tal cual para poder hacerle zoom con CSS; si se escapara
        // se vería el código XML en vez del dibujo.
        mostrarPanel('p-ast', `<div class="grafico">${datos.ast_svg}</div>`);
        return;
    }
    // Sin Graphviz instalado se cae de vuelta al árbol en texto, que siempre
    // está disponible.
    mostrarPanel('p-ast', datos.ast
        ? `<p class="vacio">Graphviz no está disponible; se muestra el árbol en texto.</p>
           <pre class="arbol">${seguro(datos.ast)}</pre>`
        : '<p class="vacio">No se pudo construir el árbol.</p>');
}

/* ---------- ejecutar ---------- */

async function ejecutar() {
    btnEjecutar.disabled = true;
    limpiarConsola();
    escribir('> Ejecutando OxigenScript...', 'estado');

    try {
        const respuesta = await fetch('/api/ejecutar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CSRF_TOKEN,
            },
            body: JSON.stringify({ codigo: codigo.value }),
        });

        if (!respuesta.ok) {
            escribir(`El servidor respondió ${respuesta.status}.`, 'fallo');
            return;
        }

        const datos = await respuesta.json();

        if (datos.errores.length === 0) {
            escribir('--- Compilación exitosa ---', 'estado');
        } else {
            escribir(`--- Se encontraron ${datos.errores.length} error(es) ---`, 'fallo');
        }

        if (datos.salida) escribir(datos.salida);

        escribir('--- Fin de la ejecución ---', 'estado');

        pintarErrores(datos.errores);
        pintarSimbolos(datos.simbolos);
        pintarAst(datos);

    } catch (fallo) {
    //servidor caido
        escribir('No se pudo contactar al servidor: ' + fallo.message, 'fallo');
    } finally {
        btnEjecutar.disabled = false;
    }
}

btnEjecutar.addEventListener('click', ejecutar);

/* ---------- archivo ---------- */

document.getElementById('btn-nuevo').addEventListener('click', () => {
    if (codigo.value.trim() && !confirm('Se perderá el código actual. ¿Continuar?')) return;
    codigo.value = 'fn main() {\n    \n}\n';
    nombreArchivo = 'programa.oxs';
    pintarNumeros();
    limpiarConsola();
});

document.getElementById('btn-abrir').addEventListener('click', () => archivo.click());

archivo.addEventListener('change', () => {
    const elegido = archivo.files[0];
    if (!elegido) return;
    const lector = new FileReader();
    lector.onload = () => {
        codigo.value = lector.result;
        nombreArchivo = elegido.name;
        pintarNumeros();
        escribir(`Archivo abierto: ${elegido.name}`, 'estado');
    };
    lector.readAsText(elegido);
    archivo.value = '';   
});

document.getElementById('btn-guardar').addEventListener('click', () => {
    const enlace = document.createElement('a');
    const blob = new Blob([codigo.value], { type: 'text/plain;charset=utf-8' });
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombreArchivo;
    enlace.click();
    URL.revokeObjectURL(enlace.href);
});

/* ---------- arranque ---------- */

pintarNumeros();
escribir('> empecemos crack', 'estado');
