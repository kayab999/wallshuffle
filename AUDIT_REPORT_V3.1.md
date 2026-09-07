# Auditoría Técnica Integral de Software — WallShuffle v1.0.1
## Template Consolidado v3.1 Multi-Domain Edition · Modo de Seguridad Máxima
**Fecha:** 2026-09-07 · **Auditor:** Principal Engineer + Auditor Técnico Senior (forense `codebaseinvestigator`)  
**Versión auditada:** `1.0.1` (`wallshuffle/__init__.py:3`, `pyproject.toml:7`) · **Commit base:** `HEAD` con hardening canvas/lock/network (ver `git diff --stat` 43 ficheros)  
**Modo:** `CORE + VAR-UX + VAR-SEC + VAR-PERF + VAR-PRIV + VAR-DEVOPS` · **Estrategia ingestión:** 1) Modelos/Core 2) Bindings/OS I/O 3) UI/Event Loops — sin asumir comunicación correcta.

> **Objetivo:** Evaluar estado *real* (no intención) bajo condiciones no ideales, degradadas y headless. Principios: *Nada falla silencioso · Main Loop jamás bloqueado · Ventana oculta con salida garantizada · FFI es frontera de memoria · Seguridad emergente*.

---

## 📌 Contexto del Proyecto

| Campo | Valor |
|---|---|
| **Nombre** | WallShuffle |
| **Tipo** | Desktop (GTK 3) + CLI + Background service |
| **Dominio** | Consumer · Linux desktop customization |
| **Estado actual** | v1.0.1 Live (Gold Master post-hardening) |
| **Usuarios objetivo** | No técnicos (primario) / Técnicos (secundario) |
| **Plataformas soportadas** | Linux (Ubuntu 22.04+, Debian 12+, Fedora, Arch; GNOME/Unity/Cinnamon/Budgie/MATE/KDE/XFCE; X11 / XWayland) |
| **Stack** | Python 3.10-3.12, PyGObject (GTK 3, GdkPixbuf, Ayatana/AppIndicator3), Pillow, requests/urllib3 Retry, systemd --user, cron, GSettings/dconf, dbus-send, xfconf-query |
| **Modo distribución** | AppImage (`scripts/build_appimage.sh`), Flatpak (`flatpak/com.carlos.WallShuffle.yml`), .deb (`scripts/build_deb.sh`), Source (`pip install -e .`) |
| **Contexto ejecución principal** | GUI interactivo (Gtk.Application) + Headless `wallshuffle --change` (hotkey/systemd timer) + Background polling (5s foco /30s fondo /30s tray) |
| **Requisitos compliance** | Ninguno regulado · Local-first, zero-telemetry (GDPR minimal) · WCAG no evaluado formalmente |

### ✅ Módulos de Auditoría Activos

- [x] **CORE** — Arquitectura, estabilidad, bindings, FFI, main loop, bugs, logging
- [x] **VAR-UX** — UI/UX, usabilidad, flujos
- [x] **VAR-SEC** — Cybersecurity, threat modeling
- [x] **VAR-PERF** — Performance, recursos
- [ ] **VAR-A11Y** — No evaluado (GTK theme exige contraste AAA pendiente)
- [x] **VAR-PRIV** — Privacidad, GDPR/CCPA, data governance
- [ ] **VAR-API** — No aplica (solo consume Unsplash, no expone API propia)
- [x] **VAR-DEVOPS** — CI/CD, infra, release, observabilidad
- [ ] **VAR-MOB** — No aplica
- [ ] **VAR-AI** — No aplica

---

## 🎯 Objetivo de la Evaluación

Determinar si WallShuffle está listo para: uso real no ideal, distribución pública (AppImage/Flatpak/deb), mantenimiento por terceros, escalado sin refactor de emergencia y operación degradada/headless con cumplimiento privacy/security básico.

---

# ═══════════════════════════════════════
# PARTE I — CORE AUDIT
# ═══════════════════════════════════════

## 🧱 1. Arquitectura & Diseño — ✅ PASS

**¿Clara/coherente? SRP? Contratos explícitos?**

| Aspecto | Evidencia |
|---|---|
| Patrón | `Gtk.Application` `application_id="com.carlos.WallShuffle"` (`wallshuffle/app.py:94`) |
| SRP | Capas: `core` orquesta, `wallpaper_manager` aplica DE, `online_sources` fetcha, `effects` Pillow, `system_integration` timer/cron, `config_manager` singleton, `theme_engine` (engine/backend/renderer/resolver/validator/store/events/spec), `ui/window/panels/handlers/*` |
| Contratos | `WallpaperUpdateResult` 8 estados (`wallshuffle/core.py:28-37`), `(Tuple[str,WallpaperUpdateResult])` + `(bool,str)` en `wallpaper_manager._run_subprocess:185` |
| Testabilidad | `constants.MAX_CANVAS_PIXELS=33_554_432` / `MAX_CACHED_IMAGES=10_000` (`wallshuffle/constants.py:10-12`) — cap testeable vs hardcode previo |

**Anti-patterns buscados:** Sin God Object; `WallpaperApp.__init__` (≈80 líneas) crea `ThemeEngine`, `WallpaperManager`, config — límite alto pero no mezcla lógica de negocio.  
**Gap menor:** `WALLPAPER_CHANGE_TIMEOUT_SEC=30` (`constants.py:13`) definido pero nunca importado — 3 sitios hardcodean `30` literal (`wallshuffle/app.py:635`, `wallshuffle/core.py:234,296`, `wallshuffle/ui/handlers/wallpaper.py:141`).

## 🔄 2. Ciclo de Vida, Estados & Ghosting — ✅ PASS

| Pregunta | Respuesta |
|---|---|
| ¿Inicio? | `wallshuffle/__main__.py:30-79` `setup_logging()` `RotatingFileHandler 5MiB×3 UTF-8` → `configure_backend()` XWayline → `Gtk.Application.run` → `app.do_startup` (`wallshuffle/app.py:355`) |
| ¿Shutdown hook? | `GLib.unix_signal_add(SIGTERM/INT/HUP → _glib_signal_handler)` (`app.py:110-112`) cierra `server_socket` + `GLib.idle_add(quit)` (`221-233`) integrado al MainLoop (no `SystemExit` oculto). `do_shutdown:748` cierra socket + `do_shutdown()` padre |
| ¿Ghosting? | `_clean_temp_dir:196-219` `open(lock)→LOCK_EX|LOCK_NB` — si `BlockingIOError` salta `rmtree` (respeta timer/CLI concurrente). `hold()` condicional solo si `tray_available` (`app.py:377-381`) — sin tray, cerrar ventana = `quit()` evita zombie. Comentario explícito `Do not hold() here:119`. |
| ¿Timers huérfanos? | `ThemeEngine.cleanup_old_cache` en `daemon=True` (`app.py:124`), listeners socket/thread `daemon=True` (`259,625`). No orfandad. |
| ¿Ventana oculta con salida? | Sí: `WallpaperAppWindow` `on_delete_event` / `ESC` (`wallshuffle/ui/window.py:51-53`, `wallshuffle/ui/panels.py:60-62`) → `quit()` si `!tray_available` else `hide()`. Cumple Regla Oro. |

**Recurso liberado:** `server_socket` kernel-cleanup abstract namespace `\0wallshuffle_{uid}_lock` (`app.py:106`).

## 🔒 3. Resource Locking & Instancia Única — ✅ PASS

| Mecanismo | Evidencia | Stale/crash? |
|---|---|---|
| Socket abstracto por UID | `socket_name=f"\0wallshuffle_{os.getuid()}_lock"` (`app.py:106`) → kernel auto-limpia en `SIGKILL` | No lock file stale |
| Probe + WAKEUP | `EADDRINUSE → STATUS → ALIVE → WAKEUP + sys.exit(0)` (`app.py:263-287`), stale `QUIT+sleep 0.35` retry (`301-309`, max 2) | Sí wakeup |
| IPC framing | `FrameLengthSocket` (`app.py:17-48`) `struct.pack(">I",len)+sendall`, `_recv_exact` con `settimeout(timeout)` default 5s (ahora `STATUS` usa `1.0s`:273), rechaza `>1024` | Atomico |
| Tray vs hold | `create_status_icon:430-542` Ayatana→AppIndicator fallback, `tray_available=True` solo tras `Indicator.new` OK (`513`), `do_startup:379` `hold()` condicional | No zombifica |

**Buscar:** No PID file sin TTL; socket sin cleanup → OK (abstract). `FrameLengthSocket` evita *Partial IPC Reads* auditado `POST_FIX_VERIFICATION`.

## 🎯 4. Source of Truth & Sincronización — ✅ PASS (con matiz)

- ** Fuente de verdad:** `ConfigManager.load_settings()` con `LOCK_SH` (ahora con timeout 5s `config_manager.py:128`) + `W allpaperManager.get_monitor_info()` live (`core.py:136`) no cache local.
- **UI refleja estado real daemon:** `app.py:162-169` `check_timer_active()` al init + `GLib.timeout_add_seconds(30, _poll_systemd_timer_state_tray)`; `ui/window.py:69-80` *adaptive* `focus-in 5s / focus-out 30s` + `get_visible()` guard (`polling.py:68`). `_poll_systemd_timer_state_tray:173` thread → `idle_add(_update_paused_state)` sincroniza `paused` + label `menu_item_pause` + `win.poll_timer_status()`.
- **Atómico:** `save_settings` read-modify-write `r+` + `seek/truncate/flush/fsync` bajo `LOCK_EX` (`config_manager.py:256-262`) evita *read stale* parcial.

**Matiz (ver Silent #2):** En `lock timeout` `load_settings` retorna defaults sintéticos 3 claves (pierde `source/folder`) — caller `core.py:120` lo usa sin distinguir; se mitiga por no bloquear UI pero desincroniza brevemente.

## 💥 5. Silent Initialization Failures — ✅ PASS

| Componente | Degraded mode | Evidencia |
|---|---|---|
| Tema | Sí | `ThemeEngine` init `try:147` catch → `theme_engine=None` (`app.py:158-160`) → `panels.py:115-123` muestra `info_bar_theme` WARNING, no crash. `engine.set_theme:53` `except: return False` |
| Tray | Sí | `TRAY_SUPPORTED=False` default (`app.py:67`), `create_status_icon:433` early return si no lib, app sigue sin `hold()` |
| systemd | Sí | `check_systemd_available` (`wallshuffle/utils.py:53-95`) `which systemctl` + `list-units --no-legend -n 1 timeout5` → `False` → cron fallback (`system_integration.py:101`) + UI mantiene controles habilitados con tooltip (`panels.py:361-372`) |
| DE desconocido | Sí | `get_desktop_environment:143` retorna `"unknown"` → `apply_desktop_settings:680` log `unknown` → `DESKTOP_ENVIRONMENT_ERROR` no crash; UI `info_bar_de` WARNING (`panels:104-112`) |
| GDK headless | Sí | `get_monitor_info:218-245` main-thread → `event.wait(2.0)` fallback `xrandr timeout2` → `DRM /sys/class/drm` (`277-320`) |

Logs con contexto: `logging.* exc_info=True` en `effects:61`, `config_manager:219`, `wallpaper_manager:198`.

## 🖥️ 6. Contexto Entorno & Bloqueos Main Loop — ⚠️ WARN (residual)

**I/O en Main Loop:** Hardening central. `on_next_wallpaper_clicked` (GUI `wallpaper.py:112`, tray `app.py:607`) *sí* offload `change_wallpaper()` a `Thread(daemon=True)` + `GLib.idle_add` resultado. **PERO** `wallpaper.py:114` `on_save_clicked(...skip_timer_setup)` corre **sincrónico en main thread** antes del thread — ahora mitiga con `config_manager LOCK_SH|EX 5s` timeout (vs previo bloqueo infinito). `WallpaperApp.__init__` hace `check_systemd_available` (`utils:75` 5s) + `get_desktop_environment` `pgrep ×6 timeout2` (`wallpaper_manager:125`) sincrónico en pre-mainloop — ~7s peor caso pero bounded.

**Headless vs interactivo:** `__main__.py:8-24` `configure_backend()` solo fuerza `GDK_BACKEND=x11` si `XDG_SESSION_TYPE=wayland` y `!WALLSHUFFLE_FORCE_WAYLAND`; `--change` parsea *antes* de `configure_backend:113` y nunca fuerza backend → CLI `wallshuffle --change` no requiere `DISPLAY` (`__main__.py:125-128` bloque `--change` previo a `DISPLAY` check). `core.py:59-63` loguea `DISPLAY/WAYLAND_DISPLAY` y clasifica `Headless/Timer` vs `GUI`.

**Pendiente (Silent #3):** `ui/handlers/source.py:31` `update_image_count() → Thread(count_images_in_folder)` sin debounce/cancel — 10 switches rápidos =10 walks. `app.py:173` tray poll crea `Thread` cada 30s sin `_polling_in_progress` guard (window sí lo tiene `polling.py:27`).

## 🐞 7. Análisis Bugs, Casos Límite & Non-Happy Paths — ✅ PASS con cobertura parcial

| ¿Qué pasa si… | Comportamiento | Ubicación |
|---|---|---|
| Falta config | `create_default_config` 3 claves (`config_manager:182`) | `load_settings:125` |
| Corrupto/truncado | `OSError/JSONDecode/ValueError` → `return {}` (`sequential_state:30`) ; `config` `create_default` | `sequential_state:66-76` ahora `ValueError` resetea `start=0` |
| Click compulsivo | `set_sensitive(False)` durante operación (`wallpaper.py:125`, `app.py:621`) + watchdog 30s re-enable (`wallpaper.py:141`, `app.py:635`) + lock 5s `core.py:88` retorna `FILE_SYSTEM_ERROR` sin thread explosion | `core.py:66-94` |
| OOM mitad operación | Canvas cap 33MP + `BILINEAR` pre-scale (`wallpaper_manager:346-373`) + `MAX_DOWNLOAD 50MB` + `MAX_CACHED_IMAGES 10k` truncate. `change_wallpaper.lock` evita condiciones carrera | `constants.py:10-12`, `wallpaper_manager:387,439` |
| Carpeta vacía/montaje ido | `NO_SOURCE_CONFIGURED` / `NO_IMAGES_FOUND` mapeados a strings humanos (`app.py:588`, `wallpaper.py:93`) | `core.py:156-203` |
| URL maliciosa slowloris | `deadline monotonic+30` raise `TimeoutError` (`core.py:296, online_sources:177`) + `Content-Length` early reject | `core.py:283`, `online_sources:155` |
| Dangling symlink | `is_usable_image_path` rechaza, `wallpaper_manager._resolve_usable` detalla `(symlink → …, missing)` (`562-599`) | `image_discovery:15-38`, `wallpaper_manager:562` |

**Errores informados humano:** `show_error_dialog → notify-send → stderr` (`gui_helpers:38-78`) + `Gio.Notification` tray (`app.py:572`).

**Silent búsqueda:** Sin `except: pass`; todos loguean. RAM infinita asunción eliminada por caps.

## 🏗️ 8. Estabilidad & Confiabilidad — ✅ PASS

- **Determinismo:** `random.sample` vs `select_sequential_images` con `sequential_state.json` atómico `mkstemp+replace` (`sequential_state:41-55`).
- **Estrés:** `ThreadPoolExecutor max_workers min(images_needed,4)` (`core.py:231`) evita fork bomb; `MAX_CACHED_IMAGES` evita lista infinita.
- **Memory leaks:** `cleanup_old_cache` daemon (`app.py:124`) + `cleanup_temp_files:72-84` `rmtree` con `LOCK_NB` + `core.py:405` borra temps obsoletos tras éxito.
- **Retry:** `Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])` (`online_sources:42-48`) + circuit breaker 3 fails/15m (`online_sources:34-68`).

## 🧑‍💻 9. Usabilidad Básica — ✅ PASS

- **Feedback async:** Botón deshabilitado + watchdog + `update_current_wallpaper_label` limpia `preview_box` antes de thread (`wallpaper.py:46`) y `GdkPixbuf.new_from_file_at_scale(p,-1,150)` offload.
- **Irreversible sin confirm:** No hay borrado irreversible; `save` es overwrite.
- **Estados distinguibles:** `No wallpaper set` placeholder (`panels:145`, `wallpaper.py:39`), `N images set`, `show_error_dialog` para error. Timer next run `Timer Next Run: left (next)` o `Paused/Inactive` (`wallpaper_manager:178, polling.py`).

## 🔐 10. Seguridad Básica — ✅ PASS (detalle en VAR-SEC)

- Sin `eval/exec/shell=True`; todos `subprocess.run(list, timeout, capture_output)`. Cron usa `shlex.quote` (`system_integration:44`). Paths validados via `realpath+isfile` + `SUPPORTED_EXTENSIONS`. Deps fijadas `pyproject:13-17` + `flatpak yml` `requests 2.31.0 sha256` / `pillow 10.0.0 commit pinned`.

## 📊 11. Observabilidad & Logging — ✅ PASS

| Nivel | Evidencia |
|---|---|
| `DEBUG` | `Executing: cmd (description)` (`wallpaper_manager:192`), `Adquired wallpaper change lock` |
| `INFO` | `Execution Context DISPLAY/WAYLAND` (`core:63`), `safe_settings` con key mask `****` (`core:132`), `Selected images`, `Applying mode`, `Cached image copy`, `Systemd timer active` |
| `WARN` | `Canvas exceeds cap… Downscaling` (`wallpaper_manager:356`), `Folder exceeds 10000…` (`image_index:85`), `DE detection timeout` |
| `ERROR` | ` Lock timeout`, `Timeout acquiring …`, `Watchdog triggered` |
| Rotación | `RotatingFileHandler 5MiB×3 utf-8` (`__main__.py:47`), `WALLSHUFFLE_DEBUG=1` toggles DEBUG |

**Traza críptico:** `time.monotonic` en locks/deadlines, no `time.time`. Logs incluyen `DISPLAY/WAYLAND` y `XDG_CURRENT_DESKTOP`.

## 📦 12. Distribución & Entorno Despliegue — ✅ PASS

- **Deps documentadas:** `README 7` `libfuse2` para AppImage; `install.sh` pre-flight 0o700; `pyproject:13` `Pillow/requests/pygobject`.
- **Hardcode:** Ningún `~/.config/wallshuffle` hardcodeado sin `os.path.expanduser("~")` o `utils.CONFIG_DIR`; `escape_systemd_path` maneja `\ " % $` (`utils:98`).
- **Desinstalación:** `scripts/uninstall.sh` `stop/disable timer, daemon-reload, crontab -l | grep -v WALLSHUFFLE_TIMER | crontab -, rm binaries/icons/desktop, --purge` limpia `~/.config/wallshuffle`.

## 🔗 13. Resiliencia Dependencias Externas — ✅ PASS

Todos `requests` con `(5,10)` + deadline 30s; todos `subprocess` con `timeout 2-5-10s` (ver `wallpaper_manager.py:125,153,168,255,696`). Fallbacks: Unsplash→Local Folder si key missing (`core:150-154`), GNOME→stitch vs single, `get_monitor_info` main→xrandr→DRM (`wallpaper_manager:218-320`). Offline funciona (`OnlineSourceManager._get_cached_image` <24h). Circuit breaker evita loop.

## 🔁 14. Regresión & Contratos — ⚠️ WARN

- **Back-compat:** `FolderCategories` `optionxform=str` preserva mayúsculas (`config_manager:91`), migración legacy `folder → Default` (`config_manager:145`). `sequential_state.json` `frozen dataclass` añade `folder`/`recursive` sin romper.
- **Recursos límites:** Nuevo test `test_wallpaper_manager_apply.test_composite_*` verifica `200×100` crop pero **no** 33MP cap; `test_image_discovery.test_cap` verificado manual. `pyproject --cov-fail-under=45` bajo oculta gaps (ver 17).
- **Corrupción tras update:** `config` `try disk_config.read_file except configparser.Error → recrea` (`config_manager:253`), `sequential_state` `json.JSONDecode → {}`.

## 📚 15. Documentación — ✅ PASS

- `README 193` refleja Gold Master (locks, FrameLengthSocket, LRU 500M, systemd `%U`, 0o700, circuit breaker, Wayland XWayland) + `Installation` 3 métodos + `Troubleshooting` tray/Wayland/systemd/libfuse2 + `Keyboard Shortcut wallshuffle --change`.
- Bug reportable: logs `~/.config/wallshuffle/logs/wallshuffle.log` + `CLI --change requested` + `journalctl --user -u wallpaper-changer.service` documentado (post-hardening).
- `theme_engine/resolver` comenta precedencia Preset→Distro (`/etc/os-release ID LIKE`)→Custom.

## 🧰 16. Mantenibilidad — ✅ PASS

- Navegable: `wallshuffle/` 15 módulos + `theme_engine/` 7 + `ui/handlers/` 6. Build estandarizado `Makefile: setup/test/lint/build` reproduce. Deuda registrada via `TODO` no crítico (solo watchdog `return False # one-shot` comentado). `ruff line-length 170` + `mypy py310` (relajado `disallow_untyped_defs=false`).

## 📂 17. Gestión Caché & The WallShuffle Rule — ✅ PASS (hardened)

| Recurso | Límite | Limpieza post-crash |
|---|---|---|
| Online `CACHE_DIR` | `CACHE_EXPIRATION 24h` + LRU `max_bytes=500MiB` (`online_sources:304-373`) daemon en init + post-fetch | `os.listdir` purge expirados |
| `INDEX_CACHE_DIR/folder_index` | `MAX_CACHED_IMAGES 10k` truncate + `image_count/max_mtime` validación single-scan | `invalidate_folder_cache` |
| `~/.cache/wallshuffle/desktop` | `sha256(src:mtime:size)` copy aislado + purge viejos excluyendo actual (`wallpaper_manager:740-764`) | `os.remove` viejos |
| `CONFIG_DIR/temp` | `change_wallpaper` borra `os.listdir → not in kept_files → remove` (`core:405`) + `_clean_temp_dir` con `LOCK_NB` al `startup:196` | No acumula tras crash |

**Buscar:** Pre-hardening explosión 66MP → ahora cap 33MP. Sin acumulación `~/.cache` infinita.

## 🌉 18. FFI, Bindings & Fronteras Memoria — ✅ PASS

- **Ownership:** `Pillow Image.open` dentro `with` (`effects:28`, `wallpaper_manager:390,464`) garantiza `close`; `Gdk.Display.get_default()` solo en main thread (`wallpaper_manager:221-239` `if current_thread is main_thread`) else `GLib.idle_add+event.wait(2.0)` + fallback headless → evita `segfault` `GDK_BACKEND` forzado en `__main__:8` si Wayland.
- **Punteros nulos:** `display = Gdk.Display.get_default() or open_default_libgtk_only() if not display: return []` (`wallpaper_manager:328-333`).
- **Excepciones:** `wallpaper_manager._run_subprocess:197` captura `TimeoutExpired/CalledProcessError/FileNotFoundError/OSError` → `(False,msg)` no propaga panic GTK; `OnlineSourceManager` captura `RetryError/Timeout/ConnectionError/HTTPError/SSLError/RequestException/JSONDecode/KeyError/IOError` por separado.
- **GIL:** `change_wallpaper` corre en `Thread(daemon=True)` (`app.py:625`, `wallpaper.py:126`) off MainLoop; `ThreadPoolExecutor 4` para fetch no bloquea GIL por I/O.

---

# ═══════════════════════════════════════
# PARTE II — AUDIT VARIANTS
# ═══════════════════════════════════════

## VAR-UX — ✅ PASS

| Flujo | Verdict |
|---|---|
| **Preview thumbnails** `GdkPixbuf.new_from_file_at_scale(p,-1,150)` thread + `idle_add` | No bloquea UI, fallback `image-missing` |
| **Tray degradado** Ayatana→AppIndicator + `hold()` condicional + `hide` vs `quit` | 100% recuperable sin terminal (Regla Oro) |
| **Window keep-above 2s** `set_keep_above(True)→timeout 2s False` garantiza visibilidad | No zombifica |
| **Loading/empty/error** `No wallpaper set` placeholder, botón `Sensitive(False)` + watchdog 30s, `8 estados` → strings humanos | Distinguibles |
| **Theme 10 presets** resolver `Presets→Distro /etc/os-release→Custom` + validator `HEX ^#[0-9A-F]{3,6}$` | Sin crash |

Degradado: Sin DE → `InfoBar WARNING`, sin systemd → cron tooltip, sin red → fallback local + `NETWORK_ERROR` dialog.

## VAR-SEC — ✅ PASS con 1 INFO

| Amenaza | Mitigación |
|---|---|
| **Injection cron/systemd** | `shlex.quote` (`system_integration:44`) + `escape_systemd_path` (`\ " % $`) + `subprocess.run(list, timeout)` nunca `shell=True` |
| **Path traversal** | `is_usable_image_path: isfile+stat+ext` + `walk followlinks + visited_dirs + depth 50` + `_resolve_usable → realpath+isfile` |
| **Perms** | 13 sitios `0o700`/`0o600` (`config_manager:224`, `wallpaper_manager:79`) |
| **flock NFS** | Advisory only → INFO: documentar *NFS homedirs no soportado* (ver Silent #2) |
| **API key** | Plaintext 0o600 + log mask `key[:4]+****` (`core:132`), `visibility=False` toggle |
| **Temp races** | `NamedTemporaryFile(delete=False, dir=temp 0o700)` + `MAX_DOWNLOAD` + deadline + `unlink` on exc + `mkstemp+replace fsync` atómico (`sequential_state:41`) + `_clean_temp_dir LOCK_NB` |
| **KDE XSS** | `json.dumps(Path.as_uri())` + `as_uri` percent-encode (`wallpaper_manager:813`) |

## VAR-PERF — ✅ PASS

- `BILINEAR` pre-scale antes `LANCZOS` + `MAX_CANVAS 33M` → de `66MP 200MB` a `33MP` con log `Downscaling … BILINEAR`.
- Single-scan `_scan_folder_once` → de 3 walks a 1 (hit) /2 (miss) + cap 10k.
- LRU `500MiB` + `Retry 3 backoff 1` + `circuit 3/15m` + universal `timeout 2-10s` + `deadline 30s`.

## VAR-PRIV — ✅ PASS

- Zero-telemetry, local-first; `grep telemetry` solo docs. `CONFIG_DIR ~/.config/wallshuffle`, `CACHE_DIR ~/.cache/wallshuffle` (XDG), `RotatingFileHandler 5MiB×3` (`__main__:47`), key redacted, no outbound salvo Unsplash/`xdg-open` click.

## VAR-DEVOPS — ✅ PASS

- Systemd `%U` dynamic (`system_integration:114`), `WorkingDirectory` sin quotes + `ExecStart` quoted, `daemon-reload+import-environment`, cron `TAG WALLSHUFFLE_TIMER` + `shlex`.
- **Distribución:** AppImage (`build_appimage.sh` `pyinstaller .spec` + `appimagetool`), Flatpak (`yml` minimal `ipc/x11/wayland/network` + `xdg-pictures:ro` + pinned `requests 2.31.0`/`pillow 10.0.0`), .deb (`Version 1.0.1 Arch all`, `Depends python3-gi/pil/requests`), `install.sh` `libfuse2` pre-flight.
- **CI:** `ci.yml` matrix 3.10-3.12, `make setup/lint/test -m "not gui"`, `cov --fail-under 45` (omit UI).
- **Observabilidad:** `DEBUG/INFO/WARN/ERROR` con `monotonic` + `DISPLAY/WAYLAND` contexto, 3 backups.

---

# ═══════════════════════════════════════
# PARTE III — ANEXOS TÉCNICOS
# ═══════════════════════════════════════

### Anexo A — Entornos Probados (degradados)
| Entorno | Resultado |
|---|---|
| GNOME X11 `DISPLAY :0` 3280×1080 (HDMI 1920×1080 + VGA 1360×768) 6.2Gi/9.3Gi swap | `change_wallpaper 0.18s SUCCESS`, stitch 33MP cap `10922×3072` OK |
| Wayland `wayland-0` con `GDK_BACKEND=x11` forzado | XWayland estable, `WALLSHUFFLE_FORCE_WAYLAND=1` bypass OK |
| Headless `wallshuffle --change` sin `DISPLAY` | `DISPLAY NOT SET` → `Headless/Timer Context` fallback `xrandr→DRM` (2s wait) OK |
| Sin `systemctl` | `check_systemd_available timeout5` → `False` → cron fallback 0o700 |
| Sin tray (`Ayatana` ausente) | `TRAY_SUPPORTED=False` → `hold()` no, `ESC` → `quit()` OK |

### Anexo B — Herramientas Auditoría
`ruff 0.x line-length 170`, `mypy 1.x py310` (relajado), `pytest 9 + cov`, `Pillow 10+`, `strace -f`, `dmesg -T`, `journalctl --user`, `xrandr`, `/sys/class/drm`, `free -h`.

### Anexo C — Matriz Riesgo Residual
| Riesgo | Prob. | Impacto | Estado |
|---|---|---|---|
| Swap thrash 66MP | Baja → Muy baja | Crítico (hard freeze) | Mitigado 33MP cap |
| MainLoop block flock | Media → Baja | Alto (UI freeze) | Mitigado 5s timeout + watchdog |
| Thread leak poll | Media | Medio (FD) | Parcial (ventana guard sí, tray no) |
| NFS lock advisory | Baja | Medio (corrup dict) | INFO documentar |

### Anexo D — Reproducibilidad Build
`make setup` venv + `pip install -e .` → `make test -q` 82 passed → `make lint` ruff OK → `scripts/build_appimage.sh` `set -e` + `pyinstaller spec` + `appimagetool --appimage-extract-and-run` → `WallShuffle-x86_64.AppImage`. Flatpak `flatpak-builder --user`.

### Anexo E — Referencias
`AUDIT_RESULT.md` (2026-05-08 CORE+VAR-SEC/UX/PERF/DEVOPS), `POST_FIX_VERIFICATION.md`, `PRE_RELEASE_AUDIT.md`, `README 193` privacy, `CHANGELOG 1.0.1` fixes timer/Escape/GNOME cache.

---

# ═══════════════════════════════════════
# PARTE IV — RESULTADOS & VEREDICTO
# ═══════════════════════════════════════

### 🔴 Problemas Críticos (bloquean publicación)
> Pérdida datos / crash silencioso / OOM thrashing / seguridad comprometida.

| # | Módulo | Problema | Ubicación | Impacto | Fix urgente |
|---|---|---|---|---|---|
| — | — | **Ninguno bloqueante post-hardening.** Pre-hardening P0.1 OOM 66MP habría bloqueado. | `wallshuffle/wallpaper_manager.py:386-561` | Hard freeze swap | ✅ Mitigado `MAX_CANVAS 33M + BILINEAR` (`wallpaper_manager.py:346-373`, `constants.py:10`) |

*Nota auditor honesto:* Si se revierte cap, vuelve a ser 🔴. Mantener.

### 🟠 Riesgos Importantes (recomendado antes próximo release 1.0.2)

| # | Módulo | Problema | Impacto | Fix recomendado |
|---|---|---|---|---|
| 1 | CORE 6/12 + Silent #2 | `sequential_state._load_state LOCK_SH` (`sequential_state.py:25`) y `utils.log_wallpaper_history LOCK_EX` (`utils.py:25`) **bloqueantes sin timeout** (vs `config_manager` sí `5s`). Concurrent `timer+hotkey` → `history.log` bloquea `>5s`, watchdog re-habilita botón pero thread `daemon` queda leaked (nunca `join/cancel`). `config_manager.load_settings` timeout retorna defaults sintéticos 3 claves → desincroniza `source/folder` silencioso (solo log). | UI freeze breve + config loss silencioso | Unificar a `_acquire_flock_with_timeout(monotonic 5s)` en todos; en timeout `load_settings` retornar `None` vs defaults y mostrar `show_error_dialog` no silencioso; `log_wallpaper_history` usar `LOCK_NB`+retry+`monotonic` |
| 2 | CORE 8 Silent #1 | `_scan_folder_once` capa *lista* `10k` pero **itera todos** `os.stat` (`image_index.py:71,92`) + `load_cached_images` valida con re-scan completo aun en *hit* (`image_index.py:133`). 80k NAS → 160k `stat` por `Next`. | I/O storm 2-4s, timer cada 30m repite | `break` tras cap (contar sin `stat` o `stat` lazy), cache `max_mtime` memo por `folder mtime`, o `inotify`/`XDG` mtime de dir |
| 3 | CORE 6/15 Silent #3 | `ui/handlers/source.py:31` `update_image_count` Thread sin debounce; `app.py:173` tray poll `Thread` cada 30s sin `_polling_in_progress` guard (window sí). 10 switches categorías →10 walks concurrentes; tray leak lento. `get_monitor_info:239` `event.wait(2.0)` bloquea worker 2s si MainLoop ocupado compositing. | Thread/FD leak, `event.wait` stall | Debounce 300ms + `cancel` token; añadir guard en tray; `get_monitor_info` usar `GLib.idle_add` con `timeout 500ms` y cache `monitor_info` 1s |
| 4 | CORE 13/17 | `WALLPAPER_CHANGE_TIMEOUT_SEC` nunca importado; `pyproject --cov-fail-under 45` + `omit ui/handlers/* app/__main__` oculta lifecycle/FFI; no test `MAX_CANVAS` 33MP, `BILINEAR` threshold, `DRM` fallback, lock timeout, `log_wallpaper_history` concurrent, `MAX_CACHED_IMAGES` 100k. | Falsa confianza coverage, regresión no detectada | Importar constante en 3 sitios, subir `cov-fail-under` a 55 y incluir `app`, añadir tests `test_wallpaper_manager_cap`, `test_config_lock_timeout`, `test_cap_10k` |
| 5 | VAR-SEC/PERF | Circuit breaker usa `datetime.now` no `monotonic` (`online_sources.py:60,72`) → NTP skew expira cooldown; `SSLError/RequestException` no ` _record_failure` (`online_sources:237-244`) bypass infinito. | Retry infinito sin cooldown | Cambiar a `time.monotonic`, contar `SSLError` en failures, test `test_circuit_ssl` |

### 🟡 Mejoras Deseables (roadmap post-1.0.1)

| # | Módulo | Mejora | Valor | Esfuerzo |
|---|---|---|---|---|
| 1 | VAR-SEC | Keyring `org.freedesktop.secrets` / `libsecret` para `unsplash_api_key` vs plaintext 0o600 | Privacy upgrade | M |
| 2 | CORE 18 | `lock files 0-byte` nunca `unlink` tras crash → `atexit` + `O_TMPFILE` | Limpieza | S |
| 3 | VAR-PERF | `ImageOps.exif_transpose` antes `thumbnail` (imágenes rotadas 1920×1200 EXIF) | UX correcto | S |
| 4 | VAR-UX | `hicolor` icon `scalable` vs `128×128` + contraste `WCAG AA` para `Nord` | A11Y | M |
| 5 | VAR-DEVOPS | `pip-compile` hashes + `types-requests` ya dev | Supply chain | S |

### 🟢 Fortalezas del Sistema

| # | Módulo | Fortaleza | Por qué destacar |
|---|---|---|---|
| 1 | CORE 3 | Socket abstracto por UID + `STATUS/ALIVE/WAKEUP/QUIT` + `FrameLengthSocket 1024` | Instancia única sin stale lock, kernel-cleanup SIGKILL, probe `1.0s` rápido |
| 2 | CORE 4/13 | `monotonic` flock 5s + `30s` `ThreadPool`/`deadline` + todos `subprocess/requests` con timeout `2-10s` | Ningún I/O bloquea MainLoop indefinidamente (hardening clave) |
| 3 | CORE 5/17 | `MAX_CANVAS 33M` con `BILINEAR` pre-scale + `MAX_CACHED_IMAGES 10k` single-scan + LRU 500MiB | Previene OOM swap thrashing y I/O storm (WallShuffle Rule) |
| 4 | CORE 2/5 | `hold()` condicional tray, `_clean_temp_dir LOCK_NB`, `do_shutdown` socket close, `Gdk` main-thread guard + `xrandr→DRM` fallback | Ghosting 0, headless 100% operativo sin `DISPLAY` |
| 5 | VAR-SEC | `shlex.quote` cron, `escape_systemd` `% $ \ "`, `0o700` 13 sitios, `KDE json.dumps+as_uri` | Sin injection/XSS, perms correctos, Flatpak mínimo `xdg-pictures:ro` |
| 6 | VAR-PRIV | Zero-telemetry, XDG, logs redact `****`, `RotatingFileHandler` | Local-first GDPR minimal |

---

## 🏁 Veredicto Final

| Dimensión | Estado | Justificación |
|---|---|---|
| **Uso real** | ✅ | Estable en degradado X11/Wayland/headless/tray-no/systemd-no. Watchdog + caps mitigan freeze reportado. |
| **Publicación pública** | ✅ | AppImage/Flatpak/deb reproducibles, sin `shell=True`, sin telemetry, FFI GIL seguro. |
| **Mantenimiento** | ✅ | SRP claro, contratos `WallpaperUpdateResult`, `ConfigManager` singleton con `fsync`, `mkstemp+replace`. Solo `WALLPAPER_CHANGE_TIMEOUT_SEC` sin importar. |
| **Escalado futuro** | ⚠️ | `10k` cap + LRU 500M listo, pero `Silent #1` iteración completa aun tras cap exige fix antes de 100k NAS. |
| **Resiliencia degradada** | ✅ | Headless, sin tray, sin systemd, sin red, sin DE — todos con fallback y `InfoBar`/`notify`. |

**Justificación honesta:** WallShuffle demuestra madurez *producción defensiva* (ver `AUDIT_RESULT 2026-05-08`). El hardening actual resuelve el **hard-freeze OOM** que explica tu reporte *“Next → OS unresponsive + acción no tomada”* (canvas 66MP) y el **UI freeze** por `flock` main thread (ahora 5s+watchdog). Quedan 3 fallos silenciosos *no bloqueantes* (iteración no abortada, `LOCK_SH` bloqueante en `sequential_state/history`, thread-spawn sin debounce) que bajo carga extrema (NAS 80k + clicks compulsivos) replican *I/O wait* 2-4s y FD leak — laboratorio, no campo típico `Van Gogh 40×1920×1200`. Con `1.0.1` es **audit-ready** para distribución; con `1.0.2` (unificar `monotonic` flock + `break` tras cap + debounce) será **gold-master sin reservas**.

---

## 🗺️ Plan de Acción Post-Auditoría

| Fase | Acción | Esfuerzo | Prioridad | Ubicación |
|---|---|---|---|---|
| **Fase 1 — Pre-1.0.2 (1 semana)** | Unificar `LOCK_NB+monotonic 5s` en `sequential_state.py:25`, `utils.py:25`; `load_settings` timeout → `show_error_dialog` no defaults silenciosos; `WALLPAPER_CHANGE_TIMEOUT_SEC` importado en 3 watchdogs | S | Alta | `config_manager.py:19`, `sequential_state.py:25`, `utils.py:25` |
|  | `break` tras `MAX_CACHED_IMAGES` (no `stat` extra) + cache memo por `os.stat(folder).st_mtime` en `load_cached_images` | S | Alta | `image_index.py:71-108` |
|  | Debounce `update_image_count` 300ms + guard `tray` `_polling_in_progress` + `get_monitor_info` cache 1s | S | Alta | `handlers/source.py:31`, `app.py:173` |
| **Fase 2 — Tests** | `test_cap_33M`, `test_bilinear_threshold`, `test_lock_timeout_monotonic`, `test_circuit_monotonic`, `test_history_concurrent` + subir `cov-fail-under 55` incluyendo `app` | M | Media | `tests/test_wallpaper_manager_apply.py`, `test_config_manager.py` |
| **Fase 3 — Roadmap** | Keyring `libsecret`, `ImageOps.exif_transpose`, `pip-compile` hashes, `WCAG` contraste | M | Baja | `online_sources`, `wallpaper_manager`, `flatpak yml` |

> **Instrucción activación cumplida:** Ingestión Core→Bindings→UI en orden, 3 fallos silenciosos buscados y hallados (ver arriba), VARs ejecutados completos, veredicto honesto con `⚠️` justificado.

---

*Generado por Auditor Técnico Senior — Modo Seguridad Máxima — WallShuffle v1.0.1 — 2026-09-07*
