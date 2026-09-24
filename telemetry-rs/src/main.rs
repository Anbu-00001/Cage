//! cage-telemetry -- a lean, zero-dependency 1 Hz resource + energy sampler.
//!
//! The polyglot stack's Rust leg, made real. It samples exactly the vector the
//! design docs call for (constraint-cage.md Part 11/12): RAPL package energy
//! (the "watts" in intelligence-per-watt), CPU temperature, per-core frequency,
//! pressure-stall (PSI), and available memory -- once per second, emitting one
//! NDJSON object per sample to stdout (or a file). It is the "hardened in Rust"
//! counterpart to src/telemetry (Python): no GC, no async runtime, no crates,
//! so it can run alongside a memory-bound inference loop without stealing the
//! cycles it is trying to measure.
//!
//! RAPL correctness (the subtle bits, per docs/DE-RISKING.md §2):
//!   * sum only TOP-LEVEL domains (`intel-rapl:0`), never the `:0:0` subzones,
//!     or the core's joules get counted twice;
//!   * the `energy_uj` counter is finite and ROLLS OVER (every minute or two
//!     under load on some parts) -- unwrap it using `max_energy_range_uj`.
//!   * needs read access to energy_uj (root-only by default -- run
//!     scripts/setup_rapl_access.sh once, DE-RISKING §2).
//!
//! Usage:
//!   cage-telemetry                 # 1 Hz to stdout
//!   cage-telemetry --interval 0.5  # 2 Hz
//!   cage-telemetry --out run.ndjson

use std::fs;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const POWERCAP: &str = "/sys/class/powercap";

fn read_trim(path: &Path) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_string())
}

fn read_u64(path: &Path) -> Option<u64> {
    read_trim(path).and_then(|s| s.parse().ok())
}

/// A top-level RAPL power domain with rollover-aware joule accounting.
struct RaplDomain {
    label: String,
    energy_path: PathBuf,
    max_range_uj: u64,
    last_uj: u64,
    total_j: f64,
}

impl RaplDomain {
    /// Delta joules since the previous read, unwrapping a counter rollover.
    fn sample(&mut self) -> Option<f64> {
        let cur = read_u64(&self.energy_path)?;
        let delta_uj = if cur >= self.last_uj {
            cur - self.last_uj
        } else {
            // Counter wrapped: (max - last) + cur.
            self.max_range_uj.saturating_sub(self.last_uj) + cur
        };
        self.last_uj = cur;
        let delta_j = delta_uj as f64 / 1_000_000.0;
        self.total_j += delta_j;
        Some(delta_j)
    }
}

/// Discover only top-level `intel-rapl:N` domains (exactly one ':' after the
/// prefix), skipping `:N:M` subzones and non-intel-rapl controllers.
fn discover_rapl() -> Vec<RaplDomain> {
    let mut out = Vec::new();
    let Ok(entries) = fs::read_dir(POWERCAP) else {
        eprintln!("cage-telemetry: {POWERCAP} unreadable; RAPL disabled (see DE-RISKING §2)");
        return out;
    };
    for e in entries.flatten() {
        let name = e.file_name().to_string_lossy().into_owned();
        // top-level intel-rapl package domains look like "intel-rapl:0"
        let is_top = name.starts_with("intel-rapl:") && name.matches(':').count() == 1;
        if !is_top {
            continue;
        }
        let dir = e.path();
        let energy_path = dir.join("energy_uj");
        let Some(first) = read_u64(&energy_path) else {
            eprintln!("cage-telemetry: {} unreadable; run scripts/setup_rapl_access.sh", energy_path.display());
            continue;
        };
        let label = read_trim(&dir.join("name")).unwrap_or(name);
        let max_range_uj = read_u64(&dir.join("max_energy_range_uj")).unwrap_or(u64::MAX);
        out.push(RaplDomain { label, energy_path, max_range_uj, last_uj: first, total_j: 0.0 });
    }
    out
}

/// Highest CPU temperature in °C across thermal zones (package temp proxy).
fn max_temp_c() -> Option<f64> {
    let mut best: Option<f64> = None;
    for e in fs::read_dir("/sys/class/thermal").ok()?.flatten() {
        let p = e.path();
        if !p.file_name()?.to_string_lossy().starts_with("thermal_zone") {
            continue;
        }
        if let Some(milli) = read_u64(&p.join("temp")) {
            let c = milli as f64 / 1000.0;
            best = Some(best.map_or(c, |b: f64| b.max(c)));
        }
    }
    best
}

/// Max current per-core frequency in kHz (spot the P-core turbo / throttle).
fn max_freq_khz() -> Option<u64> {
    let mut best: Option<u64> = None;
    for e in fs::read_dir("/sys/devices/system/cpu").ok()?.flatten() {
        let p = e.path().join("cpufreq/scaling_cur_freq");
        if let Some(khz) = read_u64(&p) {
            best = Some(best.map_or(khz, |b: u64| b.max(khz)));
        }
    }
    best
}

/// PSI "some avg10" for a resource (cpu/memory/io); the short-window stall %.
fn psi_some_avg10(resource: &str) -> Option<f64> {
    let text = fs::read_to_string(format!("/proc/pressure/{resource}")).ok()?;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("some ") {
            for tok in rest.split_whitespace() {
                if let Some(v) = tok.strip_prefix("avg10=") {
                    return v.parse().ok();
                }
            }
        }
    }
    None
}

fn mem_available_kb() -> Option<u64> {
    let text = fs::read_to_string("/proc/meminfo").ok()?;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("MemAvailable:") {
            return rest.split_whitespace().next()?.parse().ok();
        }
    }
    None
}

fn opt_num<T: std::fmt::Display>(v: Option<T>) -> String {
    v.map(|x| x.to_string()).unwrap_or_else(|| "null".into())
}

fn main() {
    // --- tiny arg parse (no clap: zero deps) ---
    let args: Vec<String> = std::env::args().collect();
    let mut interval = 1.0_f64;
    let mut out_path: Option<String> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--interval" => { i += 1; interval = args.get(i).and_then(|s| s.parse().ok()).unwrap_or(1.0); }
            "--out" => { i += 1; out_path = args.get(i).cloned(); }
            "-h" | "--help" => { eprintln!("usage: cage-telemetry [--interval SECS] [--out FILE]"); return; }
            other => { eprintln!("cage-telemetry: ignoring unknown arg {other:?}"); }
        }
        i += 1;
    }

    let mut writer: BufWriter<Box<dyn Write>> = BufWriter::new(match &out_path {
        Some(p) => Box::new(fs::File::create(p).expect("cannot open --out file")),
        None => Box::new(std::io::stdout()),
    });

    let mut rapl = discover_rapl();
    let period = Duration::from_secs_f64(interval.max(0.05));
    let t0 = Instant::now();

    loop {
        let tick = Instant::now();
        let unix = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f64();

        // RAPL: watts = delta_j / interval; also carry cumulative joules.
        let mut rapl_json = String::from("{");
        for (idx, d) in rapl.iter_mut().enumerate() {
            let dj = d.sample();
            let watts = dj.map(|j| j / interval);
            if idx > 0 { rapl_json.push(','); }
            rapl_json.push_str(&format!(
                "\"{}\":{{\"watts\":{},\"joules_total\":{:.3}}}",
                d.label, opt_num(watts.map(|w| format!("{w:.3}"))), d.total_j
            ));
        }
        rapl_json.push('}');

        let line = format!(
            "{{\"t\":{unix:.3},\"elapsed_s\":{:.3},\"rapl\":{rapl_json},\"temp_c\":{},\"freq_khz_max\":{},\"psi_cpu_some_avg10\":{},\"psi_mem_some_avg10\":{},\"mem_available_kb\":{}}}",
            t0.elapsed().as_secs_f64(),
            opt_num(max_temp_c().map(|c| format!("{c:.1}"))),
            opt_num(max_freq_khz()),
            opt_num(psi_some_avg10("cpu").map(|v| format!("{v:.2}"))),
            opt_num(psi_some_avg10("memory").map(|v| format!("{v:.2}"))),
            opt_num(mem_available_kb()),
        );
        if writeln!(writer, "{line}").is_err() { break; }
        let _ = writer.flush();

        // Fixed-rate sleep that accounts for the work we just did.
        let elapsed = tick.elapsed();
        if elapsed < period {
            thread::sleep(period - elapsed);
        }
    }
}
