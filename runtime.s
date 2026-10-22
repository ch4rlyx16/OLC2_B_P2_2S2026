// ============================================================================
//  runtime.s -- Rutinas de apoyo de OxigenNative
//  io.s es del laboratorio y no se toca; esto es lo nuestro.
//
//    alloc          x0 = bytes     -> x0 = direccion reservada
//    to_upper       x1 = cadena    -> x0 = cadena nueva en MAYUSCULAS
//    to_lower       x1 = cadena    -> x0 = cadena nueva en minusculas
//    array_reverse  x1 = puntero   -> x0 = el mismo puntero, invertido
//    random         w0 = min, w1 = max          -> w0 en [min, max]
//    str_contains   x1 = cadena, x2 = aguja     -> w0 = 1 si la contiene
//    array_contains x1 = puntero, w2 = valor    -> w0 = 1 si esta
//    str_replace    x1 = cadena, x2 = viejo, x3 = nuevo -> x0 = cadena nueva
//    array_slice    x1 = puntero, w2 = inicio, w3 = fin  -> x0 = arreglo nuevo
//    str_split      x1 = cadena, x2 = separador          -> x0 = arreglo de cadenas
//    print_f64      d0 = numero    -> lo imprime con hasta 6 decimales
// ============================================================================

.bss
.align 4
monton:         .skip 65536

.data
.align 3
monton_libre:   .quad monton

.text
.global alloc
.global to_upper
.global to_lower
.global array_reverse

// ---------------------------------------------------------------------------
//  alloc(x0 = bytes) -> x0 = direccion
//  Reserva avanzando un puntero. Nunca libera: los programas son cortos.
// ---------------------------------------------------------------------------
alloc:
    adrp    x9, monton_libre
    add     x9, x9, :lo12:monton_libre
    ldr     x10, [x9]
    add     x11, x10, x0
    add     x11, x11, #15
    and     x11, x11, #-16
    str     x11, [x9]
    mov     x0, x10
    ret

// ---------------------------------------------------------------------------
//  to_upper(x1 = cadena terminada en 0) -> x0 = cadena nueva
// ---------------------------------------------------------------------------
to_upper:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    str     x19, [sp, #-16]!
    mov     x19, x1

    bl      strlen
    add     x0, x2, #1
    bl      alloc

    mov     x9, x19
    mov     x10, x0
up_loop:
    ldrb    w11, [x9], #1
    cmp     w11, #97
    b.lt    up_guarda
    cmp     w11, #122
    b.gt    up_guarda
    sub     w11, w11, #32
up_guarda:
    strb    w11, [x10], #1
    cbnz    w11, up_loop

    ldr     x19, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  to_lower(x1 = cadena terminada en 0) -> x0 = cadena nueva
// ---------------------------------------------------------------------------
to_lower:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    str     x19, [sp, #-16]!
    mov     x19, x1

    bl      strlen
    add     x0, x2, #1
    bl      alloc

    mov     x9, x19
    mov     x10, x0
low_loop:
    ldrb    w11, [x9], #1
    cmp     w11, #65
    b.lt    low_guarda
    cmp     w11, #90
    b.gt    low_guarda
    add     w11, w11, #32
low_guarda:
    strb    w11, [x10], #1
    cbnz    w11, low_loop

    ldr     x19, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  array_reverse(x1 = puntero al elemento 0) -> x0 = el mismo puntero
//  La longitud vive en la cabecera, en [x1, #-8].
// ---------------------------------------------------------------------------
array_reverse:
    mov     x0, x1
    ldr     x2, [x1, #-8]
    cmp     x2, #2
    b.lt    rev_fin
    mov     x3, x1
    sub     x4, x2, #1
    add     x4, x1, x4, lsl #3
rev_loop:
    cmp     x3, x4
    b.hs    rev_fin
    ldr     x5, [x3]
    ldr     x6, [x4]
    str     x6, [x3]
    str     x5, [x4]
    add     x3, x3, #8
    sub     x4, x4, #8
    b       rev_loop
rev_fin:
    ret
.bss
.align 3
rnd_ts:         .skip 16

.data
.align 3
rnd_estado:     .quad 0

.text
.global random
.global str_contains
.global array_contains
.global str_replace
.global array_slice
.global str_split
.global print_f64

// ---------------------------------------------------------------------------
//  rnd_siguiente() -> w0 = pseudoaleatorio no negativo
// ---------------------------------------------------------------------------
rnd_siguiente:
    adrp    x9, rnd_estado
    add     x9, x9, :lo12:rnd_estado
    ldr     x10, [x9]
    cbnz    x10, rnd_tiene

    mov     x0, #1
    adrp    x1, rnd_ts
    add     x1, x1, :lo12:rnd_ts
    mov     x8, #113
    svc     #0
    adrp    x11, rnd_ts
    add     x11, x11, :lo12:rnd_ts
    ldr     x10, [x11, #8]
    orr     x10, x10, #1
    adrp    x9, rnd_estado
    add     x9, x9, :lo12:rnd_estado

rnd_tiene:
    mov     w11, #0x4E6D
    movk    w11, #0x41C6, lsl #16
    mul     w10, w10, w11
    mov     w12, #12345
    add     w10, w10, w12
    str     x10, [x9]
    ubfx    w0, w10, #8, #23
    ret

// ---------------------------------------------------------------------------
//  random(w0 = min, w1 = max) -> w0 en [min, max]
// ---------------------------------------------------------------------------
random:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    stp     x19, x20, [sp, #-16]!
    mov     w19, w0
    mov     w20, w1

    cmp     w19, w20
    b.gt    rnd_solo_min

    bl      rnd_siguiente
    sub     w1, w20, w19
    add     w1, w1, #1
    udiv    w2, w0, w1
    msub    w0, w2, w1, w0
    add     w0, w0, w19
    b       rnd_salir

rnd_solo_min:
    mov     w0, w19
rnd_salir:
    ldp     x19, x20, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  str_contains(x1 = cadena, x2 = aguja) -> w0 = 1 si la contiene
// ---------------------------------------------------------------------------
str_contains:
    mov     x3, x1
cont_outer:
    mov     x4, x3
    mov     x5, x2
cont_inner:
    ldrb    w6, [x5], #1
    cbz     w6, cont_si
    ldrb    w7, [x4], #1
    cbz     w7, cont_no
    cmp     w6, w7
    b.ne    cont_avanza
    b       cont_inner
cont_avanza:
    ldrb    w7, [x3]
    cbz     w7, cont_no
    add     x3, x3, #1
    b       cont_outer
cont_si:
    mov     w0, #1
    ret
cont_no:
    mov     w0, #0
    ret

// ---------------------------------------------------------------------------
//  array_contains(x1 = puntero, w2 = valor) -> w0 = 1 si esta
// ---------------------------------------------------------------------------
array_contains:
    ldr     x3, [x1, #-8]
    mov     x4, #0
arrc_loop:
    cmp     x4, x3
    b.hs    arrc_no
    ldr     x5, [x1, x4, lsl #3]
    cmp     w5, w2
    b.eq    arrc_si
    add     x4, x4, #1
    b       arrc_loop
arrc_si:
    mov     w0, #1
    ret
arrc_no:
    mov     w0, #0
    ret

// ---------------------------------------------------------------------------
//  str_replace(x1 = cadena, x2 = viejo, x3 = nuevo) -> x0 = cadena nueva
//  Dos pasadas: contar ocurrencias, reservar lo justo, copiar reemplazando.
// ---------------------------------------------------------------------------
str_replace:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    stp     x19, x20, [sp, #-16]!
    stp     x21, x22, [sp, #-16]!
    stp     x23, x24, [sp, #-16]!

    mov     x19, x1                 // cadena
    mov     x20, x2                 // viejo
    mov     x21, x3                 // nuevo

    mov     x1, x19
    bl      strlen
    mov     x22, x2                 // len(cadena)
    mov     x1, x20
    bl      strlen
    mov     x23, x2                 // len(viejo)
    mov     x1, x21
    bl      strlen
    mov     x24, x2                 // len(nuevo)

    cbz     x23, rep_devuelve_original

    // --- pasada 1: contar ocurrencias en x6 ---
    mov     x6, #0
    mov     x4, x19
rep_cuenta:
    ldrb    w7, [x4]
    cbz     w7, rep_cuenta_fin
    mov     x8, x4
    mov     x9, x20
rep_cmp:
    ldrb    w10, [x9], #1
    cbz     w10, rep_hallado
    ldrb    w11, [x8], #1
    cmp     w10, w11
    b.ne    rep_no_hallado
    b       rep_cmp
rep_hallado:
    add     x6, x6, #1
    add     x4, x4, x23
    b       rep_cuenta
rep_no_hallado:
    add     x4, x4, #1
    b       rep_cuenta
rep_cuenta_fin:
    cbz     x6, rep_devuelve_original

    // --- reservar: len + n*(len_nuevo - len_viejo) + 1 ---
    mul     x12, x6, x24
    mul     x13, x6, x23
    add     x0, x22, x12
    sub     x0, x0, x13
    add     x0, x0, #1
    bl      alloc
    mov     x14, x0                 // destino (se conserva para devolver)
    mov     x15, x0                 // puntero de escritura

    // --- pasada 2: copiar reemplazando ---
    mov     x4, x19
rep_copia:
    ldrb    w7, [x4]
    cbz     w7, rep_copia_fin
    mov     x8, x4
    mov     x9, x20
rep_cmp2:
    ldrb    w10, [x9], #1
    cbz     w10, rep_pega_nuevo
    ldrb    w11, [x8], #1
    cmp     w10, w11
    b.ne    rep_pega_byte
    b       rep_cmp2
rep_pega_nuevo:
    mov     x9, x21
rep_pega_nuevo_loop:
    ldrb    w10, [x9], #1
    cbz     w10, rep_pega_nuevo_fin
    strb    w10, [x15], #1
    b       rep_pega_nuevo_loop
rep_pega_nuevo_fin:
    add     x4, x4, x23
    b       rep_copia
rep_pega_byte:
    ldrb    w10, [x4], #1
    strb    w10, [x15], #1
    b       rep_copia
rep_copia_fin:
    strb    wzr, [x15]
    mov     x0, x14
    b       rep_salir

rep_devuelve_original:
    mov     x0, x19
rep_salir:
    ldp     x23, x24, [sp], #16
    ldp     x21, x22, [sp], #16
    ldp     x19, x20, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  array_slice(x1 = puntero, w2 = inicio, w3 = fin) -> x0 = arreglo nuevo
//  Copia [inicio, fin) a un bloque nuevo con su propia cabecera de longitud.
// ---------------------------------------------------------------------------
array_slice:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    stp     x19, x20, [sp, #-16]!
    stp     x21, x22, [sp, #-16]!

    mov     x19, x1
    mov     w20, w2
    sub     w21, w3, w2
    cmp     w21, #0
    b.ge    sl_ok
    mov     w21, #0
sl_ok:
    add     x0, x21, #1
    lsl     x0, x0, #3
    bl      alloc
    mov     x22, x0
    str     x21, [x22]
    add     x22, x22, #8
    mov     x0, x22

    mov     x9, #0
sl_loop:
    cmp     x9, x21
    b.hs    sl_fin
    add     x10, x9, x20
    ldr     x11, [x19, x10, lsl #3]
    str     x11, [x22, x9, lsl #3]
    add     x9, x9, #1
    b       sl_loop
sl_fin:
    ldp     x21, x22, [sp], #16
    ldp     x19, x20, [sp], #16
    ldp     x29, x30, [sp], #16
    ret

// ---------------------------------------------------------------------------
//  str_split(x1 = cadena, x2 = separador) -> x0 = arreglo de cadenas
//  Dos pasadas: contar trozos, reservar el arreglo, cortar y copiar cada uno.
// ---------------------------------------------------------------------------
str_split:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    stp     x19, x20, [sp, #-16]!
    stp     x21, x22, [sp, #-16]!
    stp     x23, x24, [sp, #-16]!

    mov     x19, x1                 // cadena
    mov     x20, x2                 // separador

    mov     x1, x20
    bl      strlen
    mov     x21, x2                 // len(separador)
    cbz     x21, sp_uno_solo

    // --- pasada 1: contar trozos (ocurrencias + 1) ---
    mov     x22, #1
    mov     x4, x19
sp_cuenta:
    ldrb    w7, [x4]
    cbz     w7, sp_cuenta_fin
    mov     x8, x4
    mov     x9, x20
sp_cmp:
    ldrb    w10, [x9], #1
    cbz     w10, sp_hallado
    ldrb    w11, [x8], #1
    cmp     w10, w11
    b.ne    sp_no
    b       sp_cmp
sp_hallado:
    add     x22, x22, #1
    add     x4, x4, x21
    b       sp_cuenta
sp_no:
    add     x4, x4, #1
    b       sp_cuenta
sp_cuenta_fin:

    // --- reservar el arreglo de punteros ---
    add     x0, x22, #1
    lsl     x0, x0, #3
    bl      alloc
    str     x22, [x0]
    add     x23, x0, #8             // x23 = elemento 0 del arreglo
    mov     x24, #0                 // indice del trozo

    // --- pasada 2: cortar y copiar ---
    mov     x4, x19                 // inicio del trozo actual
sp_corta:
    mov     x5, x4                  // explorador
sp_busca:
    ldrb    w7, [x5]
    cbz     w7, sp_ultimo
    mov     x8, x5
    mov     x9, x20
sp_cmp2:
    ldrb    w10, [x9], #1
    cbz     w10, sp_corte_aqui
    ldrb    w11, [x8], #1
    cmp     w10, w11
    b.ne    sp_sigue
    b       sp_cmp2
sp_sigue:
    add     x5, x5, #1
    b       sp_busca

sp_corte_aqui:
    sub     x6, x5, x4              // largo del trozo
    bl      sp_copia_trozo
    add     x4, x5, x21             // saltar el separador
    b       sp_corta

sp_ultimo:
    sub     x6, x5, x4
    bl      sp_copia_trozo
    sub     x0, x23, #8
    add     x0, x0, #8
    b       sp_salir

// copia x6 bytes desde x4 a un bloque nuevo y lo guarda en x23[x24]
sp_copia_trozo:
    stp     x29, x30, [sp, #-16]!
    mov     x0, x6
    add     x0, x0, #1
    bl      alloc
    str     x0, [x23, x24, lsl #3]
    add     x24, x24, #1
    mov     x12, x4
    mov     x13, x0
    mov     x14, #0
sp_cp:
    cmp     x14, x6
    b.hs    sp_cp_fin
    ldrb    w15, [x12], #1
    strb    w15, [x13], #1
    add     x14, x14, #1
    b       sp_cp
sp_cp_fin:
    strb    wzr, [x13]
    ldp     x29, x30, [sp], #16
    ret

sp_uno_solo:
    mov     x0, #16
    bl      alloc
    mov     x9, #1
    str     x9, [x0]
    add     x0, x0, #8
    str     x19, [x0]
sp_salir:
    ldp     x23, x24, [sp], #16
    ldp     x21, x22, [sp], #16
    ldp     x19, x20, [sp], #16
    ldp     x29, x30, [sp], #16
    ret
.data
pf_menos:   .asciz "-"
pf_punto:   .asciz "."

.bss
.align 3
pf_buf:     .skip 16

.text

// ---------------------------------------------------------------------------
//  print_f64(d0 = numero) -> imprime con hasta 6 decimales, sin ceros de sobra
// ---------------------------------------------------------------------------
print_f64:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    stp     x19, x20, [sp, #-16]!
    stp     x21, x22, [sp, #-16]!

    fcmp    d0, #0.0
    b.ge    pf_pos
    str     d0, [sp, #-16]!
    adrp    x1, pf_menos
    add     x1, x1, :lo12:pf_menos
    bl      print_cstr
    ldr     d0, [sp], #16
    fneg    d0, d0
pf_pos:
    // --- parte entera ---
    fcvtzs  x19, d0
    str     d0, [sp, #-16]!
    mov     w0, w19
    bl      print_num
    ldr     d0, [sp], #16

    // --- parte fraccionaria * 1000000 ---
    scvtf   d1, x19
    fsub    d0, d0, d1
    movz    x9, #0x4240
    movk    x9, #0xF, lsl #16       // x9 = 1000000
    scvtf   d2, x9
    fmul    d0, d0, d2
    fcvtzu  w20, d0
    cbz     w20, pf_fin

    // --- 6 digitos en el buffer, de atras hacia adelante ---
    adrp    x21, pf_buf
    add     x21, x21, :lo12:pf_buf
    add     x22, x21, #6
    strb    wzr, [x22]
    mov     w9, #10
    mov     x10, #6
pf_dig:
    sub     x22, x22, #1
    udiv    w11, w20, w9
    msub    w12, w11, w9, w20
    add     w12, w12, #48
    strb    w12, [x22]
    mov     w20, w11
    subs    x10, x10, #1
    b.ne    pf_dig

    // --- quitar ceros finales, dejando al menos un digito ---
    add     x22, x21, #5
pf_quita:
    cmp     x22, x21
    b.ls    pf_imprime
    ldrb    w11, [x22]
    cmp     w11, #48
    b.ne    pf_imprime
    strb    wzr, [x22]
    sub     x22, x22, #1
    b       pf_quita

pf_imprime:
    adrp    x1, pf_punto
    add     x1, x1, :lo12:pf_punto
    bl      print_cstr
    adrp    x1, pf_buf
    add     x1, x1, :lo12:pf_buf
    bl      print_cstr

pf_fin:
    ldp     x21, x22, [sp], #16
    ldp     x19, x20, [sp], #16
    ldp     x29, x30, [sp], #16
    ret
