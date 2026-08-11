# RUNBOOK — GranjaManager como servicio a clientes

Cada cliente (ganadería) tiene su propia app y volumen en Fly.io, totalmente
aislados entre sí (misma base de código, datos separados). No hay panel
central ni facturación automática — ambas cosas se gestionan a mano por ahora.

## Dar de alta un cliente nuevo

**Formulario** (para no tener que recordar la sintaxis de los flags): abre
`scripts/formulario_despliegue.html` en el navegador — rellena nombre, slug y
los módulos con checkboxes, y te da el comando exacto listo para copiar. No
ejecuta nada por sí solo, solo genera el texto del comando de abajo.

```bash
./scripts/provisionar_cliente.sh <slug-app> "<Nombre de la explotación>"
```

Ejemplo:

```bash
./scripts/provisionar_cliente.sh granja-perez "Ganadería Pérez"
```

El script crea la app en Fly.io, su volumen persistente (1GB, se puede ampliar
después con `fly volumes extend`), genera una `SECRET_KEY` propia, configura
los secrets básicos y despliega. Al terminar, el cliente entra en
`https://<slug-app>.fly.dev` y crea su propio usuario administrador (primera
pantalla, `/auth/setup` — no requiere que tú crees nada a mano en su base de
datos).

El slug se añade automáticamente a `scripts/clientes.txt` para que quede
incluido en los despliegues masivos.

### Datos propios de cada cliente

- **Nombre de la explotación** (`EXPLOTACION_NOMBRE`): se pasa al provisionar.
  Para cambiarlo después: `fly secrets set EXPLOTACION_NOMBRE="..." --app <slug>`.
- **Datos fiscales / cuaderno de explotación** (razón social, NIF, nº registro,
  dirección...): los rellena el propio cliente dentro de la app, en
  Cuaderno de explotación → Configuración. No hace falta tocar nada en Fly.
- **Telegram**: el bot es el mismo para todos los clientes (un solo
  `TELEGRAM_BOT_TOKEN`, no hace falta crear uno nuevo por cliente). Cada
  cliente solo necesita darte su `chat_id` (lo consigue escribiendo a
  `@userinfobot` en Telegram) para que le lleguen sus propias alertas:
  ```bash
  fly secrets set TELEGRAM_CHAT_ID=xxxxxxx --app <slug>
  ```
- **Email de confirmación de reservas** (módulo Agroturismo, opcional): sin
  configurar, la reserva se guarda igual pero no se envía correo al
  visitante (solo el aviso por Telegram al titular). Para activarlo:
  ```bash
  fly secrets set SMTP_HOST=smtp.ejemplo.com SMTP_PORT=587 \
    SMTP_USER=usuario SMTP_PASSWORD=xxxxx SMTP_FROM="reservas@..." \
    --app <slug>
  ```

## Elegir módulos por instalación

Por defecto un cliente nuevo lleva todos los módulos. Si solo necesita una
parte (p.ej. una explotación de carne que no hace queso), se pueden
seleccionar de antemano con `--modulos`:

```bash
./scripts/provisionar_cliente.sh granja-lopez "Ganadería López" \
  --modulos=maquinaria,alimentacion,economia,cuaderno
```

Módulos opcionales disponibles: `queseria` (incluye trazabilidad),
`analisis_leche`, `maquinaria`, `alimentacion`, `economia` (incluye
presupuesto), `cuaderno` (incluye exportaciones SITRAN/ARCA/censo),
`agroturismo` (actividades, alojamientos y reservas con control de aforo),
`facturacion` (clientes, facturas con numeración correlativa, PDF y
encadenado con huella entre facturas emitidas — ver aviso sobre VERI*FACTU
más abajo), `rentabilidad` (panel de ingresos/gastos/margen por año y por
animal — combina Economía, Quesería y Facturación; funciona con datos
parciales si alguno de esos módulos no está activo, pero da su mejor
resultado con `economia` activado), `bienestar` (auditorías de bienestar
animal con checklist por alimentación/alojamiento/salud/comportamiento,
puntuación 0-10 por indicador, acciones correctoras con fecha límite y
aviso automático si una acción queda vencida sin resolver), `documentos`
(certificados ecológicos, inspecciones, contratos, seguros y licencias con
archivo adjunto opcional — PDF, imagen, Word o Excel — y aviso automático
antes de que caduquen, configurable con `ALERTA_DOCUMENTO_DIAS`, por
defecto 60/30/15/7 días).

El núcleo — Animales, Reproducción, Sanidad, Lotes/Parcelas, Tareas — está
siempre incluido, no es seleccionable.

Los módulos no incluidos ni aparecen en el menú ni responden por URL (dan
404), así que no hay manera de acceder a ellos por accidente.

Para cambiar los módulos de un cliente ya existente:

```bash
fly secrets set MODULOS=maquinaria,alimentacion,economia,cuaderno --app <slug>
```

### ⚠️ Facturación y VERI*FACTU

El módulo `facturacion` genera facturas reales (numeración correlativa,
PDF, datos fiscales) con un encadenado de huellas (hash) entre facturas
emitidas para detectar alteraciones a posteriori. Eso cubre la parte de
"no alterable / trazable" del Reglamento VERI*FACTU, pero **no implementa
el resto**: no genera el código QR con el formato que exige la AEAT ni
envía las facturas en tiempo real (modalidad VERI*FACTU) ni genera el
registro de facturación firmado (modalidad no verificable completa).

Antes de activar este módulo para un cliente real que vaya a usarlo para
facturar de verdad a sus clientes, hay que cerrar esa pieza (o confirmar
con el cliente que asume la limitación mientras tanto). No lo actives sin
hablarlo antes con el cliente.

(el redeploy que dispara `fly secrets set` ya aplica el cambio; no hace
falta hacer nada más — las tablas de los módulos desactivados simplemente
dejan de usarse, no se borran, así que si se reactiva un módulo más adelante
los datos que ya hubiera siguen ahí).

## Instancia de demostración

Para enseñar la app a un cliente potencial sin usar datos reales de nadie:

```bash
./scripts/provisionar_cliente.sh granja-demo "Explotación Demo" --demo
```

El flag `--demo` hace tres cosas de más respecto a un cliente normal:
- Activa `DEMO_MODE=true`, que enciende un aviso morado en toda la app
  ("Estás en la demo...") y programa un reinicio automático cada noche a
  las 04:00 (hora España).
- Siembra la base de datos con una explotación ficticia completa (animales,
  lotes y parcelas con uso, sanidad con ejemplos de "todo el rebaño" y "por
  lote", maquinaria con revisiones, un análisis de leche, lotes de queso,
  economía y tareas) — para que un visitante vea la app ya poblada, no vacía.
- Crea un usuario fijo `demo` / `demo1234` para que cualquiera pueda entrar
  sin tener que registrarse.

Si en algún momento quieres reiniciarla a mano (sin esperar a las 04:00):

```bash
fly ssh console --app granja-demo -C "python services/demo_seed.py"
```

`desplegar_todos.sh` también actualiza la demo si la añades a
`scripts/clientes.txt` (el script de aprovisionamiento ya lo hace solo).

## Publicar una actualización a todos los clientes

```bash
./scripts/desplegar_todos.sh
```

Recorre `scripts/clientes.txt` y hace `fly deploy` en cada app con el código
actual. Al final indica si algún despliegue falló, para poder reintentarlo
solo en esa app:

```bash
fly deploy --app <slug> --ha=false
```

## Baja de un cliente

```bash
fly apps destroy <slug-app>
```

Esto borra la app **y su volumen** (los datos del cliente desaparecen). Si
hay que conservar los datos, primero:

```bash
fly volumes snapshots list --app <slug-app>
```

y descargar o conservar el snapshot antes de destruir la app.

## Copias de seguridad

Fly.io hace snapshots automáticos diarios de cada volumen (retención por
defecto 5 días, configurable). No sustituye a una copia propia si el negocio
crece — de momento es suficiente para 2-5 clientes piloto.

## Limitaciones actuales (a propósito, dado el volumen de clientes)

- **Sin panel central**: para ver el estado de todos los clientes hay que
  mirarlos uno a uno (`fly status --app <slug>`) o en el dashboard de Fly.io.
- **Sin facturación integrada**: se factura fuera de la app.
- **Cada actualización de código hay que desplegarla a cada cliente**
  (`desplegar_todos.sh` lo automatiza, pero no es instantáneo ni atómico —
  si falla a mitad, ese cliente se queda en la versión anterior hasta
  reintentar).

Si el número de clientes crece de forma relevante (más de ~10, o aparece
necesidad de panel/self-service/facturación automática), este es el punto en
el que compensa migrar a una arquitectura multi-inquilino real (una sola app,
base de datos compartida con aislamiento por `tenant_id`) — es un cambio de
arquitectura serio, no una ampliación incremental de este runbook.
