"""Synthetic fixtures only: no live /proc, statvfs, host, account, or network reads."""

import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("health", ROOT / "tools/health.py")
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)
NOW = datetime(2026, 10, 2, 6, 5, tzinfo=timezone.utc)
MEMINFO = "MemTotal: 2048 kB\nMemFree: 50 kB\nMemAvailable: 512 kB\nSwapTotal: 1024 kB\nSwapFree: 256 kB\n"
PSI = "some avg10=12.00 avg60=10.00 avg300=3.00 total=2000000\nfull avg10=2.00 avg60=1.00 avg300=0.50 total=300000\n"
FS = SimpleNamespace(f_frsize=4096, f_blocks=1000, f_bfree=200, f_bavail=150,
                     f_files=1000, f_ffree=100, f_favail=50)
CLI_ENV = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
if os.name == "nt":
    # Python 3.9 needs the Windows system directory during interpreter startup.
    CLI_ENV["SystemRoot"] = os.environ["SystemRoot"]


def demo():
    return json.loads((ROOT / "examples/health-demo.json").read_text(encoding="utf-8"))


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.proc = Path(self.temp.name)
        (self.proc / "pressure").mkdir()
        for path, text in {"meminfo": MEMINFO, "loadavg": "0.25 1.00 0.75 1/25 999\n",
                           "stat": "cpu 1 2 3 4\ncpu0 1 2 3 4\ncpu1 1 2 3 4\nprocesses 25\n",
                           "uptime": "3600.25 6500.0\n", "pressure/memory": PSI}.items():
            (self.proc / path).write_text(text, encoding="ascii")

    def collect(self, fs=FS):
        return health.collect_snapshot(self.proc, lambda path: fs, "linux", NOW)

    def test_proc_parsing_and_memory_swap_formulas(self):
        snapshot = self.collect()
        self.assertEqual(snapshot["collected_at"], "2026-10-02T06:05:00Z")
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["source"]["kind"], "linux-procfs")
        metrics = snapshot["metrics"]
        self.assertEqual(metrics["cpu"], {"load_1m": 0.25, "load_5m": 1.0, "load_15m": 0.75, "logical_cpus": 2})
        self.assertEqual(metrics["memory"], {"total_bytes": 2048 * 1024, "available_bytes": 512 * 1024})
        self.assertEqual(metrics["swap"], {"total_bytes": 1024 * 1024, "used_bytes": 768 * 1024})
        self.assertEqual(metrics["uptime"]["seconds"], 3600.25)
        self.assertEqual(metrics["memory_psi"]["some"]["total_us"], 2000000)
        self.assertNotIn("999", json.dumps(snapshot))  # last PID from loadavg is discarded

    def test_disk_bytes_and_reserved_blocks_and_inodes(self):
        metrics = self.collect()["metrics"]
        self.assertEqual(metrics["root_bytes"], {"total_bytes": 4096000, "free_bytes": 819200, "available_bytes": 614400})
        self.assertEqual(metrics["root_inodes"], {"total": 1000, "free": 100, "available": 50})
        self.assertEqual(health.assess("root_bytes", metrics["root_bytes"]), "warning")
        self.assertEqual(health.assess("root_inodes", metrics["root_inodes"]), "critical")

    def test_unsupported_inodes_leave_bytes_available(self):
        fs = copy.copy(FS)
        fs.f_files = fs.f_ffree = fs.f_favail = 0
        metrics = self.collect(fs)["metrics"]
        self.assertIn("error", metrics["root_inodes"])
        self.assertNotIn("error", metrics["root_bytes"])

    def test_missing_or_corrupt_proc_is_unknown(self):
        for file, content, metric in (("loadavg", "nan 1 2", "cpu"), ("stat", "cpu 1 2 3", "cpu"),
                                      ("uptime", "", "uptime"), ("pressure/memory", "some avg10=0", "memory_psi")):
            with self.subTest(file=file):
                path = self.proc / file
                original = path.read_text()
                path.write_text(content)
                value = self.collect()["metrics"][metric]
                self.assertEqual(health.assess(metric, value), "unknown")
                path.write_text(original)
        (self.proc / "pressure/memory").unlink()
        self.assertEqual(health.assess("memory_psi", self.collect()["metrics"]["memory_psi"]), "unknown")

    def test_memavailable_has_no_memfree_fallback_and_swap_is_independent(self):
        (self.proc / "meminfo").write_text(MEMINFO.replace("MemAvailable: 512 kB\n", ""))
        metrics = self.collect()["metrics"]
        self.assertIn("error", metrics["memory"])
        self.assertEqual(metrics["swap"]["used_bytes"], 768 * 1024)

    def test_bad_memory_units_and_negative_swap_are_unknown(self):
        (self.proc / "meminfo").write_text(MEMINFO.replace("MemTotal: 2048 kB", "MemTotal: 2048 MB").replace("SwapFree: 256", "SwapFree: 2048"))
        metrics = self.collect()["metrics"]
        self.assertIn("error", metrics["memory"])
        self.assertIn("error", metrics["swap"])

    def test_non_linux_stops_before_reading(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("no reads")):
            with self.assertRaisesRegex(ValueError, "仅支持 Linux"):
                health.collect_snapshot(system="darwin")

    def test_statvfs_failure_is_unknown_and_only_root_is_requested(self):
        def unavailable(path):
            self.assertEqual(path, "/")
            raise OSError("synthetic unavailable")
        metrics = health.collect_snapshot(self.proc, unavailable, "linux", NOW)["metrics"]
        self.assertIn("error", metrics["root_bytes"])
        self.assertIn("error", metrics["root_inodes"])
        self.assertNotIn("error", metrics["memory"])


class ValidationAndThresholdTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        cases = [("memory", {"total_bytes": 100, "available_bytes": 11}, "ok"),
                 ("memory", {"total_bytes": 100, "available_bytes": 10}, "warning"),
                 ("memory", {"total_bytes": 100, "available_bytes": 5}, "critical"),
                 ("swap", {"total_bytes": 100, "used_bytes": 50}, "warning"),
                 ("swap", {"total_bytes": 0, "used_bytes": 0}, "info"),
                 ("cpu", {"load_1m": 10, "load_5m": 1.99, "load_15m": 1, "logical_cpus": 2}, "ok"),
                 ("cpu", {"load_1m": 0, "load_5m": 2, "load_15m": 1, "logical_cpus": 2}, "warning"),
                 ("memory_psi", health.parse_psi(PSI), "warning")]
        for name, value, expected in cases:
            with self.subTest(name=name, value=value):
                self.assertEqual(health.assess(name, health.validate_metric(name, value)), expected)

    def test_missing_metric_is_unknown_never_healthy(self):
        snapshot = demo()
        del snapshot["metrics"]["cpu"]
        value = health.validate_snapshot(snapshot)["metrics"]["cpu"]
        self.assertEqual(health.assess("cpu", value), "unknown")
        self.assertIn("1 项未知", health.render_snapshot(snapshot, NOW))

    def test_malformed_metric_is_rejected(self):
        cases = [None, {}, {"total_bytes": 0, "available_bytes": 0},
                 {"total_bytes": 100, "available_bytes": 101},
                 {"total_bytes": 100, "available_bytes": -1},
                 {"total_bytes": 100, "available_bytes": True},
                 {"total_bytes": 100, "available_bytes": float("nan")},
                 {"total_bytes": 100, "available_bytes": "50"},
                 {"error": "unknown", "total_bytes": 100}]
        for value in cases:
            with self.subTest(value=value):
                snapshot = demo()
                snapshot["metrics"]["memory"] = value
                with self.assertRaises(ValueError):
                    health.render_snapshot(snapshot, NOW)

    def test_schema_and_timestamp_required(self):
        for key, value in (("schema_version", 2), ("schema_version", True),
                           ("collected_at", "2026-02-30T06:00:00Z"), ("collected_at", "2026-10-02T06:00:00"),
                           ("source", {}), ("metrics", [])):
            with self.subTest(key=key, value=value):
                snapshot = demo()
                snapshot[key] = value
                with self.assertRaises(ValueError):
                    health.validate_snapshot(snapshot)

    def test_impossible_filesystem_and_psi_are_rejected(self):
        with self.assertRaises(ValueError):
            health.validate_metric("root_inodes", {"total": 100, "free": 50, "available": 60})
        psi = health.parse_psi(PSI)
        psi["full"]["avg60"] = 20
        with self.assertRaises(ValueError):
            health.validate_metric("memory_psi", psi)


class RenderingAndCliTests(unittest.TestCase):
    def test_report_is_offline_explains_age_and_no_swap(self):
        report = health.render_snapshot(demo(), NOW)
        for text in ("合成演示数据", "0 天 00:05:00", "2 项需关注 · 0 项未知", "未配置",
                     "无 swap 不等于已发生 OOM", "不是 CPU utilization", "年龄固定在 HTML 生成时"):
            self.assertIn(text, report)
        self.assertNotIn("<script", report)
        self.assertNotIn("http://", report)
        self.assertNotIn("https://", report)
        self.assertIn("default-src 'none'", report)
        old = health.render_snapshot(demo(), datetime(2026, 10, 3, tzinfo=timezone.utc))
        self.assertIn("历史快照（超过 15 分钟）", old)
        future = health.render_snapshot(demo(), datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertIn("时钟异常", future)

    def test_untrusted_text_is_html_escaped(self):
        snapshot = demo()
        attack = '</style><script>alert("x")</script><img src="https://example.com/x">'
        snapshot["source"]["description"] = attack
        snapshot["metrics"]["cpu"] = {"error": attack}
        report = health.render_snapshot(snapshot, NOW)
        self.assertNotIn(attack, report)
        self.assertNotIn("<script>", report)
        self.assertNotIn("<img", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("&quot;x&quot;", report)

    def test_cli_synthetic_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "demo.json"
            report = Path(directory) / "demo.html"
            command = [sys.executable, str(ROOT / "tools/health.py")]
            for arguments in (["collect", "--demo", "-o", str(snapshot)],
                              ["render", str(snapshot), "-o", str(report)]):
                result = subprocess.run(command + arguments, capture_output=True, encoding="utf-8",
                                        cwd=directory, env=CLI_ENV)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(snapshot.read_text(encoding="utf-8")), demo())
            self.assertIn("合成演示数据", report.read_text(encoding="utf-8"))
            result = subprocess.run(command + ["render", str(snapshot), "-o", str(snapshot)],
                                    capture_output=True, encoding="utf-8", cwd=directory,
                                    env=CLI_ENV)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(snapshot.read_text(encoding="utf-8")), demo())

    def test_cli_rejects_bad_json_without_creating_report(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "bad.json"
            output = Path(directory) / "report.html"
            snapshot.write_text('{"schema_version": NaN}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "tools/health.py"), "render", str(snapshot), "-o", str(output)],
                                    capture_output=True, encoding="utf-8", cwd=directory,
                                    env=CLI_ENV)
            self.assertEqual(result.returncode, 2)
            self.assertIn("NaN", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
