# Linux Boot Time Optimization on Raspberry Pi 4B

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204B%20(Rev%201.4)-red.svg)](https://www.raspberrypi.com/)
[![Kernel](https://img.shields.io/badge/Kernel-Linux%206.18.34%2Brpt--rpi--v8-blue.svg)](https://github.com/raspberrypi/linux)
[![Architecture](https://img.shields.io/badge/Arch-arm64%20%2F%20aarch64-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT%20%2F%20Academic-green.svg)]()

A systematic, stage-by-stage methodology and complete toolchain for profiling, diagnosing, and optimizing Linux boot time on resource-constrained embedded systems. Evaluated on the **Raspberry Pi 4 Model B (4 GB)** across two distinct deployment profiles:

1. **Headless Server** (*Raspberry Pi OS Lite*): display-less, audio-less, headless network appliance.
2. **Interactive Unit** (*Raspberry Pi OS with Desktop*): graphical desktop workstation requiring HDMI, audio, USB input, and Bluetooth.

---

## 📊 Executive Summary & Key Results

All measurements reflect the **mean across 10 unattended boot iterations** under clean production kernel command-line settings (no instrumentation logging overhead).

### 1. Headless Server Profile (*Raspberry Pi OS Lite*)

| Stage / Configuration | Kernel Time | Userspace Time | Total Boot Time | Time to Target (`multi-user.target`) |
| :--- | :---: | :---: | :---: | :---: |
| **Stock Baseline** | 2.00 s | 13.96 s | **15.96 s** | 10.53 s |
| **Stage 1: Tracing Disabled** (`FTRACE`, `KPROBES`) | 1.05 s | — | — | — |
| **Stage 2: DRM/VC4 & VCHIQ Removed** | 1.04 s | — | — | — |
| **Stage 3: USB & PCIe Subsystem Disabled** | **0.81 s** | — | — | — |
| **Userspace + Cloud-Init Disabled** | 0.81 s | 6.89 s | **7.70 s** | 7.70 s |
| **Userspace + `systemd-networkd` & Unmanaged `eth0`** | 0.81 s | 5.18 s | **5.99 s** | 5.99 s |
| **Final Optimized (with Optional Cleanup)** | **0.79 s** | **5.23 s** | **6.01 s** | **6.01 s** |
| **Overall Improvement** | **-60.5% (1.21 s saved)** | **-62.5% (8.73 s saved)** | **-62.3% (9.95 s saved)** | **-42.9% (4.52 s saved)** |

### 2. Interactive Unit Profile (*Raspberry Pi OS Desktop*)

| Stage / Configuration | Kernel Time | Userspace Time | Total Boot Time | Time to Target (`graphical.target`) |
| :--- | :---: | :---: | :---: | :---: |
| **Stock Baseline** | 2.65 s | 18.85 s | **21.50 s** | 15.98 s |
| **Kernel: Tracing Disabled** | 1.07 s | — | — | — |
| **Userspace: Cloud-Init Disabled & `eth0` Unmanaged** | 1.07 s | 10.14 s | **11.21 s** | **8.74 s** |
| **Overall Improvement** | **-59.6% (1.58 s saved)** | **-46.2% (8.71 s saved)** | **-47.9% (10.29 s saved)** | **-45.3% (7.24 s saved)** |

---

## 🔬 Key Engineering Discoveries

1. **Upstream Tracing Lock Contention**:
   - Instrumented initcall profiling revealed `init_kprobe_trace` taking ~378 ms and `gpio_led_driver_init` taking ~218 ms in stock builds.
   - Root cause: serialized lock contention where `setup_boot_kprobe_events()` blocks on `event_mutex` while `early_event_add_tracer()` waits on `trace_event_sem` during trace event metadata updates.
   - Disabling tracing (`CONFIG_FTRACE`, `CONFIG_KPROBE_EVENTS`, `CONFIG_EVENT_TRACING`) eliminated this lock contention entirely, dropping `gpio_led_driver_init` to ~1.8 ms.
2. **The Disconnected `eth0` Carrier-Wait Trap**:
   - NetworkManager introduced multi-second delays waiting for network online readiness, originally suspected to be WPA-Enterprise authentication latency (which was measured to be <10 ms).
   - The culprit was an unmanaged/disconnected physical Ethernet interface (`eth0`) unconditionally polled by NetworkManager's startup completion logic.
   - Explicitly unmanaging `eth0` resolved the carrier-wait artifact completely.
3. **Off-Critical-Chain Pruning vs. Real Boot Latency**:
   - Disabling services like `bluetooth.service`, `avahi-daemon.service`, and `keyboard-setup.service` improved runtime memory and CPU footprint, but had **zero impact** on boot time because none were on the `critical-chain`.

---

## 🛠️ Hardware & Software Environment

- **Board**: Raspberry Pi 4 Model B (Rev 1.4, 4 GB LPDDR4)
- **Power Supply**: Official Raspberry Pi 15.3W USB-C Power Supply (5.1V DC, 3.0A)
- **Storage**: Samsung EVO Plus 64 GB microSDXC (UHS-I U3, A2)
- **Kernel Tree**: [raspberrypi/linux](https://github.com/raspberrypi/linux) branch `rpi-6.18.y` (pinned to `6.18.34+rpt-rpi-v8`)
- **Cross-Compiler**: `aarch64-linux-gnu-gcc` on an x86_64 build host

---

## 📂 Repository Layout

```text
.
├── README.md                          # Project documentation and summary
├── data/                              # Raw measurement logs and parsed CSV data (10 runs per stage)
│   ├── headless/
│   │   ├── kernel/                    # Stage 0 to Stage 3 kernel initcall & milestone data
│   │   └── userspace/                 # Default, without-cloud-init, networkd, optional-services data
│   └── interactive/
│       ├── 0-baseline/                # Stock desktop baseline measurements
│       ├── 1-tracing-disabled-kernel/
│       ├── 2-userspace-cloudinit/
│       └── kernel-6.18.39/            # Point-version comparative data
├── scripts/                           # Complete benchmarking & analysis toolchain
│   ├── toggle_kernel_logging.sh       # Safely enables/disables initcall_debug in cmdline.txt
│   ├── boot_log_capture.sh            # 10-iteration unattended dmesg / initcall log capture script
│   ├── boot-log-capture.service       # Systemd one-shot service running boot_log_capture.sh
│   ├── profile-boot.sh                # 10-iteration unattended systemd-analyze capture & reboot script
│   ├── boot-profiler.service          # Systemd service executing profile-boot.sh on boot
│   ├── parse_initcalls.py             # Parses dmesg initcall logs into raw & summary CSVs
│   ├── plot_initcalls.py              # Plots top slowest initcalls and cumulative duration charts
│   ├── parse_metrics.py               # Parses systemd-analyze time logs into global milestone CSVs
│   ├── parse_userspace.py             # Parses blame & critical-chain logs into structured CSVs
│   ├── plot_userspace.py              # Plots critical chain Gantt timelines and blame rankings
│   ├── analyze_global.py              # Generates stacked kernel/userspace milestone plots
│   └── analyze_components.py          # Component bottleneck & pie chart breakdown generator
├── report/                            # Full academic project report
│   ├── main.tex                       # Complete LaTeX report document
│   ├── main.pdf                       # Compiled research paper
│   └── images/                        # Generated plots, critical chains, and benchmark graphs
└── docs/                              # Additional hardware and methodology notes
```

---

## 🚀 Automation & Measurement Toolchain

The repository includes a self-contained suite of shell scripts, systemd units, and Python analysis tools designed for unattended, repeatable benchmarking.

### Toolchain Inventory

| Script / Service | Role / Purpose | Input / Target | Output |
| :--- | :--- | :--- | :--- |
| [`toggle_kernel_logging.sh`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/toggle_kernel_logging.sh) | Idempotently toggles `initcall_debug printk.time=1 loglevel=8` | `/boot/firmware/cmdline.txt` | Modifies cmdline (preserves `.orig` backup) |
| [`boot_log_capture.sh`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/boot_log_capture.sh) | Unattended 10-iteration kernel `dmesg` capture and auto-reboot | Kernel ring buffer (`dmesg`) | `run{N}_dmesg.txt`, `run{N}_initcall.txt` |
| [`boot-log-capture.service`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/boot-log-capture.service) | Systemd unit triggering `boot_log_capture.sh` | Triggered at `multi-user.target` | Disables itself after run 10 |
| [`profile-boot.sh`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/profile-boot.sh) | Unattended 10-iteration `systemd-analyze` profiler and auto-reboot | `systemd-analyze` time, blame, chain | `run_{N}_summary.txt`, `run_{N}_blame.txt`, `run_{N}_chain.txt` |
| [`boot-profiler.service`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/boot-profiler.service) | Systemd unit triggering `profile-boot.sh` | Triggered at `multi-user.target` | Disables itself after run 10 |
| [`parse_initcalls.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/parse_initcalls.py) | Regex parser extracting initcall name, return code, duration | Directory of `run*_initcall.txt` | `initcall_raw.csv`, `initcall_summary.csv` |
| [`plot_initcalls.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/plot_initcalls.py) | Matplotlib renderer for slowest initcalls & cumulative curves | `initcall_summary.csv` | `top_20_slowest_initcalls.png`, cumulative plot |
| [`parse_metrics.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/parse_metrics.py) | Parses systemd duration tokens (e.g. `821ms`, `1min 9.8s`) | Directory of `run_*_summary.txt` | `global_milestones.csv`, `global_summary.csv` |
| [`parse_userspace.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/parse_userspace.py) | Extracts timing & tree hierarchies from blame and critical-chain | `run_*_blame.txt`, `run_*_chain.txt` | `critical_chain_detail.csv`, `blame_summary.csv` |
| [`plot_userspace.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/plot_userspace.py) | Gantt timeline & color-coded blame plot (on-chain vs off-chain) | `critical_chain_detail.csv`, blame CSV | `critical_chain_timeline.png`, `blame_ranking.png` |
| [`analyze_global.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/analyze_global.py) | Renders stacked kernel vs. userspace bar chart with target lines | `global_milestones.csv` | `global_milestones.png` |
| [`analyze_components.py`](file:///home/kartikey/Documents/12-credit-PE/boot-time-measurements/scripts/analyze_components.py) | Cleans unit names and generates component breakdown visualizations | `component_bottlenecks.csv` | `component_bottlenecks.png`, `component_pie.png` |

---

## 🔄 End-to-End Workflow Walkthrough

### Phase 1: Profiling Kernel Initcalls (Instrumented Mode)

1. **Enable Kernel Debug Logging**:
   ```bash
   sudo ./scripts/toggle_kernel_logging.sh on
   ```
2. **Install and Enable the Boot Log Capture Service**:
   ```bash
   sudo cp scripts/boot_log_capture.sh /usr/local/bin/
   sudo chmod +x /usr/local/bin/boot_log_capture.sh
   sudo cp scripts/boot-log-capture.service /etc/systemd/system/
   sudo systemctl enable boot-log-capture.service
   sudo reboot
   ```
   *The system will automatically boot 10 times, capture logs to `/home/pi/boot_logs/`, and disable the service upon completion.*

3. **Disable Kernel Debug Logging for Production Runs**:
   ```bash
   sudo ./scripts/toggle_kernel_logging.sh off
   ```

4. **Parse and Visualize Kernel Initcalls**:
   ```bash
   python3 scripts/parse_initcalls.py /home/pi/boot_logs/ --out-summary initcall_summary.csv
   python3 scripts/plot_initcalls.py initcall_summary.csv --out-bar top_20_initcalls.png
   ```

---

### Phase 2: Profiling Userspace & Global Milestones (Clean Production Mode)

1. **Install and Enable the Userspace Profiler Service**:
   ```bash
   sudo cp scripts/profile-boot.sh /usr/local/bin/
   sudo chmod +x /usr/local/bin/profile-boot.sh
   sudo cp scripts/boot-profiler.service /etc/systemd/system/
   sudo systemctl enable boot-profiler.service
   sudo reboot
   ```
   *`profile-boot.sh` polls `systemctl is-system-running`, waits for stability, records `systemd-analyze` metrics for 10 iterations, and automatically disables itself.*

2. **Parse Userspace and Global Metrics**:
   ```bash
   # Parse systemd-analyze time outputs
   python3 scripts/parse_metrics.py /home/kartikey/profile/

   # Parse systemd-analyze blame and critical-chain logs
   python3 scripts/parse_userspace.py /home/kartikey/profile/
   ```

3. **Generate Publication-Quality Plots**:
   ```bash
   # Stacked kernel/userspace milestone chart
   python3 scripts/analyze_global.py /home/kartikey/profile/ \
       --profile "Headless Server (Optimized)"

   # Userspace critical-chain Gantt chart and blame ranking
   python3 scripts/plot_userspace.py /home/kartikey/profile/ \
       --profile "Headless Server (Optimized)"
   ```

---

## ⚙️ Kernel Configuration Recipes

Kernel builds were performed on an x86_64 host using the official Raspberry Pi cross-compilation toolchain:

```bash
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-

git clone --depth=1 --branch rpi-6.18.y https://github.com/raspberrypi/linux.git
cd linux
make bcm2711_defconfig
```

### Stage 1: Tracing Subsystem Removal (Common to Headless & Interactive)
Disables FTRACE, Kprobes, and dynamic tracepoint event infrastructure:
```bash
scripts/config --disable CONFIG_FTRACE
scripts/config --disable CONFIG_KPROBE_EVENTS
scripts/config --disable CONFIG_EVENT_TRACING
scripts/config --disable CONFIG_KPROBES
make olddefconfig
```

### Stage 2: VideoCore DRM & VCHIQ Removal (Headless Server)
Removes the display pipeline, hardware video codecs, GPU IPC, and camera interfaces:
```bash
scripts/config --disable CONFIG_DRM_VC4
scripts/config --disable CONFIG_BCM2835_VCHIQ
scripts/config --disable CONFIG_BCM2835_VCHIQ_MMAL
scripts/config --disable CONFIG_BCM_VC_SM_CMA
scripts/config --disable CONFIG_SND_BCM2835
scripts/config --disable CONFIG_VIDEO_BCM2835
scripts/config --disable CONFIG_VIDEO_BCM2835_UNICAM
scripts/config --disable CONFIG_VIDEO_BCM2835_UNICAM_LEGACY
scripts/config --disable CONFIG_VIDEO_CODEC_BCM2835
scripts/config --disable CONFIG_VIDEO_ISP_BCM2835
make olddefconfig
```

### Stage 3: USB & PCIe Subsystem Removal (Headless Server)
Removes PCIe root complex controller and xHCI host controllers:
```bash
scripts/config --disable CONFIG_USB_PCI
scripts/config --disable CONFIG_PCIE_BRCMSTB
make olddefconfig
```

### Build & Deploy:
```bash
make -j$(nproc) Image modules dtbs
```

---

## 🌐 Userspace Optimization Recipes

### 1. Disabling Cloud-Init
```bash
sudo systemctl disable --now cloud-init.service cloud-init-local.service cloud-config.service cloud-final.service
sudo touch /etc/cloud/cloud-init.disabled
```

### 2. Headless Network: `systemd-networkd` + `wpa_supplicant`
Disable NetworkManager and switch to native `systemd-networkd`:
```bash
sudo systemctl disable --now NetworkManager NetworkManager-wait-online.service
sudo systemctl enable systemd-networkd systemd-resolved
```

Configure `/etc/systemd/network/10-eth0.network` to ignore disconnected Ethernet:
```ini
[Match]
Name=eth0

[Link]
Unmanaged=yes
```

Configure `/etc/systemd/network/20-wlan0.network`:
```ini
[Match]
Name=wlan0

[Network]
DHCP=yes
```

### 3. Interactive Desktop: Unmanaging `eth0` in NetworkManager
Keep NetworkManager for GUI ease of use, but avoid carrier wait on unconnected Ethernet:
```ini
# /etc/NetworkManager/conf.d/99-unmanage-eth0.conf
[keyfile]
unmanaged-devices=interface-name:eth0
```

---

## 📜 Academic Project Report

For full theoretical analysis, lock-contention call graphs, and citations, refer to the documents in [`report/`](report/):
- **Source**: [`report/main.tex`](report/main.tex)
- **Compiled PDF**: [`report/main.pdf`](report/main.pdf)

**Citation**:
```bibtex
@techreport{dubey2026boottime,
  title={Profiling and Reducing Linux Kernel Boot Time on Resource-Constrained Embedded Boards: A Practitioner's Guide (Raspberry Pi)},
  author={Dubey, Kartikey and Thangaraju, B.},
  institution={International Institute of Information Technology Bangalore (IIIT-B)},
  year={2026}
}
```
