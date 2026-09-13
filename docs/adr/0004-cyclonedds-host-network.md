# ADR-0004: CycloneDDS over host networking, localhost-only discovery

- **Status:** Accepted
- **Date:** 2026-09-13

## Context

ROS 2 nodes run in up to six containers on one host. DDS discovery through Docker bridge networks is unreliable: multicast and dynamic ports break behind NAT. Camera images (~1 MB per frame) cross container boundaries.

## Decision

- `network_mode: host` and `ipc: host` for all ROS services.
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` everywhere, configured by `cyclonedds.xml`: loopback interface, multicast off, `localhost` peer, `MaxAutoParticipantIndex=60`, 10 MB socket buffers.
- `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, `ROS_DOMAIN_ID=42`.
- Non-DDS servers bind to `127.0.0.1` explicitly.

## Consequences

- Discovery is deterministic, and nothing leaks onto the LAN.
- Port conflicts with host services are possible (documented port map in NETWORKING.md).
- Host sysctl tuning is required for smooth image transport (documented in SETUP.md).

## Alternatives considered

- **Fast DDS with shared memory.** Faster for images, but SHM across containers with different UIDs is fragile. `ipc: host` keeps this option open.
- **rmw_zenoh.** Promising in Jazzy and later, but adds a router process. Revisit if we go multi-machine.
- **Bridge network + discovery server.** More configuration for no benefit on a single host.
