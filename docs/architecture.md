# 🏛️ KAYAB v4.0 "GENESIS" - Arquitectura Pragmática Escalable

## 📜 Filosofía del Diseño: El Principio del Roble
"El roble más fuerte no fue el más alto desde el principio, sino la semilla que arraigó correctamente."

GENESIS equilibra tres fuerzas:
1. **Simplicidad Inicial** (deployable hoy en una laptop)
2. **Arquitectura Correcta** (escalable a datacenters sin reescribir)
3. **Verificabilidad Progresiva** (seguridad demostrable en cada etapa)

## 🎯 Alcance y Fases de Evolución
- **Fase 1: GENESIS-LOCAL (Meses 0-6)** ✅ Implementable HOY
  - Target: Ubuntu CLI tool, single-machine
  - Complejidad: ~5K SLOC
  - Costo: $0
- **Fase 2: GENESIS-CLUSTER (Meses 6-18)**
  - Target: 3-node consensus system
- **Fase 3: GENESIS-DISTRIBUTED (Meses 18-36)**
  - Target: Multi-datacenter infrastructure

## 🏗️ ARQUITECTURA GENESIS-LOCAL (v4.0)

### Capas Arquitectónicas
1. **Layer 4: Human Interface (CLI/TUI)** - Rich interactive prompts
2. **Layer 3: Decision Engine (Risk Evaluator)** - Heuristic risk scoring
3. **Layer 2: Execution Guardian (Safety Kernel)** - Atomic transactions
4. **Layer 1: System Interface (Sandboxed Executor)** - Namespaced execution
5. **Layer 0: Operating System (Ubuntu 25)**

### 🔒 COMPONENTES CRÍTICOS DETALLADOS

#### Componente 1: Safety Kernel (El Núcleo de Seguridad)
Garantiza atomicidad y reversibilidad.
- **Features:** Anti-TOCTOU, Path traversal protection, SHA-256 hashes, Verified Rollback.
- **Snapshot Logic:** Pre-execution verification of disk space and integrity.

#### Componente 2: Risk Evaluator (Motor de Riesgo Pragmático)
Evalúa riesgo sin complejidad excesiva.
- **Score:** Base Score + Intent Drift (Embeddings) + Context Multiplier.
- **Drift Detection:** Cosine similarity between goal and action.

#### Componente 3: Lite Formal Verification (TLA+ Pragmático)
Verifica invariantes críticas con timeout de 500ms.
- **Fallback:** Degrada a heurístico si TLA+ excede el tiempo.

#### Componente 4: Challenge-Response System
Confirmación entrópica para operaciones de alto riesgo (tokens aleatorios).

## 📊 PROTOCOLO DE EJECUCIÓN
1. **Pre-Validación:** Sanitización y Canonicalización.
2. **Evaluación de Riesgo:** Allow / Challenge / Formal Verify / Deny.
3. **Snapshot:** Backup verificado.
4. **Ejecución:** Sandbox (Firejail/Bubblewrap).
5. **Validación Post-Ejecución:** Rollback automático si falla.
6. **Auditoría:** Log inmutable (SQLite -> Kafka -> Blockchain).

## 🛡️ THREAT MODEL (STRIDE Analysis - v4.0)
- **Spoofing:** Local user auth.
- **Tampering:** SHA-256 + immutable log.
- **Repudiation:** Signed audit entries.
- **Info Disclosure:** File permissions.
- **DoS:** Rate limiting.
- **Elevation of Privilege:** Root detection + deny.

## 🔬 VALIDACIÓN EXPERIMENTAL (Metas)
- **Lectura:** <20ms latency.
- **Mutación:** <120ms latency.
