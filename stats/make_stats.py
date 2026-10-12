"""Regenerate the dataset statistics (tables and figures) from data/.

Usage: python stats/make_stats.py   (requires matplotlib)
"""
import csv, json, statistics
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
TABLES, FIGS = ROOT / "stats/tables", ROOT / "stats/figures"
TABLES.mkdir(parents=True, exist_ok=True); FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
                     "font.size": 12, "axes.labelsize": 14, "xtick.labelsize": 12, "ytick.labelsize": 12})
DARK = "#313131"
PALETTE = ["#003f5c", "#58508d", "#bc5090", "#ff6361", "#ffa600"]

meta = list(csv.DictReader(open(ROOT / "data/apt_metadata.csv")))
campaigns = json.load(open(ROOT / "data/campaigns.json"))
chains = json.load(open(ROOT / "data/apt_chains.json"))
N = len(meta)


def save(fig, name):
    """PDF for papers, PNG for the README."""
    fig.savefig(FIGS / name, dpi=300, bbox_inches="tight")
    fig.savefig(FIGS / name.replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def write_counts(name, counter, total, label):
    with open(TABLES / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow([label, "n_groups", "percent"])
        for k, v in counter.most_common():
            w.writerow([k, v, round(100 * v / total, 1)])


def barh(counter, xlabel, out, top=None, figsize=(8, 4)):
    items = counter.most_common(top)
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh([k for k, _ in items], [v for _, v in items], color=DARK)
    ax.invert_yaxis(); ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
    for b in bars:
        ax.text(b.get_width() + 0.2, b.get_y() + b.get_height() / 2, str(int(b.get_width())),
                ha="left", va="center", fontweight="bold", fontsize=10)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    fig.tight_layout(); save(fig, out)


def pie(counter, out, startangle):
    items = counter.most_common()
    fig, ax = plt.subplots(figsize=(8, 4))
    _, _, autos = ax.pie([v for _, v in items], labels=[k for k, _ in items], autopct="%1.1f%%",
                         colors=PALETTE, startangle=startangle, textprops={"fontsize": 10, "weight": "bold"})
    for a in autos:
        a.set_color("white")
    save(fig, out)


# --- group-level statistics (paper appendix, Figs. "APT timeline" and "APT analysis")
sectors = Counter(s.strip() for m in meta for s in m["target_sectors"].split(";"))
objectives = Counter(m["primary_objective"] for m in meta)
platforms = Counter(m["platforms"] for m in meta)
write_counts("target_sectors", sectors, N, "sector")
write_counts("objectives", objectives, N, "objective")
write_counts("platforms", platforms, N, "platforms")
barh(sectors, "Number of APT Groups", "target_sectors_distribution.pdf", top=12)  # figure: top 12; table: all
pie(objectives, "objectives_distribution.pdf", 90)
pie(platforms, "os_distribution.pdf", 45)

tl = sorted(meta, key=lambda m: int(m["first_seen"]))
fig, ax = plt.subplots(figsize=(6.6, 5.0))
for i, m in enumerate(tl):
    s, e = int(m["first_seen"]), int(m["last_seen"])
    ax.barh(i, max(e - s, 0.5), left=s, height=0.6, color=DARK, alpha=0.75, edgecolor="black", linewidth=0.5)
ax.set_yticks(range(len(tl))); ax.set_yticklabels([m["apt"] for m in tl], fontsize=15)
ax.set_xlabel("Year", fontsize=16, fontweight="bold"); ax.tick_params(axis="x", labelsize=14)
ax.grid(axis="x", alpha=0.3, linestyle="--"); ax.invert_yaxis()
ax.set_xlim(min(int(m["first_seen"]) for m in tl) - 1, max(int(m["last_seen"]) for m in tl) + 1)
fig.tight_layout(); save(fig, "apt_timeline.pdf")

# --- sequence-level statistics
def summary(name, lengths):
    return {"set": name, "n": len(lengths), "min": min(lengths), "median": statistics.median(lengths),
            "mean": round(statistics.mean(lengths), 1), "max": max(lengths)}

paper = [c for c in campaigns if c["used_in_paper"]]
rows = [summary("campaigns (all)", [c["n_techniques"] for c in campaigns]),
        summary("campaigns (used in paper)", [c["n_techniques"] for c in paper]),
        summary("campaigns (steps, all)", [c["n_steps"] for c in campaigns]),
        summary("apt_chains", [c["n_techniques"] for c in chains])]
with open(TABLES / "sequence_lengths.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

with open(TABLES / "campaigns_per_group.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["apt", "attack_group_id", "n_campaigns", "first_seen", "last_seen"])
    for m in sorted(meta, key=lambda m: m["apt"]):
        w.writerow([m["apt"], m["attack_group_id"], m["n_campaigns"], m["first_seen"], m["last_seen"]])

tech = Counter(t for c in campaigns for t in {t for st in c["sequence"] for t in st})
with open(TABLES / "technique_frequency.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["technique", "n_campaigns"])
    w.writerows(tech.most_common())

fig, ax = plt.subplots(figsize=(6, 3.5))
ax.hist([c["n_techniques"] for c in campaigns], bins=range(0, 60, 4), color=DARK, edgecolor="white")
ax.set_xlabel("Techniques per campaign", fontweight="bold"); ax.set_ylabel("Campaigns", fontweight="bold")
ax.grid(axis="y", alpha=0.3, linestyle="--")
fig.tight_layout(); save(fig, "campaign_length_distribution.pdf")

print(f"{N} groups, {len(campaigns)} campaigns ({len(paper)} used in paper), {len(chains)} per-group chains, "
      f"{len(tech)} distinct techniques")
for r in rows:
    print(r)
print("objectives:", {k: f"{100 * v / N:.1f}%" for k, v in objectives.most_common()})
print("platforms:", {k: f"{100 * v / N:.1f}%" for k, v in platforms.most_common()})
print("sectors:", len(sectors))
