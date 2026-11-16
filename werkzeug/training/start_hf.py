"""Daten packen, hochladen und den Trainingslauf auf Hugging Face Jobs starten.

    python train_start.py <Name des Laufs> <Schritte> <Lernrate> <Hardware> <Datenordner> [weitere Datenordner] [--keep]
"""
import json, pathlib, sys, tarfile
import huggingface_hub as h
here = pathlib.Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
name, steps, lr, flavor, folders = args[0], args[1], args[2], args[3], [pathlib.Path(a) for a in args[4:]]
api = h.HfApi(); repo = api.whoami()["name"] + "/localscribe-training"
tar_path = here / "daten.tar"
if "--keep" not in sys.argv:
    rows = []
    with tarfile.open(tar_path, "w") as tar:
        for k, folder in enumerate(folders):
            for line in open(folder / "liste.jsonl", encoding="utf-8"):
                r = json.loads(line); src = folder / r["audio"]
                r["audio"] = f"audio/d{k}_{src.name}"; tar.add(src, r["audio"]); rows.append(r)
        tmp = here / "liste_alle.jsonl"
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        tar.add(tmp, "liste.jsonl")
    print("gepackt", len(rows), "Sätze,", round(tar_path.stat().st_size / 1e6), "MB", flush=True)
    api.upload_file(path_or_fileobj=str(tar_path), path_in_repo="daten.tar", repo_id=repo, repo_type="dataset")
    api.upload_file(path_or_fileobj=str(here.parent.parent / "diktat" / "fachlexikon.json"), path_in_repo="fachlexikon.json", repo_id=repo, repo_type="dataset")
    print("hochgeladen", flush=True)
job = api.run_uv_job(str(here / "trainieren.py"), script_args=["daten", name, steps, lr, f"--repo={repo}"] + [a for a in sys.argv if a == "--voll" or a.startswith("--neuro=")], flavor=flavor, timeout="75m",
                     secrets={"HF_TOKEN": h.get_token()}, name="localscribe-" + name)
print("JOB", job.id, job.url)
(here / "job_id.txt").write_text(job.id)
