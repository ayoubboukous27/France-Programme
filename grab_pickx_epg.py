#!/usr/bin/env python3
"""
grab_pickx_epg.py

Génère le fichier EPG (XMLTV) pour le site pickx.be en s'appuyant sur
l'outil officiel iptv-org/epg (Node.js), qui contient déjà toute la
logique de scraping (détection de version d'API, parsing JSON, etc.)
pour ce site — logique qui change souvent et qu'il est déconseillé de
réimplémenter en Python.

Ensuite, le script enrichit chaque <channel> du guide avec un tag
<icon src="..."/> pointant vers le logo correspondant dans le dépôt
tv-logo/tv-logos (dossier countries/belgium), quand une correspondance
est trouvée.

Étapes :
  1. Clone (ou met à jour) un checkout shallow de iptv-org/epg.
  2. Installe les dépendances npm (une seule fois).
  3. Lance `npm run grab -- --sites=pickx.be [--lang=xx] [--days=N]`.
  4. Clone (sparse) le dossier countries/belgium de tv-logo/tv-logos.
  5. Fait correspondre chaque chaîne du guide à un logo par nom normalisé
     (xmltv_id en priorité, sinon display-name), et insère <icon src="...">.
  6. Sauvegarde le résultat au chemin de sortie demandé.

Utilisation :
    python3 grab_pickx_epg.py --output epg/pickx.be.xml
    python3 grab_pickx_epg.py --output epg/pickx.be.xml --lang nl --days 3
    python3 grab_pickx_epg.py --output epg/pickx.be.xml --no-logos

Prérequis sur la machine / le runner CI : git, node (>=18), npm.
"""

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

EPG_REPO_URL = "https://github.com/iptv-org/epg.git"
LOGOS_REPO_URL = "https://github.com/tv-logo/tv-logos.git"
LOGOS_RAW_BASE = "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/belgium"
SITE = "pickx.be"


def run(cmd, cwd=None):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"Commande échouée ({result.returncode}): {' '.join(str(c) for c in cmd)}")


# ---------------------------------------------------------------------------
# iptv-org/epg : récupération du guide
# ---------------------------------------------------------------------------

def ensure_repo(work_dir: Path, repo_url: str, branch: str = "master"):
    if (work_dir / ".git").exists():
        print(f"Dépôt déjà présent dans {work_dir}, mise à jour...")
        run(["git", "fetch", "--depth", "1", "origin", branch], cwd=work_dir)
        run(["git", "reset", "--hard", f"origin/{branch}"], cwd=work_dir)
    else:
        print(f"Clonage de {repo_url} dans {work_dir}...")
        work_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "-b", branch, repo_url, str(work_dir)])


def ensure_npm_deps(work_dir: Path):
    if (work_dir / "node_modules").exists():
        print("node_modules déjà installé, on saute npm install.")
        return
    run(["npm", "install"], cwd=work_dir)


def grab(work_dir: Path, lang, days):
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


# ---------------------------------------------------------------------------
# tv-logo/tv-logos : récupération et indexation des logos belges
# ---------------------------------------------------------------------------

def ensure_logos_repo(logos_dir: Path) -> bool:
    """Clone en mode sparse uniquement countries/belgium. Retourne False en cas d'échec."""
    try:
        if (logos_dir / ".git").exists():
            print(f"Dépôt logos déjà présent dans {logos_dir}, mise à jour...")
            run(["git", "fetch", "--depth", "1", "origin", "main"], cwd=logos_dir)
            run(["git", "reset", "--hard", "origin/main"], cwd=logos_dir)
        else:
            print(f"Clonage (sparse) de {LOGOS_REPO_URL}...")
            logos_dir.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                 LOGOS_REPO_URL, str(logos_dir)])
            run(["git", "sparse-checkout", "set", "countries/belgium"], cwd=logos_dir)
        return True
    except SystemExit as e:
        print(f"⚠️  Impossible de récupérer les logos ({e}), le guide sera généré sans icônes.")
        return False


def normalize(name: str) -> str:
    """Réduit un nom à ses seuls caractères alphanumériques, en minuscule."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_logo_index(logos_dir: Path) -> dict:
    """Associe une clé normalisée (ex: 'vtm2') au nom de fichier du logo (ex: 'vtm2-be.png')."""
    belgium_dir = logos_dir / "countries" / "belgium"
    index = {}
    if not belgium_dir.exists():
        return index

    for f in sorted(belgium_dir.glob("*.png")):
        stem = f.stem  # ex: "vtm2-be"
        stem_no_country = re.sub(r"-be$", "", stem, flags=re.IGNORECASE)
        key = normalize(stem_no_country)
        # on garde le premier match (fichiers triés alphabétiquement = plus stable)
        index.setdefault(key, f.name)
    return index


def find_logo(channel_id: str, display_names: list, logo_index: dict):
    candidates = []
    if channel_id:
        # ex: "VTM2.be" -> "VTM2"
        candidates.append(re.sub(r"\.be$", "", channel_id, flags=re.IGNORECASE))
    candidates.extend(display_names)

    for candidate in candidates:
        key = normalize(candidate)
        if key in logo_index:
            return logo_index[key]
    return None


def add_logos(guide_path: Path, logo_index: dict) -> tuple:
    tree = ET.parse(guide_path)
    root = tree.getroot()

    matched, total = 0, 0
    for channel in root.findall("channel"):
        total += 1
        if channel.find("icon") is not None:
            continue  # déjà une icône (peu probable pour pickx.be, mais on ne l'écrase pas)

        channel_id = channel.get("id", "")
        display_names = [dn.text for dn in channel.findall("display-name") if dn.text]

        logo_file = find_logo(channel_id, display_names, logo_index)
        if not logo_file:
            continue

        icon = ET.Element("icon", {"src": f"{LOGOS_RAW_BASE}/{quote(logo_file)}"})
        channel.append(icon)
        matched += 1

    tree.write(guide_path, encoding="UTF-8", xml_declaration=True)
    return matched, total


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Génère le guide EPG pickx.be (avec logos) via iptv-org/epg")
    parser.add_argument("--output", required=True, help="Chemin du fichier XMLTV de sortie")
    parser.add_argument("--work-dir", default=".epg-tool", help="Dossier de checkout de iptv-org/epg")
    parser.add_argument("--logos-dir", default=".logos-tool", help="Dossier de checkout de tv-logo/tv-logos")
    parser.add_argument("--lang", default=None, help="Filtrer par langue, ex: nl, fr, en")
    parser.add_argument("--days", type=int, default=None, help="Nombre de jours à récupérer")
    parser.add_argument("--no-logos", action="store_true", help="Ne pas ajouter les logos")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    output_path = Path(args.output).resolve()

    ensure_repo(work_dir, EPG_REPO_URL, "master")
    ensure_npm_deps(work_dir)
    guide_path = grab(work_dir, args.lang, args.days)

    if not args.no_logos:
        logos_dir = Path(args.logos_dir).resolve()
        if ensure_logos_repo(logos_dir):
            logo_index = build_logo_index(logos_dir)
            print(f"{len(logo_index)} logos belges indexés.")
            matched, total = add_logos(guide_path, logo_index)
            print(f"🖼️  Logos ajoutés à {matched}/{total} chaînes.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(guide_path, output_path)
    print(f"✅ Guide EPG pickx.be sauvegardé dans : {output_path}")


if __name__ == "__main__":
    main()
