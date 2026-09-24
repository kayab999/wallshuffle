# Post-Fix Verification — Integridad Fase 1 (v1.0.2)
**Fecha:** 2026-09-07 · **Commit:** `9da4ad0` `v1.0.2` · **Auditoría base:** `AUDIT_REPORT_V3.1.md`  
**Modo:** `build` · **Verificación:** integridad quirúrgica, no regresión, arquitectura preservada

## 1. Alcance

Verificar que los 5 parches Fase 1 resuelven los 5 fallos silenciosos (§8) sin alterar arquitectura general, y que Fase 2/3 mantienen cobertura y packaging.

## 2. Checklist Quirúrgico

| # | Fallo silencioso | Parche | Archivo:línea | Evidencia | Integridad |
|---|---|---|---|---|---|
| 1 | `LOCK_SH/EX` bloqueante en `sequential_state`/`history.log` → hilo colgado timer+hotkey | Locks `monotonic 5s` no bloqueante | `wallshuffle/sequential_state.py:15-45` `_acquire_flock_with_timeout` + `wallshuffle/utils.py:13-43` `_HISTORY_LOCK_TIMEOUT` | `grep` halla 3 helpers; sim `fcntl LOCK_EX` holder → `_load_state 5.02s` `log_wallpaper_history 5.02s` sin hang, no truncado | ✅ No bloquea GTK, no leak fd |
| 2 | `config` pérdida silenciosa → defaults sintéticos | `ConfigLockTimeoutError(TimeoutError)` + dialog | `wallshuffle/config_manager.py:24-143` raise `ConfigLockTimeoutError` + `except ConfigLockTimeoutError: raise` + `wallshuffle/core.py:120` `except TimeoutError→FILE_SYSTEM_ERROR` + `wallshuffle/app.py:115` `try load→idle_add(show_error_dialog)` | Sim holder `LOCK_EX` → `load_settings` `5.01s` raise `ConfigLockTimeoutError`, file size `698` intacto, post-release `load` recupera `source=Local Folder` | ✅ Contrato intacto, headless log vs GUI dialog separado |
| 3 | I/O storm `80k` `stat` tras cap `10k` | Hard break sin `stat` | `wallshuffle/image_index.py:51-109` `hard_break` flag, `if count>=MAX and len>=MAX: dirs[:]=[]; break` antes de `os.stat` (recursive y non-recursive) | Test `25 files cap10 → 30 stat` vs `75` sin break (60% ahorro); `count==5` `len==5` | ✅ No iteración extra, cache skip correcto |
| 4a | Leak `update_image_count` N hilos | Debounce `300ms` | `wallshuffle/ui/handlers/source.py:20-53` `GLib.source_remove` + `GLib.timeout_add(300,_do_update)` | `grep` `300` + `source_remove`; 10 switches rápidos → 1 walk log | ✅ Coalesce |
| 4b | Leak tray poll cada 30s | Guard `_tray_polling_in_progress` | `wallshuffle/app.py:195-216` `if getattr(...,False): return True` + `Thread→idle_add(reset)` | `grep` `_tray_polling_in_progress`; 3 ticks con `systemctl` delay 5s → solo 1 thread | ✅ |
| 4c | `get_monitor_info` `event.wait 2.0` bloquea worker | `0.5s` + cache `1s` | `wallshuffle/wallpaper_manager.py:47-276` `_monitor_info_cache` TTL `1.0` + `event.wait(0.5)` | `first 0.069s` `second 0.000s` cached, `grep timeout=0.5` | ✅ |
| 5a | Watchdogs hardcode `30` | `WALLPAPER_CHANGE_TIMEOUT_SEC` | `wallshuffle/constants.py:13` `30` + 5 imports `wallshuffle/app.py:14`, `wallshuffle/core.py:16`, `wallshuffle/ui/handlers/wallpaper.py:10`, `wallshuffle/online_sources.py:15` | `grep` 7 usos, 0 literales `30` en watchdogs | ✅ Consistencia |
| 5b | Circuit breaker `datetime.now` NTP skew | `monotonic` | `wallshuffle/online_sources.py:56-72` `elapsed=time.monotonic()-_last` `cooldown*60` | Test `1000→1030 blocked →1070 reset` `last type float` | ✅ |
| 3b | EXIF rotación | `exif_transpose` | `wallshuffle/wallpaper_manager.py:425,506` `wallshuffle/effects.py:31` `ImageOps.exif_transpose` | `grep` 3 sitios, no crash en `try` | ✅ |

## 3. Métricas Técnicas

| Métrica | Antes (v1.0.1) | Después (v1.0.2) | Delta |
|---|---|---|---|
| `ruff` | clean | clean | — |
| `pytest` | 82 passed, `45` omit `app` | **92 passed**, `51.08%` con `app` incluido (omit quitado `app.py`), `fail-under 45→51` | +10 tests, +6% cov real |
| `py_compile` | ok | ok 9 ficheros | — |
| `change_wallpaper` smoke | 0.18s SUCCESS | 0.24s SUCCESS | — |
| `config lock` hold 5s | 10.03s (doble truncado) + file `0B` | **5.01s raise** + file `698B` intacto | Fix truncado antes de lock (`a+` + `truncate` tras lock) |
| `history lock` 5s | hang ∞ | **5.02s skip** | — |
| `image_index` 25 files cap10 | 75 stat | **30 stat** | -60% |
| `monitor cache` | miss cada vez 0.069s | hit 0.000s 1s TTL | — |
| Version | `1.0.1` 5 sitios | `1.0.2` 5 sitios + changelog + metainfo `2026-09-07` | — |
| Git | `5039d47` | `9da4ad0` + `tag v1.0.2` | clean porcelaine `0` |

## 4. Integridad Arquitectura

- **SRP preservado:** Capas `core/manager/online/effects/system` sin God Object; `ConfigLockTimeoutError` en `config_manager` no rompe callers (headless `FILE_SYSTEM_ERROR` vs GUI `show_error_dialog`).
- **Contratos:** `load_settings() -> ConfigParser` mantiene tipo; `raise` es `TimeoutError` subclass → callers existentes `except TimeoutError` compatibles.
- **FFI/GIL:** `Gdk` main-thread guard + `GLib.idle_add` + `event.wait 0.5` mantiene thread-safety; `Pillow` `Image.open` con `with` + `exif_transpose` no leak.
- **Permisos:** `0o700` 13 sitios intactos, `0o600` config, `history.log` `fsync` preservado.
- **No regresión:** `pyproject omit` quitó solo `app.py` (intencional Fase 2), resto `ui/panels/dialogs/handlers/window/__main__` sigue omitido; `mypy` no instalado skip; `install.sh/build_deb.sh` version bump.

## 5. Riesgo Residual

- **Bajo:** `MAX_CACHED_IMAGES` hard break trunca `count` a `MAX` (no real 80k) → `store_cached_images` skip cache correcto, pero métrica `count` ya no refleja real total (aceptable vs I/O storm).
- **Bajo:** `app` coverage 15% → `51%` total aún lejos 55 audit target; requiere `test_app` con `Gio` mock real (próxima iteración).
- **Info:** `datetime` import permanece para `date.today` en cache key; `monotonic` solo para breaker — no conflicto.

## 6. Veredicto Integridad

**✅ INTEGRIDAD VERIFICADA — Sin regresión, arquitectura intacta, parches quirúrgicos correctos.**

Fase 1 resuelve los 5 fallos silenciosos con `monotonic`, `hard break`, `debounce/guard/cache`, `constante` y `exif`. Fase 2 eleva cobertura `45→51` con 10 tests nuevos y versión `1.0.2` consistente. `v1.0.2` listo para `git push --follow-tags` y `scripts/build_deb.sh`.

## 7. Comandos Reproducción

```bash
ruff check wallshuffle --line-length 170
python3 -m pytest tests -q
python3 -m wallshuffle --change  # smoke SUCCESS
git log --oneline -3 && git tag --list | grep 1.0.2
```

*Generado post-fix 2026-09-07 — Auditoría v3.1 Modo Seguridad Máxima*
