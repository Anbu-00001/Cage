// membw.cpp -- realized memory-bandwidth microbenchmark (STREAM triad).
//
// WHY THIS EXISTS: decode tok/s on a CPU is memory-bandwidth-bound
// (tokens/sec ~= realized GB/s / model size), and the single most important
// unknown for this whole project is whether this laptop's 16 GB is single- or
// dual-channel -- it *halves or doubles every tok/s estimate*
// (docs/DE-RISKING.md #1). dmidecode tells you how many modules are populated;
// this tells you the number that actually matters: realized GB/s.
//
// METHOD: the STREAM triad kernel a[i] = b[i] + s*c[i] over arrays far larger
// than the last-level cache (>4x LLC, per the STREAM rules), parallelised with
// OpenMP. We sweep thread counts because a single thread cannot saturate a
// multi-channel controller (measured, not assumed). Bandwidth counts the three
// streams touched per iteration (2 read + 1 write = 24 B); the true DRAM
// traffic is ~4/3 higher on write-allocate architectures, so this is a
// conservative lower bound on realized bandwidth.
//
// This is the polyglot stack's C++ leg made real and *useful*, not decorative:
// it is the instrument that converts the tok/s [EST] table into [FACT].
//
// Build:  g++ -O3 -march=native -fopenmp bench/membw.cpp -o bench/membw
// Run:    bench/membw            (or:  OMP_PROC_BIND=close bench/membw)

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include <algorithm>
#include <chrono>
#include <string>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

constexpr double kScalar = 3.0;

// Time one triad pass over N elements with `threads` OpenMP threads; return
// seconds. Arrays are passed in so allocation/first-touch isn't re-timed.
double triad_once(double* __restrict a, const double* __restrict b,
                  const double* __restrict c, std::size_t n, int threads) {
    using clk = std::chrono::steady_clock;
    auto t0 = clk::now();
#ifdef _OPENMP
#pragma omp parallel for num_threads(threads) schedule(static)
#endif
    for (std::size_t i = 0; i < n; ++i) {
        a[i] = b[i] + kScalar * c[i];
    }
    auto t1 = clk::now();
    (void)threads;
    return std::chrono::duration<double>(t1 - t0).count();
}

double best_gbps(std::size_t n, int threads, int reps,
                 double* a, const double* b, const double* c) {
    double best = 1e300;
    for (int r = 0; r < reps; ++r) {
        double s = triad_once(a, b, c, n, threads);
        best = std::min(best, s);
    }
    // 3 arrays * 8 bytes touched per element (STREAM triad convention).
    const double bytes = 3.0 * sizeof(double) * static_cast<double>(n);
    return bytes / best / 1e9;
}

}  // namespace

int main(int argc, char** argv) {
    // Arrays >> LLC. 150U has ~12 MB L3; 64 MB/array (8M doubles) is >4x LLC.
    std::size_t mb_per_array = 64;
    int reps = 10;
    if (argc > 1) mb_per_array = std::strtoull(argv[1], nullptr, 10);
    if (argc > 2) reps = std::atoi(argv[2]);

    const std::size_t n = (mb_per_array * 1024ull * 1024ull) / sizeof(double);

    std::vector<double> a(n), b(n), c(n);
    // First-touch init (also warms pages so timing excludes page faults).
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
    for (std::size_t i = 0; i < n; ++i) { a[i] = 0.0; b[i] = 1.0; c[i] = 2.0; }

    int max_threads = 1;
#ifdef _OPENMP
    max_threads = omp_get_max_threads();
#endif
    std::vector<int> thread_counts;
    for (int t : {1, 2, 4, 8, max_threads})
        if (t <= max_threads &&
            std::find(thread_counts.begin(), thread_counts.end(), t) == thread_counts.end())
            thread_counts.push_back(t);

    std::printf("STREAM triad  a = b + s*c   | %zu MB/array (%zu elems), %d reps (min time)\n",
                mb_per_array, n, reps);
    std::printf("%-10s %14s\n", "threads", "GB/s");
    double peak = 0.0;
    for (int t : thread_counts) {
        double g = best_gbps(n, t, reps, a.data(), b.data(), c.data());
        peak = std::max(peak, g);
        std::printf("%-10d %14.1f\n", t, g);
    }

    // Interpretation. LPDDR5-5200 theoretical: ~41.6 GB/s single-channel
    // (64-bit), ~83.2 GB/s dual-channel (128-bit). STREAM triad lands ~80-90%
    // of theoretical on a saturated controller, lower on a 2-P-core ULV part.
    std::printf("\npeak realized: %.1f GB/s\n", peak);
    const char* verdict;
    if (peak < 50.0)      verdict = "LIKELY SINGLE-CHANNEL -> halve tok/s estimates; a 2nd matched DIMM is the cheapest upgrade";
    else if (peak < 60.0) verdict = "AMBIGUOUS (50-60) -> cross-check with `sudo dmidecode -t memory` module count";
    else                  verdict = "LIKELY DUAL-CHANNEL -> tok/s estimates in the design docs stand";
    std::printf("verdict: %s\n", verdict);
    std::printf("(cross-check populated modules: sudo dmidecode -t memory | grep -c '^\\tSize: [0-9]')\n");
    return 0;
}
