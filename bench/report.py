"""
Trinetra Resilience Report Generator
Produces exportable, production-grade HTML and JSON resilience reports
complete with mathematical formula breakdowns, safety invariant audits,
and consortium certification grading.
"""
from typing import Dict, Any
import json
import time


def generate_html_report(snapshot: Dict[str, Any]) -> str:
    """Generate self-contained standalone HTML resilience report."""
    metrics = snapshot.get("metrics", {})
    resilience = metrics.get("resilience", {})
    score = resilience.get("score", 0.0)
    grade = resilience.get("grade", "F")
    components = resilience.get("components", {})
    invariants = snapshot.get("invariants", {})
    nodes = snapshot.get("nodes", [])

    grade_color = {
        "A": "#2ECC71",
        "B": "#4C8DFF",
        "C": "#FFC857",
        "D": "#F5A623",
        "F": "#FF4D4F"
    }.get(grade, "#FF4D4F")

    nodes_html = "".join([
        f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-family: monospace;">N{n['id']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E;">{n['role']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-family: monospace;">Term {n['term']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-family: monospace;">Block #{n['height']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-family: monospace;">{n['head_hash']}..</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-weight: 600; color: {'#2ECC71' if n['status'] == 'HEALTHY' else '#FF4D4F'};">{n['status']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #24305E; font-family: monospace;">{n['trust_score']}%</td>
        </tr>
        """ for n in nodes
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Trinetra Resilience Certification Report</title>
    <style>
        body {{
            background-color: #0B1020;
            color: #E6E9F5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: #121A33;
            border: 1px solid #24305E;
            border-radius: 16px;
            padding: 36px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #24305E;
            padding-bottom: 24px;
            margin-bottom: 28px;
        }}
        .logo {{
            font-size: 26px;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: #6C63FF;
        }}
        .sublogo {{
            font-size: 13px;
            color: #9AA4C4;
            margin-top: 4px;
        }}
        .grade-badge {{
            text-align: center;
            background: #18224A;
            border: 2px solid {grade_color};
            border-radius: 12px;
            padding: 12px 28px;
        }}
        .grade-val {{
            font-size: 42px;
            font-weight: 900;
            color: {grade_color};
            line-height: 1;
        }}
        .grade-score {{
            font-size: 14px;
            color: #9AA4C4;
            margin-top: 4px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 28px;
        }}
        .card {{
            background: #18224A;
            border: 1px solid #24305E;
            border-radius: 10px;
            padding: 18px;
        }}
        .card h3 {{
            margin-top: 0;
            font-size: 12px;
            letter-spacing: 1px;
            color: #9AA4C4;
            text-transform: uppercase;
        }}
        .stat {{
            font-size: 28px;
            font-weight: 700;
            color: #E6E9F5;
            font-family: monospace;
        }}
        .stat-sub {{
            font-size: 12px;
            color: #9AA4C4;
            margin-top: 4px;
        }}
        .formula-box {{
            background: #0B1020;
            border: 1px dashed #6C63FF;
            border-radius: 8px;
            padding: 16px;
            font-family: monospace;
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 28px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}
        th {{
            padding: 10px;
            border-bottom: 2px solid #24305E;
            color: #9AA4C4;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .inv-chip {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 8px;
            margin-bottom: 8px;
        }}
        .inv-pass {{
            background: rgba(46, 204, 113, 0.15);
            color: #2ECC71;
            border: 1px solid #2ECC71;
        }}
        .inv-fail {{
            background: rgba(255, 77, 79, 0.15);
            color: #FF4D4F;
            border: 1px solid #FF4D4F;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: #9AA4C4;
            margin-top: 36px;
            border-top: 1px solid #24305E;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="logo">🧿 TRINETRA CHAOS CONSOLE</div>
                <div class="sublogo">Consortium Blockchain Resilience & Consensus Safety Audit</div>
            </div>
            <div class="grade-badge">
                <div class="grade-val">{grade}</div>
                <div class="grade-score">{score} / 100</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <h3>Throughput & Latency</h3>
                <div class="stat">{metrics.get('tps', 0)} TPS</div>
                <div class="stat-sub">p50: {metrics.get('p50_ms', 0)} ms | p95: {metrics.get('p95_ms', 0)} ms</div>
            </div>
            <div class="card">
                <h3>Recovery & Churn</h3>
                <div class="stat">{metrics.get('mttr_ms', 0)} ms</div>
                <div class="stat-sub">MTTR failover | Churn: {metrics.get('churn_per_min', 0)} elections/min</div>
            </div>
        </div>

        <h3>Published Mathematical Formula</h3>
        <div class="formula-box">
            <b>Safety Gate:</b> If Fork Detected OR State-Root Mismatch &rArr; Score = 0 (Grade F)<br>
            <b>Resilience Formula:</b> Score = 100 &times; (0.45&times;Availability + 0.25&times;Recovery + 0.20&times;Stability + 0.10&times;Efficiency)<br>
            &bull; Availability ({components.get('availability', 0)}): Share of 500ms windows with committed blocks<br>
            &bull; Recovery ({components.get('recovery', 0)}): clamp(1 - MTTR / 5.0s, 0, 1)<br>
            &bull; Stability ({components.get('stability', 0)}): 1 - min(1, elections_per_minute / 10.0)<br>
            &bull; Efficiency ({components.get('efficiency', 0)}): clamp(baseline_msgs / actual_msgs, 0, 1)
        </div>

        <h3>Consensus Safety Invariants</h3>
        <div style="margin-bottom: 24px;">
            <span class="inv-chip {'inv-pass' if invariants.get('election_safety') else 'inv-fail'}">
                {'✔' if invariants.get('election_safety') else '✖'} Election Safety
            </span>
            <span class="inv-chip {'inv-pass' if invariants.get('log_matching') else 'inv-fail'}">
                {'✔' if invariants.get('log_matching') else '✖'} Log Matching
            </span>
            <span class="inv-chip {'inv-pass' if invariants.get('chain_integrity') else 'inv-fail'}">
                {'✔' if invariants.get('chain_integrity') else '✖'} Chain Integrity
            </span>
            <span class="inv-chip {'inv-pass' if invariants.get('no_fork') else 'inv-fail'}">
                {'✔' if invariants.get('no_fork') else '✖'} Fork Prevention
            </span>
            <span class="inv-chip {'inv-pass' if invariants.get('state_root_agreement') else 'inv-fail'}">
                {'✔' if invariants.get('state_root_agreement') else '✖'} State-Root Agreement
            </span>
        </div>

        <h3>Validator Node Cluster Snapshot</h3>
        <table>
            <thead>
                <tr>
                    <th>Node</th>
                    <th>Role</th>
                    <th>Term</th>
                    <th>Height</th>
                    <th>Head Hash</th>
                    <th>Status</th>
                    <th>Trust</th>
                </tr>
            </thead>
            <tbody>
                {nodes_html}
            </tbody>
        </table>

        <div class="footer">
            Certified by Trinetra Chaos Engineering Suite &bull; Deterministic &amp; Cryptographically Audited
        </div>
    </div>
</body>
</html>
"""
