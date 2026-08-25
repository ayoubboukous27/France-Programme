#!/usr/bin/env python3
"""
grab_pickx_epg.py

Génère le fichier EPG (XMLTV) pour le site pickx.be en s'appuyant sur
l'outil officiel iptv-org/epg (Node.js), qui contient déjà toute la
logique de scraping (détection de version d'API, parsing JSON, etc.)
pour ce site — logique qui change souvent et qu'il est déconseillé de
réimplémenter en Python.

Ce script :
  1. Clone (ou met à jour) un checkout shallow de iptv-org/epg dans un
     dossier de travail.
  2. Installe les dépendances npm (une seule fois).
  3. Lance `npm run grab -- --site=pickx.be [--lang=xx] [--days=N]`.
  4. Copie le guide.xml généré vers le chemin de sortie demandé.

Utilisation :
    python3 grab_pickx_epg.py --output epg/pickx.be.xml
    python3 grab_pickx_epg.py --output epg/pickx.be.xml --lang nl --days 3

Prérequis sur la machine / le runner CI : git, node (>=18), npm.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/iptv-org/epg.git"
SITE = "pickx.be"


def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"Commande échouée ({result.returncode}): {' '.join(cmd)}")


def ensure_repo(work_dir: Path):
    if (work_dir / ".git").exists():
        print(f"Dépôt déjà présent dans {work_dir}, mise à jour...")
        run(["git", "fetch", "--depth", "1", "origin", "master"], cwd=work_dir)
        run(["git", "reset", "--hard", "origin/master"], cwd=work_dir)
    else:
        print(f"Clonage de {REPO_URL} dans {work_dir}...")
        work_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "-b", "master", REPO_URL, str(work_dir)])


def ensure_npm_deps(work_dir: Path):
    node_modules = work_dir / "node_modules"
    if node_modules.exists():
        print("node_modules déjà installé, on saute npm install.")
        return
    run(["npm", "install"], cwd=work_dir)


def grab(work_dir: Path, lang: str | None, days: int | None):
    guide_path = work_dir / "guide.xml"
    if guide_path.exists():
        guide_path.unlink()

    cmd = ["npm", "run", "grab", "--", f"--sites={SITE}"]
    if lang:
        cmd.append(f"--lang={lang}")
    if days:
        cmd.append(f"--days={days}")

    run(cmd, cwd=work_dir)

    if not guide_path.exists():
        sys.exit("guide.xml n'a pas été généré, vérifie les logs npm ci-dessus.")
    return guide_path


def main():
    parser = argparse.ArgumentParser(description="Génère le guide EPG pickx.be via iptv-org/epg")
    parser.add_argument("--output", required=True, help="Chemin du fichier XMLTV de sortie")
    parser.add_argument("--work-dir", default=".epg-tool", help="Dossier de checkout de iptv-org/epg")
    parser.add_argument("--lang", default=None, help="Filtrer par langue, ex: nl, fr, en")
    parser.add_argument("--days", type=int, default=None, help="Nombre de jours à récupérer")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    output_path = Path(args.output).resolve()

    ensure_repo(work_dir)
    ensure_npm_deps(work_dir)
    guide_path = grab(work_dir, args.lang, args.days)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(guide_path, output_path)
    print(f"✅ Guide EPG pickx.be sauvegardé dans : {output_path}")


if __name__ == "__main__":
    main()
