import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SEVERITY_COLORS = {
    "Critical": "#FF3131",
    "High": "#FFA500",
    "Medium": "#FFD700",
    "Low": "#00BFFF",
    "Informational": "#22C55E",
    "Unknown": "#6B7280",
}

_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_RE_HASH = re.compile(r"\b[a-fA-F0-9]{32,64}\b")
_RE_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")

_SOURCE_MAP = {
    "threat": "threat_report",
    "log": "log",
}

_IOC_TYPES = {"ip", "domain", "hash", "indicator", "url"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_severity(raw: Optional[str]) -> str:
    text = str(raw or "").strip().lower()
    if "critical" in text:
        return "Critical"
    if "high" in text:
        return "High"
    if "medium" in text:
        return "Medium"
    if "low" in text:
        return "Low"
    if "info" in text:
        return "Informational"
    return "Unknown"


def _infer_severity_from_text(*values: Any) -> str:
    combined = " ".join(str(v or "") for v in values).lower()
    inferred = _normalize_severity(combined)
    return "Medium" if inferred == "Unknown" else inferred


def _severity_from_score(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "Unknown"

    # Heuristic thresholds for retrieval/confidence-like scores.
    if value >= 0.9:
        return "Critical"
    if value >= 0.75:
        return "High"
    if value >= 0.5:
        return "Medium"
    return "Low"


def _fallback_report_severity(severity: str, iocs: Dict[str, List[str]], analysis: Dict[str, Any]) -> str:
    normalized = _normalize_severity(severity)
    if normalized != "Unknown":
        return normalized

    cve_count = len(iocs.get("cves", []))
    hash_count = len(iocs.get("hashes", []))
    ip_count = len(iocs.get("ips", []))
    detection_count = len(analysis.get("detections", [])) if isinstance(analysis, dict) else 0

    if cve_count > 0:
        return "High"
    if hash_count > 0 or detection_count >= 5:
        return "High"
    if ip_count > 0 or detection_count > 0:
        return "Medium"
    return "Low"


def _infer_entity_type(indicator: str, explicit_type: str = "") -> str:
    type_hint = str(explicit_type or "").strip().lower()
    indicator = str(indicator or "").strip()
    if "cve" in type_hint or _RE_CVE.search(indicator):
        return "cve"
    if "ip" in type_hint or _RE_IPV4.search(indicator):
        return "ip"
    if "hash" in type_hint or _RE_HASH.search(indicator):
        return "hash"
    if "domain" in type_hint:
        return "domain"
    if "url" in type_hint:
        return "url"
    if _RE_DOMAIN.search(indicator):
        return "domain"
    return "indicator"


def _extract_source_ip(candidate_fields: Iterable[str]) -> str:
    for value in candidate_fields:
        if not value:
            continue
        match = _RE_IPV4.search(str(value))
        if match:
            return match.group(0)
    return "N/A"


def _parse_since(range_value: str) -> Optional[str]:
    mapping = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = mapping.get(range_value)
    if not delta:
        return None
    return (datetime.now(timezone.utc) - delta).isoformat()


class DashboardMetricsStore:
    def __init__(self) -> None:
        root_dir = Path(__file__).resolve().parents[1]
        self._data_dir = root_dir / "data"
        self._db_path = self._data_dir / "dashboard_metrics.db"
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    report_id TEXT,
                    filename TEXT,
                    uploaded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entities (
                    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(upload_id, entity_type, value),
                    FOREIGN KEY(upload_id) REFERENCES uploads(upload_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_ip TEXT NOT NULL,
                    ioc TEXT NOT NULL,
                    type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(upload_id, source_ip, ioc, type, severity),
                    FOREIGN KEY(upload_id) REFERENCES uploads(upload_id) ON DELETE CASCADE
                );
                """
            )

    def _insert_upload(self, conn: sqlite3.Connection, source: str, filename: str, report_id: Optional[str]) -> int:
        now = _now_iso()
        cur = conn.execute(
            """
            INSERT INTO uploads(source, report_id, filename, uploaded_at)
            VALUES (?, ?, ?, ?)
            """,
            (source, report_id, filename, now),
        )
        return int(cur.lastrowid)

    def _insert_entity(
        self,
        conn: sqlite3.Connection,
        *,
        upload_id: int,
        entity_type: str,
        value: str,
        severity: str,
        source: str,
    ) -> None:
        value = str(value or "").strip()
        if not value:
            return
        conn.execute(
            """
            INSERT OR IGNORE INTO entities(upload_id, entity_type, value, severity, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (upload_id, entity_type, value, _normalize_severity(severity), source, _now_iso()),
        )

    def _insert_alert(
        self,
        conn: sqlite3.Connection,
        *,
        upload_id: int,
        timestamp: str,
        source_ip: str,
        ioc: str,
        alert_type: str,
        severity: str,
        source: str,
    ) -> None:
        ioc = str(ioc or "").strip()
        if not ioc:
            return
        conn.execute(
            """
            INSERT OR IGNORE INTO alerts(upload_id, timestamp, source_ip, ioc, type, severity, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                timestamp or _now_iso(),
                source_ip or "N/A",
                ioc,
                alert_type or "Indicator",
                _normalize_severity(severity),
                source,
                _now_iso(),
            ),
        )

    def record_threat_report_analysis(
        self,
        *,
        filename: str,
        report_id: Optional[str],
        severity: str,
        iocs: Dict[str, List[str]],
        analysis: Dict[str, Any],
    ) -> None:
        with self._conn() as conn:
            upload_id = self._insert_upload(conn, source="threat_report", filename=filename, report_id=report_id)
            normalized_severity = _fallback_report_severity(
                severity=severity,
                iocs=iocs if isinstance(iocs, dict) else {},
                analysis=analysis if isinstance(analysis, dict) else {},
            )

            for value in iocs.get("ips", []):
                self._insert_entity(conn, upload_id=upload_id, entity_type="ip", value=value, severity=normalized_severity, source="threat_report")
            for value in iocs.get("domains", []):
                self._insert_entity(conn, upload_id=upload_id, entity_type="domain", value=value, severity=normalized_severity, source="threat_report")
            for value in iocs.get("hashes", []):
                self._insert_entity(conn, upload_id=upload_id, entity_type="hash", value=value, severity=normalized_severity, source="threat_report")
            for value in iocs.get("cves", []):
                self._insert_entity(conn, upload_id=upload_id, entity_type="cve", value=value, severity=normalized_severity, source="threat_report")

            default_ip = iocs.get("ips", ["N/A"])[0] if isinstance(iocs.get("ips"), list) else "N/A"

            for detection in analysis.get("detections", []) if isinstance(analysis, dict) else []:
                signal = str(detection.get("signal", "")).strip() if isinstance(detection, dict) else ""
                if not signal:
                    continue
                detected_type = _infer_entity_type(signal, explicit_type="indicator")
                self._insert_entity(
                    conn,
                    upload_id=upload_id,
                    entity_type=detected_type,
                    value=signal,
                    severity=normalized_severity,
                    source="threat_report",
                )
                self._insert_alert(
                    conn,
                    upload_id=upload_id,
                    timestamp=_now_iso(),
                    source_ip=default_ip,
                    ioc=signal,
                    alert_type="Detection Signal",
                    severity=normalized_severity,
                    source="threat_report",
                )

            for entry in analysis.get("top_iocs", []) if isinstance(analysis, dict) else []:
                if not isinstance(entry, dict):
                    continue
                indicator = str(entry.get("indicator", "")).strip()
                if not indicator:
                    continue
                ioc_type = _infer_entity_type(indicator, explicit_type=str(entry.get("type", "")))
                self._insert_entity(
                    conn,
                    upload_id=upload_id,
                    entity_type=ioc_type,
                    value=indicator,
                    severity=normalized_severity,
                    source="threat_report",
                )
                self._insert_alert(
                    conn,
                    upload_id=upload_id,
                    timestamp=_now_iso(),
                    source_ip=default_ip,
                    ioc=indicator,
                    alert_type=str(entry.get("type", "Indicator")),
                    severity=normalized_severity,
                    source="threat_report",
                )

    def record_log_analysis(self, *, filename: str, chunk_results: List[Dict[str, Any]]) -> None:
        with self._conn() as conn:
            upload_id = self._insert_upload(conn, source="log", filename=filename, report_id=None)

            for chunk in chunk_results or []:
                analysis = chunk.get("analysis", {}) if isinstance(chunk, dict) else {}
                matches = analysis.get("matches", []) if isinstance(analysis, dict) else []
                for match in matches:
                    if not isinstance(match, dict):
                        continue
                    label = str(match.get("label") or match.get("source") or "Unknown Indicator").strip()
                    match_type = str(match.get("type") or "").strip()
                    text = str(match.get("text") or "")
                    metadata = match.get("metadata", {}) if isinstance(match.get("metadata"), dict) else {}

                    source_ip = _extract_source_ip(
                        [
                            metadata.get("src_ip"),
                            metadata.get("source_ip"),
                            metadata.get("dest_ip"),
                            metadata.get("dst_ip"),
                            text,
                            label,
                        ]
                    )
                    severity = _infer_severity_from_text(match.get("label"), match.get("source"), text, match_type)
                    score_severity = _severity_from_score(match.get("score"))
                    if score_severity != "Unknown":
                        severity = score_severity if severity == "Medium" else severity
                    entity_type = _infer_entity_type(label, explicit_type=match_type)

                    self._insert_entity(
                        conn,
                        upload_id=upload_id,
                        entity_type=entity_type,
                        value=label,
                        severity=severity,
                        source="log",
                    )
                    self._insert_alert(
                        conn,
                        upload_id=upload_id,
                        timestamp=_now_iso(),
                        source_ip=source_ip,
                        ioc=label,
                        alert_type=match_type or entity_type.upper(),
                        severity=severity,
                        source="log",
                    )

    def _source_filters(self, source: str) -> Tuple[str, List[str]]:
        source = (source or "all").lower()
        mapped = _SOURCE_MAP.get(source)
        if not mapped:
            return "", []
        return " AND source = ? ", [mapped]

    def get_stats(self, *, source: str = "all") -> Dict[str, int]:
        with self._conn() as conn:
            since_week = _parse_since("7d")
            since_24h = _parse_since("24h")
            source_sql, source_args = self._source_filters(source)

            total_cves = conn.execute(
                f"""
                SELECT COUNT(DISTINCT value) AS n
                FROM entities
                WHERE entity_type = 'cve' AND created_at >= ? {source_sql}
                """,
                [since_week] + source_args,
            ).fetchone()["n"]

            ioc_detections = conn.execute(
                f"""
                SELECT COUNT(DISTINCT value) AS n
                FROM entities
                WHERE entity_type IN ('ip','domain','hash','indicator','url')
                  AND created_at >= ? {source_sql}
                """,
                [since_24h] + source_args,
            ).fetchone()["n"]

            critical_alerts = conn.execute(
                f"""
                SELECT COUNT(*) AS n
                FROM alerts
                WHERE severity = 'Critical' {source_sql}
                """,
                source_args,
            ).fetchone()["n"]

            return {
                "totalCVEs": int(total_cves or 0),
                "iocDetections": int(ioc_detections or 0),
                "criticalAlerts": int(critical_alerts or 0),
            }

    def get_severity_breakdown(self, *, range_value: str = "30d", source: str = "all") -> List[Dict[str, Any]]:
        with self._conn() as conn:
            since = _parse_since(range_value)
            source_sql, source_args = self._source_filters(source)
            time_sql = " AND created_at >= ? " if since else ""
            params: List[Any] = ([since] if since else []) + source_args

            rows = conn.execute(
                f"""
                SELECT severity, COUNT(*) AS count
                FROM alerts
                WHERE 1=1 {time_sql} {source_sql}
                GROUP BY severity
                """,
                params,
            ).fetchall()

            counts = {row["severity"]: int(row["count"]) for row in rows}
            ordered = ["Critical", "High", "Medium", "Low", "Informational"]
            return [
                {
                    "name": name,
                    "value": counts.get(name, 0),
                    "fill": SEVERITY_COLORS.get(name, SEVERITY_COLORS["Unknown"]),
                }
                for name in ordered
            ]

    def get_recent_alerts(self, *, limit: int = 10, source: str = "all") -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._conn() as conn:
            source_sql, source_args = self._source_filters(source)
            rows = conn.execute(
                f"""
                SELECT timestamp, source_ip, ioc, type, severity
                FROM alerts
                WHERE 1=1 {source_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                source_args + [safe_limit],
            ).fetchall()

            return [
                {
                    "timestamp": row["timestamp"],
                    "sourceIp": row["source_ip"],
                    "ioc": row["ioc"],
                    "type": row["type"],
                    "severity": row["severity"],
                }
                for row in rows
            ]

    def get_metrics(self, *, range_value: str = "30d", source: str = "all", recent_limit: int = 10) -> Dict[str, Any]:
        return {
            "totals": self.get_stats(source=source),
            "severity_breakdown": self.get_severity_breakdown(range_value=range_value, source=source),
            "recent_alerts": self.get_recent_alerts(limit=recent_limit, source=source),
            "last_updated": _now_iso(),
        }

    def clear_metrics(self, *, source: str = "all") -> Dict[str, Any]:
        with self._conn() as conn:
            mapped = _SOURCE_MAP.get((source or "all").lower())
            if mapped:
                conn.execute("DELETE FROM uploads WHERE source = ?", (mapped,))
                deleted_scope = source
            else:
                conn.execute("DELETE FROM uploads")
                deleted_scope = "all"

        return {"status": "success", "cleared": deleted_scope, "timestamp": _now_iso()}


metrics_store = DashboardMetricsStore()
