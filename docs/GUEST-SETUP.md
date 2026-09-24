# Guest setup — standing up the cage (Phase 2 runbook)

The one part of the project that genuinely needs **root + virtualization tools**, so it is a
**scripted hand-off**, not something the build automates for you. Every step below is a script
in the repo; this doc is the order to run them and what to check. Follow the safety scope in
[CLAUDE.md](../CLAUDE.md): in-guest boundaries only, host stays sacred.

> Nothing here was auto-run in this session (running QEMU/libvirt as root on your daily driver
> is your call). The scripts are `bash -n`-clean and the domain XML is well-formed; you run them.

## 0. Prerequisites (one-time)

```bash
sudo apt install qemu-system-x86 qemu-utils libvirt-daemon-system libvirt-clients \
                 ovmf libguestfs-tools alpine-make-vm-image
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt "$USER"   # log out/in so virsh works without sudo
```

## 1. Build the immutable golden image

```bash
sudo vm/scripts/build_golden_image.sh
# -> vm/images/golden.qcow2 (read-only, checksummed) with python3, the cage user,
#    vsock module, and the action daemon started at boot by an OpenRC service.
```

## 2. Make a per-trial overlay (this is the fast reset)

```bash
vm/scripts/reset_overlay.sh vm/images/golden.qcow2 vm/images/trial.qcow2
# Sub-second CoW overlay over the golden base. Re-run to reset between trials.
```

## 3. Define the domain

```bash
sudo vm/scripts/define_domain.sh cage-guest vm/images/trial.qcow2 3 2048
#   name=cage-guest  overlay=…/trial.qcow2  vsock-cid=3  mem=2048MB
# It pins the 2 vCPUs to E-cores (verify the ids it prints against
# `lscpu --all --extended`) and wires OVMF/UEFI + the overlay + vsock.
```

## 4. Audit isolation BEFORE first boot (do not skip)

```bash
vm/scripts/verify_isolation.sh cage-guest
# Static audit: no NIC, no 9p/virtiofs, no USB/GPU passthrough, no clipboard;
# vsock present. Then complete the runtime checks it prints once the guest is up.
```

## 5. Boot and connect

```bash
sudo virsh start cage-guest
sudo virsh console cage-guest     # watch it boot; Ctrl-] to detach
# The action daemon is now listening on vsock (cid 3, port 9000). The host-side
# orchestrator reaches it via VsockChannel(cid=3, port=9000) — see
# src/orchestrator/channel.py. Point config/example.yaml's vm.channel at vsock.
```

## 6. Run one episode against the real guest

```bash
# with llama-server up (docs: build_llama_cpp.sh, threads: 2 per DE-RISKING §4):
./run.sh --seed 42 --config config/example.yaml
```

## 7. Reset between trials / teardown

```bash
sudo virsh destroy cage-guest                 # stop
vm/scripts/reset_overlay.sh vm/images/golden.qcow2 vm/images/trial.qcow2   # clean overlay
sudo virsh start cage-guest                   # fresh trial
# full teardown:
sudo virsh undefine --nvram cage-guest
```

## Safety checklist (per trial)

- [ ] Overlay reset from the checksummed golden (reset_overlay.sh verifies the checksum).
- [ ] `verify_isolation.sh` passes — no NIC, no host mounts, vsock only.
- [ ] Only **planted fake** credentials inside the guest; no host secrets.
- [ ] QEMU running under libvirt's seccomp + AppArmor sVirt (check `seclabel` in dumpxml).
- [ ] The boundary being crossed is one **you engineered in-guest** — never the hypervisor.
