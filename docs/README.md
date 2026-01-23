# EchoNet Documentation

Welcome to the EchoNet documentation. This index helps you find the information you need.

## Core Concepts

### 🎯 [State Machine Reference](./STATE_MACHINE.md) ⭐ **START HERE**
Comprehensive guide to EchoNet's three-mode state system (inactive/trigger/active). Includes:
- Quick reference table
- State diagram with transitions
- Mode descriptions and use cases
- API examples for mode changes
- Troubleshooting guide
- Database audit trail

**Use this when**: Understanding or debugging mode behavior, implementing mode switching, tracking state changes.

---

### ⚙️ [Configuration API](./CONFIG_API.md)
Runtime configuration management for optional features:
- Config endpoints (GET/PUT)
- Pre-roll audio buffering
- Type validation
- Configuration settings reference

**Use this when**: Enabling optional features, configuring pre-roll buffering, managing runtime settings.

---

## Architecture

### 🎤 [ASR Worker Architecture](./ASR_WORKER.md)
Detailed explanation of the Automatic Speech Recognition worker:
- How the three modes work internally
- Cache-based state management
- Recording and transcription flow
- Mode lifecycle diagrams
- API integration examples

**Use this when**: Understanding ASR internals, implementing ASR features, optimizing performance.

---

### 🔊 [Audio Implementation](./AUDIO_IMPLEMENTATION.md)
Low-level audio processing details:
- PyAudio integration
- Sample rate and channel configuration
- Audio buffer management
- Recording session handling

**Use this when**: Debugging audio issues, adding audio features, understanding recording flow.

---

### 🎧 [Audio Devices](./AUDIO_DEVICES.md)
Audio device management and configuration:
- Listing available input devices
- Selecting devices at runtime
- Device enumeration API
- Multi-device support

**Use this when**: Configuring microphones, supporting multiple audio inputs, troubleshooting device issues.

---

## Testing

### 🧪 [Testing Guide](./TESTING.md)
How to run and write tests:
- Unit test organization
- Integration test patterns
- Test database setup
- Coverage reporting

**Use this when**: Running tests, writing new tests, debugging test failures.

---

### 🧪 [ASR Testing](./ASR_TESTING.md)
Specific testing approaches for ASR features:
- Mocking microphone input
- Testing wake word detection
- Verifying mode transitions
- Integration test examples

**Use this when**: Testing ASR features, validating mode behavior, writing ASR tests.

---

## Architecture Decision Records (ADRs)

### 📋 [ADR Index](./adr/README.md)
List of all architectural decisions with links to detailed documents.

### 📄 [ADR 001: Automatic Active Mode Reset](./adr/001-automatic-active-mode-reset.md)
**Decision**: Active mode automatically resets to trigger mode after recording completes.

**Rationale**: Prevents system from staying in "route all audio" mode indefinitely, improving privacy and efficiency.

**Use this when**: Understanding why active mode doesn't persist, implementing mode reset behavior.

---

### 📄 [ADR 002: Inactive Mode](./adr/002-inactive-mode.md)
**Decision**: Add third "inactive" mode where system does not record at all.

**Rationale**: Provides explicit privacy control and power management, distinct from trigger mode which still records.

**Use this when**: Understanding inactive mode purpose, implementing mute/privacy features.

---

## Quick Reference

### Common Tasks

| Task | Documentation |
|------|---------------|
| **Understand mode system** | [State Machine Reference](./STATE_MACHINE.md) |
| **Change recording mode** | [State Machine: API Reference](./STATE_MACHINE.md#api-reference) |
| **Debug mode transitions** | [State Machine: Troubleshooting](./STATE_MACHINE.md#troubleshooting) |
| **Enable optional features** | [Configuration API](./CONFIG_API.md) |
| **Configure pre-roll buffering** | [Configuration API: Pre-Roll](./CONFIG_API.md#using-pre-roll-buffering) |
| **Implement ASR features** | [ASR Worker Architecture](./ASR_WORKER.md) |
| **Configure microphone** | [Audio Devices](./AUDIO_DEVICES.md) |
| **Run tests** | [Testing Guide](./TESTING.md) |
| **Test ASR behavior** | [ASR Testing](./ASR_TESTING.md) |
| **Understand why active mode resets** | [ADR 001](./adr/001-automatic-active-mode-reset.md) |
| **Understand inactive mode** | [ADR 002](./adr/002-inactive-mode.md) |

---

## State Machine Quick Reference

| Mode | Recording | Wake Word Check | Routes Audio | Auto-Reset |
|------|-----------|-----------------|--------------|------------|
| **Inactive** | ❌ No | ❌ No | ❌ No | ❌ No |
| **Trigger** | ✅ Yes | ✅ Yes | Only if wake word | ❌ No |
| **Active** | ✅ Yes | ❌ No | ✅ All audio | ✅ Yes (→ Trigger) |

**See**: [STATE_MACHINE.md](./STATE_MACHINE.md) for complete details.

---

## Contributing

When adding new features or making architectural changes:

1. **Update relevant documentation** - Keep docs in sync with code
2. **Add ADR if needed** - Document significant decisions in `adr/` folder
3. **Update this index** - Add new docs to appropriate sections
4. **Add quick reference entries** - Help users find your documentation

---

## Documentation Structure

```
docs/
├── README.md                    # This file (documentation index)
├── STATE_MACHINE.md             # ⭐ State system reference
├── CONFIG_API.md                # ⚙️ Configuration API and pre-roll buffering
├── ASR_WORKER.md                # ASR architecture
├── AUDIO_IMPLEMENTATION.md      # Low-level audio processing
├── AUDIO_DEVICES.md             # Device management
├── TESTING.md                   # Testing guide
├── ASR_TESTING.md               # ASR-specific testing
└── adr/                         # Architecture Decision Records
    ├── README.md                # ADR index
    ├── 001-automatic-active-mode-reset.md
    └── 002-inactive-mode.md
```
